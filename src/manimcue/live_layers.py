"""Warstwy live w playerze (D20, D27, D33): ciągi sesji, obraz, cue wejścia i fokus.

Kompozycja nie zna `LiveSession` (runda 8, p. 12) — kontroler przenosi klatki do
`SlideComposition.set_layer_image`. Jeden `QTimer` pompuje sesje bieżącego slajdu i te
zatrzymywane, aż proces zostanie odebrany; bez sesji timer stoi. Sesje zatrzymywane są
pompowane tylko do odebrania procesu — ich klatki i błędy nie dotykają bieżącego slajdu.
"""

import time
from pathlib import Path

from qtpy.QtCore import QObject, QPointF, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QImage, QKeyEvent, QPen
from qtpy.QtWidgets import QGraphicsRectItem

from manimcue.composition import SlideComposition
from manimcue.live_entry import EntryHistory
from manimcue.live_pool import LivePool, ProcessBudget
from manimcue.live_session import LiveSession, LiveSpec
from manimcue.player.input import gesture_mode
from manimcue.slides.config import Keys, LiveLayer, SlideConfig
from manimcue.slides.logger import logger

POLL_MS = 4
"""Okres timera: poniżej klatki 60 fps, żeby odbiór nie dokładał opóźnienia."""

START_TIMEOUT = 60.0
"""Brak READY po tym czasie to błąd warstwy (zawieszone `build_objects`)."""

ACTIVE_COLOR = QColor(255, 200, 0)
ERROR_COLOR = QColor(220, 40, 40)
BORDER_WIDTH = 6
BORDER_Z = 1000


class LiveLayerController(QObject):
    """Właściciel sesji warstw live bieżącego slajdu i stanu aktywnej warstwy."""

    changed = Signal()
    observed = Signal(str)
    frame_received = Signal(int, object, float)
    cue_sent = Signal(int, str, float)
    error = Signal(str)
    """Treść `ERROR` sesji bieżącego slajdu — player pokazuje ją w oknie Info."""

    def __init__(self, composition: SlideComposition) -> None:
        super().__init__()
        self.pool = LivePool(ProcessBudget(64))
        self.pool_error_count = 0
        self.composition = composition
        self.key: object = None
        # Bieżące mapowanie kompozycji; tożsamość procesu i cache przechodzą między indeksami.
        self.sessions: dict[int, LiveSession] = {}
        self.started: dict[int, float] = {}
        self.stopping: list[LiveSession] = []
        self.identities: dict[int, tuple] = {}
        self.images: dict[LiveSession, QImage] = {}
        self.last_frames: dict[LiveSession, object] = {}
        self.entry_cues: dict[int, str] = {}
        self.histories: dict[LiveSession, EntryHistory] = {}
        self.restore_images: dict[LiveSession, tuple] = {}
        self.active: int | None = None
        self.failed: set[int] = set()
        self.closing = False
        self.drag_from: QPointF | None = None
        self.gesture_allowed = False
        self.drag_mode = None
        self.framed: int | None = None
        composition.layer_moved.connect(self.follow_layer)
        self.border = QGraphicsRectItem()
        self.border.setZValue(BORDER_Z)
        self.border.hide()
        composition.addItem(self.border)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)

    def show(
        self, key: object, slide: SlideConfig, resolution: tuple[int, int], reason: str = "initial"
    ) -> None:
        """Przejmuje tylko żywe sesje z sąsiedniego slajdu tej samej prezentacji."""
        if self.closing:
            return
        self.entry_cues = {}
        if key == self.key:
            for index, session in self.sessions.items():
                if session in self.images:
                    self.composition.set_layer_image(index, self.images[session])
            if reason == "replay":
                for index, session in self.sessions.items():
                    if session in self.histories:
                        self.remember_image(session)
                        cue = self.histories[session].prepare(
                            key, slide.layers[index].enter_cue, reason, time.monotonic()
                        )
                        if cue:
                            self.entry_cues[index] = cue
            return
        adjacent = (
            isinstance(key, tuple)
            and isinstance(self.key, tuple)
            and key[0] == self.key[0]
            and abs(key[1] - self.key[1]) == 1
        )
        old = self.sessions
        old_started = self.started
        old_identities = self.identities
        self.active = None
        self.drag_from = None
        self.gesture_allowed = False
        self.failed = set()
        self.border.hide()
        self.sessions, self.started, self.identities = {}, {}, {}
        self.layers = slide.layers
        self.key = key
        for index, layer in enumerate(slide.layers):
            if not isinstance(layer, LiveLayer):
                continue
            width, height = layer.size(resolution)
            identity = (
                layer.session_id,
                Path(layer.scene_file).resolve(),
                layer.scene_name,
                layer.fps,
                width,
                height,
                layer.background_opacity,
                layer.engine,
            )
            reused = next(
                (
                    i
                    for i, session in old.items()
                    if adjacent
                    and layer.session_id is not None
                    and old_identities[i] == identity
                    and session.state in ("starting", "ready")
                    and not session.stopping
                ),
                None,
            )
            if reused is not None:
                session = old.pop(reused)
                self.started[index] = old_started[reused]
            else:
                session = LiveSession()
                session.start(
                    LiveSpec(
                        str(identity[1]),
                        layer.scene_name,
                        width,
                        height,
                        layer.fps,
                        layer.background_opacity,
                        layer.engine,
                    ),
                    pool=self.pool,
                )
                self.started[index] = time.monotonic()
            self.sessions[index] = session
            self.identities[index] = identity
            if layer.session_id is not None:
                history = self.histories.setdefault(session, EntryHistory())
                self.remember_image(session)
                cue = history.prepare(key, layer.enter_cue, reason, time.monotonic())
                if cue:
                    self.entry_cues[index] = cue
            if session in self.images:
                self.composition.set_layer_image(index, self.images[session])
            if (
                layer.session_id is None
                and reason in ("next", "auto_next", "skip_all")
                and layer.enter_cue is not None
            ):
                self.entry_cues[index] = layer.enter_cue
        for session in old.values():
            session.request_stop()
            self.stopping.append(session)
            self.images.pop(session, None)
            self.last_frames.pop(session, None)
            self.histories.pop(session, None)
            self.restore_images.pop(session, None)
        self.update_timer()

    def waiting_for_entry(self) -> bool:
        """READY jest trwałe; trwające cue zostanie przerwane zgodnie z D10."""
        return any(
            self.sessions[i].state in ("waiting_slot", "starting") for i in self.entry_cues
        ) or any(history.waiting for history in self.histories.values())

    def has_preparation(self) -> bool:
        return bool(self.entry_cues) or any(h.reserved for h in self.histories.values())

    def cancel_unready_entries(self) -> None:
        """Timeout bariery usuwa tylko cue, nigdy player klipu."""
        self.entry_cues = {
            i: cue for i, cue in self.entry_cues.items() if self.sessions[i].state == "ready"
        }
        for session, history in self.histories.items():
            if history.waiting:
                history.expected = None
                history.reserved = False
                history.degraded = "stan live nieprzywrócony: timeout, cue niewysłane"
                session.request_stop()
        self.entry_cues = {
            i: cue for i, cue in self.entry_cues.items() if not self.sessions[i].stopping
        }

    def start_entries(self) -> None:
        """Jednorazowa wysyłka przy faktycznym starcie grupy, bez przejęcia fokusu."""
        cues, self.entry_cues = self.entry_cues, {}
        for index, session in self.sessions.items():
            history = self.histories.get(session)
            if (
                history
                and history.reserved
                and not history.waiting
                and history.pending_start is None
            ):
                checkpoint = history.stack[-1].checkpoint or history.reservation_checkpoint
                if index in cues and not history.degraded:
                    request = history.command("enter", checkpoint, cues[index])
                    history.stack[-1].cue_state = "sent"
                    history.stack[-1].cue_request = request
                    history.status = f"wysłano cue {cues[index]}"
                    self.cue_sent.emit(index, cues[index], time.perf_counter())
                else:
                    request = history.command("release", checkpoint)
                history.pending_start = (request, checkpoint)
                self.flush_history(session, history)
        for index, cue in cues.items():
            session = self.sessions[index]
            if session not in self.histories and session.state == "ready" and not session.stopping:
                session.send(cue)
                self.cue_sent.emit(index, cue, time.perf_counter())

    def retire(self) -> None:
        """Sesje bieżącego slajdu przechodzą do odbioru; od tej chwili nie dotykają kompozycji."""
        for session in self.sessions.values():
            session.request_stop()
        self.stopping += self.sessions.values()
        self.sessions = {}
        self.started = {}
        self.images = {}
        self.last_frames = {}
        self.entry_cues = {}
        self.histories = {}
        self.restore_images = {}

    def remember_image(self, session):
        if session in self.images:
            self.restore_images[session] = (self.images[session], self.last_frames[session])

    def flush_history(self, session, history):
        if session.state == "ready" and not session.stopping:
            outgoing, history.outgoing = history.outgoing, []
            for command in outgoing:
                session.send(command)

    def tick(self) -> None:
        now = time.monotonic()
        self.pool.poll(now)
        for message in self.pool.errors[self.pool_error_count :]:
            self.error.emit(message)
        self.pool_error_count = len(self.pool.errors)
        # Najpierw statusy wszystkich sesji, potem kosztowne obrazy (runda 9, p. 9).
        for index, session in self.sessions.items():
            history = self.histories.get(session)
            for event in session.poll():
                if history:
                    history.accept(event)
                    if history.degraded:
                        self.entry_cues.pop(index, None)
                        if session in self.restore_images:
                            self.images[session], self.last_frames[session] = self.restore_images[
                                session
                            ]
                            self.composition.set_layer_image(index, self.images[session])
                notify = not (history and (history.reserved or history.degraded))
                if event.startswith("CUE_START ") and notify:
                    self.observed.emit(f"live {index + 1}: start cue {event[10:]}")
                elif event.startswith("CUE_DONE ") and notify:
                    self.observed.emit(f"live {index + 1}: koniec cue {event[9:]}")
                elif event == "SEQUENCE_END" and notify:
                    self.observed.emit(f"live {index + 1}: koniec sekwencji")
                if event.startswith("ERROR"):
                    self.fail(index, event)
            if (
                session.state in ("waiting_slot", "starting")
                and now - self.started[index] > START_TIMEOUT
            ):
                self.fail(index, f"ERROR start: brak READY po {START_TIMEOUT:.0f} s")
                session.request_stop()
            if history:
                if history.waiting and now >= history.deadline:
                    history.expected = None
                    history.reserved = False
                    history.degraded = "stan live nieprzywrócony: timeout, wynik nieznany"
                    self.entry_cues.pop(index, None)
                    session.request_stop()
                self.flush_history(session, history)
        for index, session in self.sessions.items():
            history = self.histories.get(session)
            frame = session.try_read_frame(acknowledge=False)
            if history:
                if frame is not None:
                    history.held = frame
                frame = history.held
                if (
                    frame is not None
                    and frame.boundary
                    and frame.frame_id not in history.boundaries
                ):
                    continue
                history.held = None
            display = frame is not None and not session.stopping
            if frame is not None and history:
                request = (
                    history.boundaries.pop(frame.frame_id, None)
                    if frame.boundary
                    else history.started_restore
                )
                if history.waiting:
                    display = (
                        display
                        and history.operation_valid
                        and (
                            history.expected[0] == request
                            or (frame.frame_id == 1 and session not in self.images)
                        )
                    )
                elif history.degraded:
                    display = False
            if frame is not None:
                # Bajty żyją w `frame`, a `last_frames` trzyma go do następnej klatki — obraz
                # sesji bez kopii 5 MB na klatkę w wątku GUI.
                image = QImage(
                    frame.pixels,
                    frame.width,
                    frame.height,
                    frame.width * 4,
                    QImage.Format.Format_RGBA8888,
                )
                if display:
                    self.images[session] = image
                    self.last_frames[session] = frame
                    self.composition.set_layer_image(index, image)
                    self.frame_received.emit(index, frame, time.perf_counter())
                if frame.boundary:
                    session.send(f"frame_seen {frame.frame_id}")
                    if history and history.expected and request == history.expected[0]:
                        history.received.add(frame.frame_id)
            if history:
                history.finish()
        for session in list(self.stopping):
            session.poll()
            if not session.running:
                self.stopping.remove(session)
        self.changed.emit()
        self.update_timer()

    def update_timer(self) -> None:
        busy = (
            (not self.closing or not self.pool.closed)
            or self.stopping
            or any(session.running for session in self.sessions.values())
        )
        if busy and not self.timer.isActive():
            self.timer.start(POLL_MS)
        elif not busy and self.timer.isActive():
            self.timer.stop()

    def fail(self, index: int, event: str) -> None:
        if index in self.failed:
            return
        logger.error(f"Warstwa live {index + 1}: {event}")
        self.failed.add(index)
        session = self.sessions[index]
        if session in self.histories:
            history = self.histories[session]
            history.degraded = (
                history.degraded or f"stan live nieprzywrócony: {event}; wynik nieznany"
            )
            history.expected = None
            history.reserved = False
            self.entry_cues.pop(index, None)
            if session in self.restore_images:
                self.images[session], self.last_frames[session] = self.restore_images[session]
                self.composition.set_layer_image(index, self.images[session])
        if self.active == index:
            self.active = None
        if self.active is None:
            self.frame_layer(min(self.failed), "error")
        self.error.emit(event)

    def click(self, index: int) -> None:
        """Klik w widoku głównym: warstwa (indeks) dostaje klawisze, -1 je zwalnia."""
        self.drag_from = None
        self.drag_mode = None
        self.gesture_allowed = self.active == index
        if index not in self.sessions or index in self.failed:
            self.release()
            return
        self.active = index
        self.frame_layer(index, "active")
        self.changed.emit()

    def drag(self, point: QPointF, shift: bool, button: str = "middle", alt: bool = False) -> None:
        """Capture od press nad aktywnym kontenerem, bez delty na pierwszym kliknięciu."""
        if self.active is None or not self.gesture_allowed:
            return
        session = self.sessions[self.active]
        history = self.histories.get(session)
        rect = self.composition.layer_rects[self.active]
        mode = gesture_mode(button, shift, alt)
        if (
            (history and history.reserved)
            or mode is None
            or rect.width() <= 0
            or rect.height() <= 0
        ):
            self.end_drag()
            return
        if self.drag_from is None:
            if not rect.contains(point):
                self.end_drag()
                return
            self.drag_mode = mode
        if self.drag_from is not None:
            dx = (point.x() - self.drag_from.x()) / rect.width()
            dy = (point.y() - self.drag_from.y()) / rect.height()
            if dx == 0 and dy == 0:
                return
            if self.drag_mode == "zoom":
                self.send(f"view zoom {-20 * dy:g}")
            else:
                self.send(f"view {self.drag_mode} {dx:.5f} {dy:.5f}")
        self.drag_from = point

    def end_drag(self) -> None:
        self.drag_from = None
        self.drag_mode = None
        self.gesture_allowed = False

    def wheel(self, steps: float, index: int | None = None) -> None:
        if self.active is not None and steps and (index is None or index == self.active):
            rect = self.composition.layer_rects[self.active]
            if rect.width() <= 0 or rect.height() <= 0:
                return
            self.send(f"view zoom {steps:g}")

    def double_click(self, index: int) -> None:
        if index >= 0 and index == self.active:
            self.send("view reset")

    def release(self) -> None:
        self.end_drag()
        if self.active is None:
            return
        self.active = None
        self.border.hide()
        # Obwódka jest jedna; po zwolnieniu wraca na pierwszą warstwę z błędem, jeśli jest.
        if self.failed:
            self.frame_layer(min(self.failed), "error")
        self.changed.emit()

    def follow_layer(self, index: int) -> None:
        """Obwódka jedzie z warstwą w ruchu (runda 12, p. 5)."""
        if index == self.framed and self.border.isVisible():
            self.frame_layer(index, self.border_role)

    def frame_layer(self, index: int, role: str) -> None:
        self.framed = index
        self.border_role = role
        style = getattr(self.layers[index], f"{role}_border")
        self.border.hide()
        if style is None:
            return
        r, g, b, a = style.color.as_rgb_tuple(alpha=True)
        color = QColor(r, g, b)
        color.setAlphaF(a * style.opacity)
        rect = self.composition.layer_rects[index]
        width = min(style.width, rect.width(), rect.height())
        pen = QPen(color, width)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self.border.setPen(pen)
        half = width / 2
        self.border.setRect(rect.adjusted(half, half, -half, -half))
        self.border.show()

    def handle_key(self, event: QKeyEvent, keys: Keys) -> bool:
        """Router przed `dispatch` (D20): True, gdy klawisz należał do aktywnej warstwy.

        Kody dopasowane jak w `dispatch` (bez modyfikatorów). Autorepeat strzałek jest
        konsumowany bez wysyłania: przytrzymany klawisz przerywałby kolejne cue (D10).
        """
        if self.active is None:
            return False
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.release()
        elif key in keys.NEXT.ids:
            self.send("next", event.isAutoRepeat())
        elif key in keys.PREVIOUS.ids:
            self.send("back", event.isAutoRepeat())
        else:
            return False
        return True

    def send(self, command: str, repeat: bool = False) -> None:
        # Tylko do gotowej sceny: klik i strzałka w trakcie startu nie kolejkują cue po READY.
        session = self.sessions[self.active]
        history = self.histories.get(session)
        if history and history.reserved:
            self.end_drag()
            self.observed.emit("live: przygotowanie zarezerwowane, komenda ręczna pominięta")
            return
        if command.startswith("view ") and self.identities[self.active][-1] == "ce-cairo":
            return
        if session.state == "ready" and not repeat:
            session.send(command)

    def begin_shutdown(self) -> None:
        """Zamykanie playera: zatrzymanie bez blokowania GUI, odbiór dalej przez timer."""
        self.closing = True
        self.pool.begin_shutdown()
        self.active = None
        self.drag_from = None
        self.failed = set()
        self.border.hide()
        self.retire()
        self.key = None
        self.update_timer()

    def shutdown(self, timeout: float = 3.0) -> None:
        """Końcowy odbiór procesów po wyjściu z pętli Qt (D27) — tu timer już nie tyka.

        Blokuje najwyżej `timeout`; `LiveSession` zabija proces po 2 s od `request_stop()`.
        """
        self.begin_shutdown()
        deadline = time.monotonic() + timeout
        while (self.stopping or not self.pool.closed) and time.monotonic() < deadline:
            self.pool.poll(time.monotonic())
            for session in list(self.stopping):
                session.poll()
                if not session.running:
                    self.stopping.remove(session)
            time.sleep(0.01)
        self.timer.stop()
