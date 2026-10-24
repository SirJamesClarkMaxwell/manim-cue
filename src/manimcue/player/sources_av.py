"""Adapter mediów PC; otwieranie i dekodowanie odbywa się w osobnym procesie."""

import struct
import time
import weakref
from collections import OrderedDict
from multiprocessing import get_context
from multiprocessing.shared_memory import SharedMemory

from .decoder_worker import HEADER, PROGRESS, SLOT, run_pooled, run_thumbnail

POOL_SIZE = 4
"""Ciepłe procesy na bazę i do trzech klipów slajdu; podgląd może wystartować na zimno."""
_pool = []
_sources = weakref.WeakSet()
_retiring_pool = []
_budget = None


def configure_budget(budget):
    global _budget
    _budget = budget
    retire_live = budget.reclaimers.get("idle", lambda: None)

    def retire_idle():
        if _pool:
            close_pool(count=1)
        else:
            retire_live()

    budget.reclaimers["idle"] = retire_idle


def _spawn(role="idle"):
    if _budget is not None and not _budget.try_acquire(role):
        return None
    context = get_context("spawn")
    control = context.RawArray("d", [0] * 12)
    connection, child = context.Pipe()
    process = context.Process(target=run_pooled, args=(control, child), daemon=True)
    try:
        process.start()
    except Exception:
        if _budget is not None:
            _budget.abort()
        raise
    finally:
        child.close()
    if _budget is not None:
        _budget.register(process, role)
    return process, connection, control


def _take(role="scene"):
    """Start procesu i importy (ok. 0,2–0,35 s) poza ścieżką wejścia na slajd."""
    while _pool:
        worker = _pool.pop(0)
        if worker[0].is_alive():
            if _budget is not None:
                _budget.waiting.pop(role, None)
            break
        worker[1].close()
        if _budget is not None:
            _budget.release_after_exit(worker[0].pid)
        worker[0].close()
    else:
        worker = _spawn(role)
    while len(_pool) < POOL_SIZE:
        spare = _spawn()
        if spare is None:
            break
        _pool.append(spare)
    return worker


def close_pool(*, count=None) -> None:
    """Zamknięty potok kończy czekający proces puli bez join w UI."""
    for _ in range(len(_pool) if count is None else min(count, len(_pool))):
        process, connection, _ = _pool.pop()
        connection.close()
        if _budget is not None:
            _budget.mark_retiring(process.pid)
        _retiring_pool.append(process)


def process_counts(thumbnails=None) -> dict:
    """Kończący proces zajmuje miejsce aż do exit, nie tylko do żądania stop."""
    counts = {"scene": 0, "preview": 0, "prefetch": 0, "thumbnail": 0, "idle": 0, "retiring": 0}
    for source in list(_sources):
        if source.process is not None and source.process.exitcode is None:
            counts[source.role] += 1
        counts["retiring"] += sum(p.exitcode is None for p in source.retired)
    counts["idle"] = sum(p.exitcode is None for p, _, _ in _pool)
    for process in list(_retiring_pool):
        if process.exitcode is None:
            counts["retiring"] += 1
        else:
            if _budget is not None:
                _budget.release_after_exit(process.pid)
            process.join(0)
            process.close()
            _retiring_pool.remove(process)
    if thumbnails and thumbnails.worker:
        counts["retiring" if thumbnails.cancelled else "thumbnail"] += 1
    counts["total"] = sum(counts.values())
    return counts


class Source:
    """Nieblokujący nadzorca źródła z dwoma slotami RGBA i generacją."""

    def __init__(self):
        _sources.add(self)
        self.role = "scene"
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
        self.control = [0] * 12
        self.waiting_slot = False
        self.budget = _budget

    def prepare(self, entry_id: int, media: dict, *, hold_first: bool = False) -> None:
        """Unieważnij stare wyniki; proces z puli nie wykonuje decode w UI."""
        self.request_close()
        self.generation += 1
        self.entry_id = entry_id
        self.frame, self.last_revision = None, 0
        self.dropped = 0
        self.status, self.error, self.eof = "preparing", None, False
        self.duration = None
        self.started = self.progress = time.monotonic()
        self.media = {**media, "hold_first": hold_first}
        self.hold_first = hold_first
        self.held = False
        self.waiting_slot = True
        self._admit()

    def _admit(self):
        worker = _take(self.role)
        if worker is not None:
            self.process, self.connection, self.control = worker
            if self.budget is not None:
                self.budget.assign(self.process.pid, self.role, self.request_close)
            self.connection.send(self.media)
            self.waiting_slot = False

    def poll(self, now: float, target: float | None, budget_ms: float) -> dict:
        """Kopiuj tylko najnowszy spójny slot, zachowując ostatni dobry obraz."""
        deadline = time.perf_counter() + min(1, max(0, budget_ms)) / 1000
        self.poll_closed(now)
        if self.waiting_slot:
            if now - self.started > 5:
                self.waiting_slot = False
                self.status, self.error = "error", "Przygotowanie przekroczyło 5 s"
            else:
                self._admit()
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
                elif kind == "held":
                    self.held = True
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
            elif (
                self.status != "preparing"
                and not self.hold_first
                and not self.eof
                and now - self.progress > 2
            ):
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

    def adopt(self, entry_id: int, now: float, paused: bool) -> None:
        """Przekaż pierwszy raster bez resetu dekodera; zegar rusza w barierze."""
        self.entry_id = entry_id
        self.generation += 1
        self.hold_first = False
        self.progress = now
        self.control[0] = 2
        self.control[2] = now
        self.control[1] = int(not paused)

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
        self.waiting_slot = False
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            if self.budget is not None:
                self.budget.mark_retiring(self.process.pid)
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
                if self.budget is not None:
                    self.budget.release_after_exit(process.pid)
                process.close()
        self.retired = pending
        return self.process is None and not self.waiting_slot and not pending


class Thumbnails:
    """Jedna ekstrakcja z nieblokującym reap i LRU obejmującym CPU oraz GPU."""

    max_images = 64
    max_bytes = 16 * 1024 * 1024
    working_bytes = 8 * 256 * 144 * 4

    def __init__(self, uploader, retire):
        self.uploader, self.retire = uploader, retire
        self.cache = OrderedDict()
        self.requests = []
        self.revision = None
        self.worker = None
        self.cancelled = False
        self.current = None
        self.idle_since = 0
        self.bytes = 0
        self.budget = _budget

    def configure(self, revision, requests):
        """Nowy deck unieważnia cache; ukrycie anuluje ekstrakcję, bez nowego spawnu."""
        if revision != self.revision:
            self.clear()
            self.revision = revision
        self.requests = list(requests)
        for key, _ in requests:
            self.get(key)

    def cancel(self):
        if self.worker and not self.cancelled:
            self.cancelled = True
            self.current = None
            self.worker[0].terminate()
            if self.budget is not None:
                self.budget.mark_retiring(self.worker[0].pid)

    def clear(self):
        self.cancel()
        for value in self.cache.values():
            if value.get("lease"):
                self.retire(value["lease"])
        self.cache.clear()
        self.bytes = 0
        self.requests = []

    def _evict(self, extra=0):
        while self.cache and (
            len(self.cache) >= self.max_images or self.bytes + extra > self.max_bytes
        ):
            _, value = self.cache.popitem(last=False)
            self.bytes -= value.get("bytes", 0)
            if value.get("lease"):
                self.retire(value["lease"])

    def get(self, key):
        value = self.cache.get(key)
        if value is not None:
            self.cache.move_to_end(key)
        return value

    def poll_thumbnails(self, now: float, *, allow_start=True) -> list[dict]:
        """Publikuj przed exit; tylko zimny start podlega budżetowi ticku."""
        events = []
        value = None
        if self.worker:
            process, connection = self.worker
            if not self.cancelled and self.current:
                key, revision, began = self.current
                try:
                    if connection.poll():
                        value = connection.recv()
                        if "memory" in value:
                            memory = SharedMemory(name=value.pop("memory"))
                            try:
                                value["rgba"] = bytes(
                                    memory.buf[: value["width"] * value["height"] * 4]
                                )
                            finally:
                                memory.close()
                            connection.send("received")
                        elif "error" not in value and "rgba" not in value:
                            raise ValueError("Niepoprawny wynik ekstrakcji")
                    elif now - began > 5:
                        value = {"error": "Timeout ekstrakcji miniatury 5 s"}
                        self.cancel()
                    elif process.exitcode is not None:
                        value = {"error": "Ekstrakcja zakończona bez obrazu"}
                except (EOFError, OSError, ValueError, KeyError) as error:
                    value = {"error": f"Błąd protokołu miniatur: {error}"}
                    self.cancel()
                if value is not None:
                    if revision == self.revision:
                        self._evict()
                        if "rgba" in value:
                            size = len(value["rgba"]) * 2
                            self._evict(size + self.working_bytes)
                            try:
                                lease = self.uploader(value)
                                value = {
                                    **value,
                                    "lease": lease,
                                    "texture": lease.texture,
                                    "bytes": size,
                                }
                            except Exception as error:  # noqa: BLE001 — placeholder zamiast awarii UI
                                value = {"error": str(error)}
                        self.cache[key] = value
                        self.bytes += value.get("bytes", 0)
                        events.append({"index": key, **value})
                    self.current = None
                    self.idle_since = now
            if process.exitcode is not None:
                if self.budget is not None:
                    self.budget.release_after_exit(process.pid)
                process.join(0)
                process.close()
                connection.close()
                self.worker = None
                self.cancelled = False
                self.current = None
            elif self.cancelled or self.current:
                return events
        request = next(((key, spec) for key, spec in self.requests if key not in self.cache), None)
        if request is None:
            if self.worker and now - self.idle_since >= 2:
                self.cancel()
            return events
        if self.worker is None and not allow_start:
            return events
        key, spec = request
        # Małe rastry ekstraktora oraz canvas, resize/crop, SHM i upload playera.
        self.working_bytes = (len(spec["slide"].get("layers", [])) + 8) * 256 * 144 * 4
        self._evict(self.working_bytes)
        if self.working_bytes > self.max_bytes:
            self.cache[key] = {"error": "Kompozycja przekracza budżet miniatur"}
            return events
        if self.worker is None:
            if self.budget is not None and not self.budget.try_acquire("thumbnail"):
                return events
            context = get_context("spawn")
            connection, child = context.Pipe()
            process = context.Process(target=run_thumbnail, args=(child,), daemon=True)
            try:
                process.start()
            except Exception:
                if self.budget is not None:
                    self.budget.abort()
                raise
            finally:
                child.close()
            if self.budget is not None:
                self.budget.register(process, "thumbnail", self.cancel)
            self.worker = process, connection
        self.current = key, self.revision, now
        try:
            self.worker[1].send(spec)
        except (EOFError, OSError):
            self.cache[key] = {"error": "Zerwane połączenie ekstraktora"}
            self.cancel()
        return events
