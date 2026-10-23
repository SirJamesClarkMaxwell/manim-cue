"""Adapter mediów PC; otwieranie i dekodowanie odbywa się w osobnym procesie."""

import struct
import time
from multiprocessing import get_context
from multiprocessing.shared_memory import SharedMemory

from .decoder_worker import HEADER, PROGRESS, SLOT, run_pooled

POOL_SIZE = 4
"""Ciepłe procesy na bazę i do trzech klipów slajdu; podgląd może wystartować na zimno."""
_pool = []


def _spawn():
    context = get_context("spawn")
    control = context.RawArray("d", [0] * 12)
    connection, child = context.Pipe()
    process = context.Process(target=run_pooled, args=(control, child), daemon=True)
    process.start()
    child.close()
    return process, connection, control


def _take():
    """Start procesu i importy (ok. 0,2–0,35 s) poza ścieżką wejścia na slajd."""
    while _pool:
        worker = _pool.pop(0)
        if worker[0].is_alive():
            break
        worker[1].close()
    else:
        worker = _spawn()
    while len(_pool) < POOL_SIZE:
        _pool.append(_spawn())
    return worker


def close_pool() -> None:
    """Zamknięty potok kończy czekający proces puli bez join w UI."""
    while _pool:
        _pool.pop()[1].close()


class Source:
    """Nieblokujący nadzorca źródła z dwoma slotami RGBA i generacją."""

    def __init__(self):
        self.generation = 0
        self.entry_id = 0
        self.process = None
        self.connection = None
        self.memory = None
        self.retired = []
        self.frame = None
        self.last_revision = 0
        self.dropped = 0
        self.status = "preparing"
        self.error = None
        self.duration = None
        self.eof = False
        self.width = self.height = 0
        self.started = self.progress = 0.0

    def prepare(self, entry_id: int, media: dict) -> None:
        """Unieważnij stare wyniki; proces z puli nie wykonuje decode w UI."""
        self.request_close()
        self.generation += 1
        self.entry_id = entry_id
        self.frame, self.last_revision = None, 0
        self.dropped = 0
        self.status, self.error, self.eof = "preparing", None, False
        self.duration = None
        self.started = self.progress = time.monotonic()
        self.media = dict(media)
        self.process, self.connection, self.control = _take()
        self.connection.send(self.media)

    def poll(self, now: float, target: float | None, budget_ms: float) -> dict:
        """Kopiuj tylko najnowszy spójny slot, zachowując ostatni dobry obraz."""
        deadline = time.perf_counter() + min(1, max(0, budget_ms)) / 1000
        self.poll_closed(now)
        if self.connection is not None and self.status != "error":
            if target is not None:
                self.control[3] = target
                self.control[4] += 1
            for _ in range(4):
                if time.perf_counter() >= deadline:
                    break
                try:
                    if not self.connection.poll():
                        break
                    message = self.connection.recv()
                except (EOFError, OSError):
                    if not self.eof and self.status != "error":
                        self.status, self.error = "error", "Dekoder zakończył połączenie"
                    break
                self.progress = now
                kind = message["type"]
                if kind == "memory":
                    try:
                        self.memory = SharedMemory(name=message["name"])
                    except OSError as error:
                        self.status, self.error = "error", f"Pamięć dekodera niedostępna: {error}"
                        break
                    self.width, self.height = message["width"], message["height"]
                    self.duration = message["duration"]
                elif kind == "error":
                    self.status, self.error = "error", message["error"]
                    break
                elif kind == "eof":
                    self.eof = True
            if self.memory is not None and time.perf_counter() < deadline:
                self.progress = max(
                    self.progress, struct.unpack_from("<d", self.memory.buf, PROGRESS)[0]
                )
                headers = [(SLOT.unpack_from(self.memory.buf, i * SLOT.size), i) for i in range(2)]
                # Zapis w toku (nieparzysta rewizja) ani klatka wyprzedzona przed show_at nie
                # zasłania gotowej klatki drugiego slotu; przy vsync 60 Hz pominięty tick to
                # zgubiona klatka materiału 60 fps.
                due = [item for item in headers if item[0][0] % 2 == 0 and item[0][3] <= now]
                (revision, frame_id, pts, _), slot = max(due, default=((0, 0, 0.0, 0.0), 0))
                if revision > self.last_revision:
                    size = self.width * self.height * 4
                    start = HEADER + slot * size
                    pixels = bytes(self.memory.buf[start : start + size])
                    if SLOT.unpack_from(self.memory.buf, slot * SLOT.size)[0] == revision:
                        previous = self.frame["frame_id"] if self.frame else -1
                        self.dropped += max(0, frame_id - previous - 1)
                        self.frame = {
                            "frame_id": frame_id,
                            "pts": pts,
                            "rgba": pixels,
                            "width": self.width,
                            "height": self.height,
                            "stride": 4 * self.width,
                        }
                        self.last_revision, self.progress = revision, now
                        if self.status != "error":
                            self.status = "ready"
            if self.status == "preparing" and now - self.started > 5:
                self.status, self.error = "error", "Przygotowanie przekroczyło 5 s"
            elif self.status != "preparing" and not self.eof and now - self.progress > 2:
                self.status, self.error = "error", "Brak postępu dekodera przez 2 s"
            if self.status == "error":
                self.request_close()
        return {
            "status": "eof" if self.eof and self.frame and self.status != "error" else self.status,
            "generation": self.generation,
            "entry_id": self.entry_id,
            "duration": self.duration,
            "error": self.error,
            "metrics": {
                "decode_s": self.control[6],
                "conversion_s": self.control[7],
                "seek_s": self.control[8],
                "decoded": int(self.control[9]),
                "published": int(self.control[10]),
                "loop_seek_s": self.control[11],
                "dropped": self.dropped,
            },
            **(self.frame or {}),
        }

    def play(self, anchor: float) -> None:
        """Zamów wspólną kotwicę czasu grupy."""
        if self.process is not None:
            self.control[2] = anchor
            self.control[1] = 1

    def pause(self) -> None:
        """Zatrzymaj czas dekodera bez czekania na potwierdzenie."""
        if self.process is not None:
            self.control[1] = 0

    def reset(self, entry_id: int) -> None:
        """Nowa generacja czyta plik od początku."""
        self.prepare(entry_id, self.media)

    def request_loop_exit(self) -> None:
        """Dokończ bieżącą iterację i zachowaj jej prawdziwą ostatnią klatkę."""
        if self.process is not None:
            self.control[5] = 1

    def request_close(self) -> None:
        """Zakończ proces bez join w UI; odroczenie zwolnienia uchwytu."""
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.retired.append(self.process)
            self.process = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self.memory is not None:
            self.memory.close()
            self.memory = None

    def poll_closed(self, now: float) -> bool:
        """Zwolnij wyłącznie zakończone procesy; nigdy nie czekaj na działający."""
        pending = []
        for process in self.retired:
            if process.is_alive():
                pending.append(process)
            else:
                process.close()
        self.retired = pending
        return self.process is None and not pending
