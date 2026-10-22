"""Warstwy live w playerze (F4, D20, D27): sesje bieżącego slajdu, klatki do kompozycji, fokus.

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
from manimcue.live_session import LiveSession, LiveSpec
from manimcue.slides.config import Keys, SlideConfig
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

    error = Signal(str)
    """Treść `ERROR` sesji bieżącego slajdu — player pokazuje ją w oknie Info."""

    def __init__(self, composition: SlideComposition) -> None:
        super().__init__()
        self.composition = composition
        self.key: object = None
        self.sessions: list[LiveSession] = []
        self.started: list[float] = []
        self.stopping: list[LiveSession] = []
        self.active: int | None = None
        self.failed: set[int] = set()
        self.closing = False
        self.drag_from: QPointF | None = None
        self.border = QGraphicsRectItem()
        self.border.setZValue(BORDER_Z)
        self.border.hide()
        composition.addItem(self.border)
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.tick)

    def show(self, key: object, slide: SlideConfig, resolution: tuple[int, int]) -> None:
        """Sesje dla warstw slajdu wskazanego kluczem (prezentacja, indeks).

        Ten sam klucz (replay, pętla, reverse → normalny kierunek) zostawia sesje. Reverse
        dotyczy tylko klipu bazowego: wejście na slajd, także od tyłu, startuje live od początku.
        """
        if key == self.key or self.closing:
            return
        # Bez release(): ta odtworzyłaby obwódkę błędu starego slajdu, indeksując już nowe
        # prostokąty warstw (runda 10, p. 4).
        self.active = None
        self.drag_from = None
        self.failed = set()
        self.border.hide()
        self.retire()
        self.key = key
        for layer in slide.layers:
            width, height = layer.size(resolution)
            session = LiveSession()
            session.start(
                LiveSpec(
                    str(Path(layer.scene_file).resolve()),
                    layer.scene_name,
                    width,
                    height,
                    layer.fps,
                )
            )
            self.sessions.append(session)
            self.started.append(time.monotonic())
        self.update_timer()

    def retire(self) -> None:
        """Sesje bieżącego slajdu przechodzą do odbioru; od tej chwili nie dotykają kompozycji."""
        for session in self.sessions:
            session.request_stop()
        self.stopping += self.sessions
        self.sessions = []
        self.started = []

    def tick(self) -> None:
        now = time.monotonic()
        # Najpierw statusy wszystkich sesji, potem kosztowne obrazy (runda 9, p. 9).
        for index, session in enumerate(self.sessions):
            for event in session.poll():
                if event.startswith("ERROR"):
                    self.fail(index, event)
            if session.state == "starting" and now - self.started[index] > START_TIMEOUT:
                self.fail(index, f"ERROR start: brak READY po {START_TIMEOUT:.0f} s")
                session.request_stop()
        for index, session in enumerate(self.sessions):
            frame = session.try_read_frame()
            if frame is not None:
                # Bajty żyją w `frame` do powrotu z set_layer_image (QPixmap.fromImage).
                image = QImage(
                    frame.pixels,
                    frame.width,
                    frame.height,
                    frame.width * 4,
                    QImage.Format.Format_RGBA8888,
                )
                self.composition.set_layer_image(index, image)
        for session in list(self.stopping):
            session.poll()
            if not session.running:
                self.stopping.remove(session)
        self.update_timer()

    def update_timer(self) -> None:
        busy = self.stopping or any(session.running for session in self.sessions)
        if busy and not self.timer.isActive():
            self.timer.start(POLL_MS)
        elif not busy and self.timer.isActive():
            self.timer.stop()

    def fail(self, index: int, event: str) -> None:
        if index in self.failed:
            return
        logger.error(f"Warstwa live {index + 1}: {event}")
        self.failed.add(index)
        if self.active == index:
            self.active = None
        self.frame_layer(index, ERROR_COLOR)
        self.error.emit(event)

    def click(self, index: int) -> None:
        """Klik w widoku głównym: warstwa (indeks) dostaje klawisze, -1 je zwalnia."""
        self.drag_from = None
        if index < 0 or index >= len(self.sessions) or index in self.failed:
            self.release()
            return
        self.active = index
        self.frame_layer(index, ACTIVE_COLOR)

    def drag(self, point: QPointF, shift: bool) -> None:
        """Przeciąganie po aktywnej warstwie (D28): obrót kamery, z Shiftem przesunięcie."""
        if self.active is None:
            return
        if self.drag_from is not None:
            rect = self.composition.layer_rects[self.active]
            dx = (point.x() - self.drag_from.x()) / rect.width()
            dy = (point.y() - self.drag_from.y()) / rect.height()
            self.send(f"view {'pan' if shift else 'orbit'} {dx:.5f} {dy:.5f}")
        self.drag_from = point

    def end_drag(self) -> None:
        self.drag_from = None

    def wheel(self, steps: float) -> None:
        if self.active is not None and steps:
            self.send(f"view zoom {steps:g}")

    def double_click(self, index: int) -> None:
        if index >= 0 and index == self.active:
            self.send("view reset")

    def release(self) -> None:
        if self.active is None:
            return
        self.active = None
        self.border.hide()
        # Obwódka jest jedna; po zwolnieniu wraca na pierwszą warstwę z błędem, jeśli jest.
        if self.failed:
            self.frame_layer(min(self.failed), ERROR_COLOR)

    def frame_layer(self, index: int, color: QColor) -> None:
        pen = QPen(color, BORDER_WIDTH)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self.border.setPen(pen)
        # Wewnątrz prostokąta warstwy: przy rect na krawędzi kadru nie wyjdzie poza niego.
        half = BORDER_WIDTH / 2
        self.border.setRect(self.composition.layer_rects[index].adjusted(half, half, -half, -half))
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
        if session.state == "ready" and not repeat:
            session.send(command)

    def begin_shutdown(self) -> None:
        """Zamykanie playera: zatrzymanie bez blokowania GUI, odbiór dalej przez timer."""
        self.closing = True
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
        while self.stopping and time.monotonic() < deadline:
            for session in list(self.stopping):
                session.poll()
                if not session.running:
                    self.stopping.remove(session)
            time.sleep(0.01)
        self.timer.stop()
