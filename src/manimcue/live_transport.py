"""Transport live współdzielony przez GL i CE, bez zależności od backendu."""

import logging
import re
import select
import socket
import time
from collections import deque
from urllib.parse import unquote

from manimcue import HOST
from manimcue.live_checkpoint import CheckpointStore, UnsupportedSnapshot

log = logging.getLogger(__name__)
POLL_TIMEOUT = 1 / 60
RECV_SIZE = 4096


class LineBuffer:
    """Bufor bajtów z framingiem po ``b"\\n"``.

    Trzyma bajty, nie tekst: pojedynczy ``recv()`` może rozciąć znak wielobajtowy
    UTF-8, a ``.decode()`` na takim kawałku rzuca wyjątkiem. Dekodujemy dopiero
    kompletną linię.
    """

    def __init__(self) -> None:
        self._data = b""

    def feed(self, chunk: bytes) -> None:
        self._data += chunk
        if any(len(line) > 512 for line in self._data.split(b"\n")):
            raise ValueError("Linia live przekracza 512 bajtów")

    def clear(self) -> None:
        self._data = b""

    def has_line(self) -> bool:
        return b"\n" in self._data

    def pop_line(self) -> str:
        """Zdejmuje pierwszą kompletną linię i dekoduje ją jako UTF-8."""
        line, _, rest = self._data.partition(b"\n")
        self._data = rest
        return line.decode("utf-8", errors="replace").strip()


class LiveTransport:
    """Wspólna pętla i transport obu backendów bez importu Manima ani Qt."""

    def drain_socket(self, timeout: float) -> None:
        """Obsluguje gniazda bez pompowania klatki.

        Rozdzielone z `poll_once`, zeby petla animacji mogla zagladac do gniazda
        bez dorysowywania dodatkowej klatki.
        """
        watch = [self.listener]
        if self.client is not None:
            watch.append(self.client)
        ready, _, _ = select.select(watch, [], [], timeout)
        # Klienta obslugujemy PRZED listenerem. Jesli poprzedni klient rozlaczyl sie
        # w czasie animacji, jego EOF czeka nieodczytany; przyjecie nowego klienta
        # przed odczytaniem tego EOF odrzucilo by go przez martwe juz polaczenie.
        if self.client in ready:
            self.read_client()
        if self.listener in ready:
            self.accept_client()

    def accept_client(self) -> None:
        """Przyjmuje jednego klienta; kolejnych zamyka od razu."""
        conn, addr = self.listener.accept()
        if self.client is not None:
            log.warning(f"Odrzucono dodatkowego klienta {addr}: obslugujemy jednego na raz")
            conn.close()
            return
        conn.setblocking(False)
        self.client = conn
        log.info(f"Klient {addr} podlaczony")

    def read_client(self) -> None:
        """Dociąga bajty; EOF (``b""``) rozłącza klienta, ale nie kończy sceny."""
        try:
            chunk = self.client.recv(RECV_SIZE)
        except OSError:
            chunk = b""
        if chunk:
            self.buffer.feed(chunk)
        else:
            self.drop_client()

    def drop_client(self) -> None:
        """Zamyka gniazdo klienta i zeruje bufor — niekompletna linia jest do wyrzucenia."""
        self.client.close()
        self.client = None
        self.buffer.clear()
        log.info("Klient rozlaczony; scena czeka na nastepnego")

    def close_sockets(self) -> None:
        """Zamyka oba gniazda na każdej ścieżce wyjścia z ``construct()``."""
        for sock in (getattr(self, "client", None), getattr(self, "listener", None)):
            if sock is not None:
                sock.close()
        self.client = None
        self.listener = None

    def advance(self) -> str | None:
        """Nazwa kolejnego cue z sekwencji albo None, gdy sekwencja sie skonczyla."""
        if self.cursor >= len(self.SEQUENCE):
            log.info(f"Koniec sekwencji ({len(self.SEQUENCE)} cue); strzalka w lewo cofa")
            return None
        name = self.SEQUENCE[self.cursor]
        self.cursor += 1
        return name

    def step_back(self) -> None:
        """Cofa ostatnie cue, przywracajac stan mobjectow zapisany przed nim.

        Cofanie jest animowane (`rewind()`), ale sciezka jest interpolacja miedzy
        stanem koncowym i poczatkowym, nie odwroceniem pierwotnej animacji.
        """
        if self.cursor == 0 or not getattr(self, "undo_stack", [True]):
            log.info("Jestes na poczatku sekwencji; nie ma czego cofac")
            return
        self.cursor -= 1
        self.rewind()
        log.info(f"Cofnieto do pozycji {self.cursor}/{len(self.SEQUENCE)}")

    def cue_line(self, name: str, from_sequence: bool) -> str:
        """Linia dla prelegenta: co leci, gdzie jesteśmy, co dalej.

        Pozycje pokazujemy tylko dla cue z sekwencji: preset z gniazda kursora nie
        przesuwa (D2), wiec dopisanie do niego pozycji wprowadzaloby w blad.
        """
        position = self.position_hint() if from_sequence else ""
        loop = "  [petla]" if name in self.LOOPS else ""
        return f"Cue: {name}{position}{loop}"

    def position_hint(self) -> str:
        """Dopisek do logu: pozycja w sekwencji i nazwa nastepnego cue."""
        if self.cursor == 0 or self.cursor > len(self.SEQUENCE):
            return ""
        nxt = self.SEQUENCE[self.cursor] if self.cursor < len(self.SEQUENCE) else "-"
        return f"  [{self.cursor}/{len(self.SEQUENCE)}, nastepne: {nxt}]"

    def live_construct(self) -> None:
        """Pętla headless z barierą odbioru na granicach cue."""
        self.buffer = LineBuffer()
        self.client = None
        self.listener = socket.socket()
        self.listener.bind((HOST, 0))
        self.listener.listen(1)
        self.listener.setblocking(False)
        self.live_bootstrap.send(self.listener.getsockname())
        self.live_commands = deque()
        self.live_step = None
        self.live_step_request = 0
        self.live_step_progress = 0
        self.checkpoints = CheckpointStore(self)
        self.live_reserved = None
        self.live_generation = None
        self.live_request = 0
        self.live_reservation_request = 0
        self.live_boundary_request = "0"
        self.live_entry_counter = 0
        self.live_seen = 0
        self.live_frame_id = 0
        # Runda 10: bariera czeka na ostatnią klatkę graniczną, nie na ostatnią w ogóle —
        # zwykłe klatki (nawigacja D28 w bezczynności) nie są potwierdzane.
        self.live_boundary_id = 0
        self.live_loop = False
        self.live_view_dirty = False
        self.live_outgoing = bytearray()
        self.live_metrics = {name: [0.0, 0] for name in ("render", "readback", "publish")}
        try:
            self.build_objects()
            self.live_publish(boundary=True)
            self.live_status("READY")
            while True:
                self.live_barrier()
                while not self.live_commands:
                    self.live_poll(POLL_TIMEOUT)
                    if self.live_view_dirty:
                        # D28: zmiana widoku w bezczynności to zwykła klatka, bez bariery.
                        self.live_publish()
                command = self.live_commands.popleft()
                if isinstance(command, tuple) and command[0] == "step":
                    self.live_execute_step(*command[1:])
                    continue
                entry = None
                if isinstance(command, tuple):
                    operation, request, checkpoint, *args = command
                    if operation != "enter":
                        self.live_state_operation(operation, request, checkpoint)
                        continue
                    if (
                        checkpoint != self.live_reserved
                        or int(request) < self.live_reservation_request
                        or checkpoint not in self.checkpoints.entries
                    ):
                        self.live_status(f"CHECKPOINT_ERROR {request} {checkpoint} invalid")
                        continue
                    self.live_reserved = None
                    entry = (request, checkpoint, args[0])
                    command = unquote(args[0])
                if command == "back" and entry is None:
                    self.live_cue = "back"
                    self.step_back()
                    self.live_publish(boundary=True)
                    continue
                from_sequence = command == "next" and entry is None
                if from_sequence:
                    command = self.advance()
                    if command is None:
                        self.live_status("SEQUENCE_END")
                        continue
                self.live_cue = command
                if from_sequence:
                    self.save_state()
                self.abort_cue = False
                self.live_loop = command in self.LOOPS
                self.live_status(f"CUE_START {command}")
                if entry:
                    self.live_status(f"ENTRY_CUE_START {entry[0]} {entry[1]} {entry[2]}")
                interrupted = False
                while True:
                    self.PRESETS[command](self)
                    interrupted = interrupted or self.abort_cue
                    self.abort_cue = False
                    self.live_poll(0)
                    if not self.live_loop or self.live_commands:
                        break
                self.live_loop = False
                self.live_publish(boundary=True)
                self.live_bootstrap.send({"metrics": self.live_metrics})
                self.live_status(f"CUE_DONE {command}")
                if interrupted and self.live_reserved is not None:
                    self.live_status(
                        f"CUE_INTERRUPTED {self.live_reservation_request} {self.live_reserved}"
                    )
                if entry:
                    result = "interrupted" if interrupted else "completed"
                    self.live_status(
                        f"ENTRY_CUE_DONE {entry[0]} {entry[1]} {entry[2]} {result} {self.live_frame_id}"
                    )
        finally:
            try:
                self.live_bootstrap.send({"metrics": self.live_metrics})
            finally:
                self.close_sockets()

    def live_status(self, message: str) -> None:
        """Statusy mają framing komend; zapis nie czeka na odbiornik."""
        self.live_outgoing.extend((message + "\n").encode("utf-8"))
        self.live_flush()

    def live_execute_step(self, request, direction):
        """Granica sekwencji jest sprawdzana dopiero po zdjęciu kroku z FIFO."""
        self.live_step = request
        self.abort_cue = False
        self.live_boundary_request = request
        self.live_status(f"STEP_STATUS {request} running")
        result = "done"
        try:
            if direction == "back":
                if self.cursor == 0 or not getattr(self, "undo_stack", [True]):
                    result = "start"
                else:
                    self.live_cue = "back"
                    self.step_back()
            elif self.cursor >= len(self.SEQUENCE):
                result = "end"
            else:
                command = self.advance()
                self.live_cue = command
                self.save_state()
                self.abort_cue = False
                self.live_loop = command in self.LOOPS
                while True:
                    self.PRESETS[command](self)
                    self.abort_cue = False
                    self.live_poll(0)
                    if not self.live_loop or self.live_commands:
                        break
                self.live_loop = False
                self.live_status(f"STEP_STATUS {request} running")
            self.live_publish(boundary=True)
            self.live_status(f"STEP_RESULT {request} {result} {self.live_frame_id}")
        except Exception:
            self.live_status(f"STEP_RESULT {request} error 0")
            raise
        finally:
            self.live_step = None
            self.live_boundary_request = "0"

    def live_step_heartbeat(self):
        """Wywoływane przy postępie animacji, nigdy przez sam transport."""
        request = getattr(self, "live_step", None)
        now = time.monotonic()
        if request is None or now - self.live_step_progress < 1:
            return
        self.live_step_progress = now
        status = "looping" if self.live_loop else "running"
        self.live_status(f"STEP_STATUS {request} {status}")
        for command in self.live_commands:
            if isinstance(command, tuple) and command[0] == "step":
                self.live_status(f"STEP_STATUS {command[1]} waiting")

    def live_flush(self) -> None:
        if self.client is not None and self.live_outgoing:
            try:
                sent = self.client.send(self.live_outgoing)
                del self.live_outgoing[:sent]
            except BlockingIOError:
                pass
            except OSError:
                self.drop_client()

    def live_poll(self, timeout: float) -> None:
        self.drain_socket(timeout)
        while self.buffer.has_line():
            command = self.buffer.pop_line()
            if command == "shutdown":
                raise self.shutdown_exception()
            if command.startswith("frame_seen "):
                try:
                    frame_id = int(command.split()[1])
                    if frame_id == self.live_boundary_id:
                        self.live_seen = frame_id
                        if getattr(self, "live_prefetch", False) and frame_id == 1:
                            self.live_status("PREFETCH_HELD")
                except (ValueError, IndexError):
                    log.warning(f"Niepoprawne potwierdzenie: {command!r}")
            elif getattr(self, "live_prefetch", False) and (
                command.startswith(("view ", "step "))
                or command in ("next", "back")
                or command in self.PRESETS
            ):
                self.live_status("LIVE_RESERVED")
            elif command.startswith("step "):
                fields = command.split()
                valid = (
                    len(fields) == 3
                    and re.fullmatch(r"[1-9][0-9]{0,19}", fields[1])
                    and fields[2] in ("next", "back")
                    and int(fields[1]) > self.live_step_request
                    and self.live_reserved is None
                    and sum(isinstance(c, tuple) and c[0] == "step" for c in self.live_commands)
                    < (1 if self.live_step is not None else 2)
                )
                if valid:
                    self.live_step_request = int(fields[1])
                    self.live_commands.append(tuple(fields))
                    self.live_status(f"STEP_STATUS {fields[1]} waiting")
                elif len(fields) > 1:
                    self.live_status(f"STEP_RESULT {fields[1]} error 0")
            elif command.split(" ")[0] in (
                "checkpoint",
                "restore",
                "enter",
                "drop_checkpoint",
                "release",
                "adopt_prefetch",
            ):
                self.live_queue_operation(command)
            elif command in ("next", "back") or command in self.PRESETS:
                if self.live_reserved is None and len(self.live_commands) < 128:
                    self.live_commands.append(command)
                else:
                    self.live_status("LIVE_RESERVED")
            elif command.startswith("view "):
                if self.live_reserved is None:
                    self.live_view(command)
                else:
                    self.live_status("LIVE_RESERVED")
            else:
                log.warning(f"Nieznana komenda: {command!r}")
        self.live_flush()

    def live_queue_operation(self, command):
        """Walidacja nieznanego cue poprzedza kolejkę i możliwość przerwania."""
        fields = command.split()
        operation = fields[0]
        request, checkpoint = (fields + ["0", "invalid"])[1:3]
        valid = (
            len(fields) == (4 if operation == "enter" else 3)
            and re.fullmatch(r"[1-9][0-9]{0,19}", request)
            and re.fullmatch(r"g[0-9a-f]{1,32}_e[0-9]{1,20}", checkpoint)
            and len(checkpoint) <= 64
        )
        code = "invalid"
        if valid:
            generation = checkpoint.split("_", 1)[0]
            if self.live_generation is not None and generation != self.live_generation:
                code = "stale_generation"
                valid = False
            elif (
                int(request) <= self.live_request
                or len(self.live_commands) >= 128
                or operation == "enter"
                and unquote(fields[3]) not in self.PRESETS
                or operation == "checkpoint"
                and int(checkpoint.rsplit("e", 1)[1]) <= self.live_entry_counter
            ):
                valid = False
        if not valid:
            self.live_status(f"CHECKPOINT_ERROR {request[:20]} {checkpoint[:64]} {code}")
            return
        if operation == "release" and getattr(self, "live_prefetch", False):
            self.live_prefetch = False
        self.live_request = int(request)
        self.live_generation = generation
        if operation == "checkpoint":
            self.live_entry_counter = int(checkpoint.rsplit("e", 1)[1])
        if operation in ("checkpoint", "restore", "adopt_prefetch"):
            self.live_reserved = checkpoint
            self.live_reservation_request = int(request)
            if self.live_loop:
                self.live_status(f"LOOP_WAIT {request} {checkpoint}")
        self.live_commands.append(tuple(fields))

    def live_state_operation(self, operation, request, checkpoint):
        """Każda operacja zaczyna się po ACK poprzedniej granicy."""
        began = time.perf_counter()
        try:
            if operation == "adopt_prefetch":
                if not getattr(self, "live_prefetch", False):
                    raise ValueError("Scena nie jest prefetchem")
                metrics = {}
                status = "PREFETCH_ADOPTED"
            elif operation == "checkpoint":
                self.live_prefetch = False
                metrics = self.checkpoints.checkpoint(checkpoint)
                status = "CHECKPOINT_READY"
            elif operation == "restore":
                self.live_prefetch = False
                if checkpoint not in self.checkpoints.entries:
                    raise KeyError("missing")
                self.live_status(f"RESTORE_START {request} {checkpoint}")
                metrics = self.checkpoints.restore(checkpoint)
                status = "RESTORE_DONE"
            elif operation == "drop_checkpoint":
                self.checkpoints.entries.pop(checkpoint, None)
                self.live_status(f"CHECKPOINT_DROPPED {request} {checkpoint}")
                return
            elif operation == "release":
                if int(request) > self.live_reservation_request:
                    self.checkpoints.protected = checkpoint
                    self.live_reserved = None
                    self.live_prefetch = False
                self.live_status(f"ENTRY_RELEASED {request} {checkpoint}")
                return
            self.live_boundary_request = request
            self.live_publish(boundary=True)
            self.live_boundary_request = "0"
            self.live_status(f"{status} {request} {checkpoint} {self.live_frame_id}")
            self.live_bootstrap.send(
                {
                    "checkpoint_metric": {
                        "operation": operation,
                        "milliseconds": 1000 * (time.perf_counter() - began),
                        "bytes": self.checkpoints.accounted_bytes(),
                        "count": len(self.checkpoints.entries),
                        **metrics,
                    }
                }
            )
        except (KeyError, MemoryError, UnsupportedSnapshot, ValueError) as exc:
            log.warning("Checkpoint %s: %s", operation, exc)
            code = (
                "unsupported"
                if isinstance(exc, UnsupportedSnapshot)
                else (
                    "limit"
                    if isinstance(exc, MemoryError)
                    else "missing"
                    if isinstance(exc, KeyError)
                    else "invalid"
                )
            )
            self.live_status(f"CHECKPOINT_ERROR {request} {checkpoint} {code}")
            if int(request) == self.live_reservation_request:
                self.live_reserved = None
        except Exception:
            self.live_status(f"CHECKPOINT_ERROR {request} {checkpoint} restore_failed")
            raise

    def live_barrier(self) -> None:
        deadline = time.monotonic() + 2
        while self.live_seen < self.live_boundary_id:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Odbiornik nie potwierdził klatki granicznej w 2 s")
            self.live_poll(min(POLL_TIMEOUT, remaining))

    def live_times(self, duration: float):
        """Przeciążenie pomija terminy zamiast nadrabiać klatki."""
        began = time.monotonic()
        target = began
        last = 0.0
        while True:
            # Tempo trzyma sleep, nie select: select na Windows zaokrągla timeout w górę do
            # ~15,6 ms (16 ms czeka 31 ms — zmierzone), co dawało ~29 fps zamiast 60. sleep ma
            # od Pythona 3.11 timer wysokiej rozdzielczości. Komenda czeka najwyżej klatkę.
            remaining = target - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            self.live_poll(0)
            now = time.monotonic()
            if now < target:
                continue
            if self.abort_cue or (self.live_commands and not self.live_loop):
                self.abort_cue = True
                return
            elapsed = min(duration, now - began)
            yield elapsed, elapsed - last
            LiveTransport.live_step_heartbeat(self)
            last = elapsed
            if elapsed >= duration:
                return
            fps = getattr(self.camera, "fps", getattr(self.camera, "frame_rate", 60))
            step = int((time.monotonic() - began) * fps) + 1
            target = min(began + duration, began + step / fps)
