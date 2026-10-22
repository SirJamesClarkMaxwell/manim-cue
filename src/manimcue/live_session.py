"""Nieblokujący właściciel procesu live i jego zasobów IPC."""

import errno
import multiprocessing as mp
import socket
import time
from dataclasses import dataclass
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path

from manimcue.frame_buffer import FrameBuffer, OwnedFrame, buffer_size
from manimcue.live_worker import run_worker

__all__ = ["LiveSession", "LiveSpec", "OwnedFrame", "capture_first_frame"]


@dataclass(frozen=True)
class LiveSpec:
    scene_file: str
    scene_name: str
    width: int = 960
    height: int = 540
    fps: int = 60
    background_opacity: float = 1.0


class LiveSession:
    """Metody wywoływane z timera GUI; zatrzymanie kończy dopiero poll()."""

    state: str
    error: str | None

    def __init__(self):
        self.state = "idle"
        self.error = None
        self._process = None
        self._shm = None
        self._socket = None
        self._pipe = None
        self._outgoing = bytearray()
        self._incoming = bytearray()
        self._stop_at = None
        self._events = []
        self._metrics = {}

    def start(self, spec: LiveSpec) -> None:
        if self._process is not None:
            raise RuntimeError("Poprzedni proces nie został odebrany przez poll()")
        if not Path(spec.scene_file).is_absolute() or spec.fps <= 0:
            raise ValueError("Wymagana absolutna ścieżka sceny i dodatni fps")
        size = buffer_size(spec.width, spec.height)
        self.__init__()
        ctx = mp.get_context("spawn")
        self._shm = SharedMemory(create=True, size=size)
        self._frame_lock = ctx.Lock()
        self._buffer = FrameBuffer(self._shm, self._frame_lock, spec.width, spec.height)
        self._pipe, sender = ctx.Pipe(duplex=False)
        self._process = ctx.Process(
            target=run_worker, args=(spec, self._shm.name, self._frame_lock, sender)
        )
        self.state = "starting"
        try:
            self._process.start()
        except Exception:
            self._cleanup()
            self._process = None
            raise
        finally:
            sender.close()

    def _event(self, event):
        if event == "READY" and self.state != "error":
            self.state = "ready"
        elif event.startswith("ERROR"):
            self.state = "error"
            if self.error is None or self.error.startswith("transport:"):
                self.error = event.removeprefix("ERROR ")
            self.request_stop()
        self._events.append(event)

    def _poll_bootstrap(self) -> None:
        if self._pipe is not None:
            try:
                while self._pipe.poll(0):
                    message = self._pipe.recv()
                    if isinstance(message, dict):
                        self._metrics = message["metrics"]
                    elif isinstance(message, tuple):
                        self._socket = socket.socket()
                        self._socket.setblocking(False)
                        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        code = self._socket.connect_ex(message)
                        if code not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK, 10035):
                            raise OSError(code, "Połączenie z workerem")
                    else:
                        self._event(message)
            except (EOFError, BrokenPipeError):
                self._pipe.close()
                self._pipe = None
            except OSError as exc:
                self._event(f"ERROR bootstrap: {exc}")
                self._pipe.close()
                self._pipe = None

    def poll(self) -> list[str]:
        self._poll_bootstrap()
        if self._socket is not None:
            try:
                if self._outgoing:
                    sent = self._socket.send(self._outgoing)
                    del self._outgoing[:sent]
                while True:
                    chunk = self._socket.recv(65536)
                    if not chunk:
                        self._socket.close()
                        self._socket = None
                        break
                    self._incoming.extend(chunk)
                    while b"\n" in self._incoming:
                        line, _, rest = self._incoming.partition(b"\n")
                        self._incoming = bytearray(rest)
                        self._event(line.decode("utf-8", errors="replace"))
            except BlockingIOError:
                pass
            except OSError as exc:
                # Windows zgłasza WSAENOTCONN podczas nieblokującego connect_ex.
                if getattr(exc, "winerror", 0) != 10057:
                    self._socket.close()
                    self._socket = None
                    if self.state != "error" and self._stop_at is None:
                        self._event(f"ERROR transport: {exc}")
        if self._process is not None:
            if (
                self._stop_at is not None
                and time.monotonic() >= self._stop_at
                and self._process.is_alive()
            ):
                self._process.kill()
            if self._process.exitcode is not None:
                # Po exit code ostatnia diagnoza musi być odebrana przed zamknięciem IPC.
                self._poll_bootstrap()
                self._process.join(0)
                if self.state != "error":
                    if self._stop_at is None:
                        self._event(f"ERROR Proces live zakończony: {self._process.exitcode}")
                    else:
                        self.state = "stopped"
                self._cleanup()
                self._process.close()
                self._process = None
                self._events.append("STOPPED")
        events, self._events = self._events, []
        return events

    def send(self, command: str) -> None:
        if "\n" in command or "\r" in command:
            raise ValueError("Komenda musi zajmować jedną linię")
        if self._process is not None:
            self._outgoing.extend((command + "\n").encode("utf-8"))

    def try_read_frame(self) -> OwnedFrame | None:
        if self._shm is None:
            return None
        try:
            frame = self._buffer.try_read()
        except ValueError as exc:
            self._event(f"ERROR {exc}")
            return None
        if frame is not None and frame.boundary:
            self.send(f"frame_seen {frame.frame_id}")
        return frame

    def request_stop(self) -> None:
        if self._process is not None and self._stop_at is None:
            self._stop_at = time.monotonic() + 2
            self.send("shutdown")

    @property
    def stopping(self) -> bool:
        """Żądanie zatrzymania wyklucza przejęcie nawet przed zmianą stanu."""
        return self._stop_at is not None

    @property
    def running(self) -> bool:
        """Proces jeszcze nieodebrany przez poll()."""
        return self._process is not None

    def _cleanup(self):
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        if self._pipe is not None:
            self._pipe.close()
            self._pipe = None
        if self._shm is not None:
            self._shm.close()
            self._shm.unlink()
            self._shm = None


def capture_first_frame(spec: LiveSpec, timeout: float = 120.0) -> OwnedFrame:
    """Pierwsza klatka sceny po READY — miniatura warstwy live w renderze (F3).

    Blokuje do READY albo błędu, więc nie dla GUI. Proces zawsze jest odbierany przed powrotem.
    """
    session = LiveSession()
    session.start(spec)
    deadline = time.monotonic() + timeout
    ready = False
    frame = None
    try:
        while not (ready and frame is not None):
            ready = "READY" in session.poll() or ready
            if session.state == "error":
                raise RuntimeError(f"Scena live {spec.scene_name}: {session.error}")
            if not session.running:
                raise RuntimeError(
                    f"Scena live {spec.scene_name}: proces zakończył się przed READY"
                )
            frame = session.try_read_frame() or frame
            if time.monotonic() > deadline:
                raise TimeoutError(f"Scena live {spec.scene_name}: brak READY po {timeout} s")
            time.sleep(0.005)
        return frame
    finally:
        session.request_stop()
        while session.running:
            session.poll()
            time.sleep(0.01)
