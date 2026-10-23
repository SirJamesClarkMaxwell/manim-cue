"""Faza 4: warstwa live w playerze — sesje, fokus, router klawiszy, nawigacja widoku (D20, D28).

Player offscreen z prawdziwym procesem GL (`gpu`); sceny z korpusu F2.
"""

import multiprocessing as mp
import time
from pathlib import Path

import pytest
import test_imgui_input as input_fixtures
from PIL import Image

from manimcue.slides.config import LiveLayer, PresentationConfig, SlideConfig, SlideType

qt_gestures = input_fixtures.qt_gestures

LIVE_FILE = Path(__file__).parent / "scenes" / "live_gl.py"
RESOLUTION = (640, 360)
RECT = (0.5, 0.0, 0.5, 0.5)
MAGENTA = (255, 0, 255)
READY_TIMEOUT = 30.0


def png(path: Path, color, size=RESOLUTION) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def deck(tmp_path: Path, layers: list[tuple[str, tuple]]) -> PresentationConfig:
    """Trzy slajdy-obrazy; środkowy ma warstwy (scena, rect) z magentową miniaturą."""
    base = png(tmp_path / "base.png", (0, 0, 60))
    thumbnail = png(tmp_path / "thumb.png", MAGENTA, (32, 18))
    live_layers = [
        LiveLayer(scene_file=LIVE_FILE, scene_name=scene, rect=rect, thumbnail=thumbnail)
        for scene, rect in layers
    ]
    plain = SlideConfig(file=base, rev_file=base, type=SlideType.Image)
    live = SlideConfig(file=base, rev_file=base, type=SlideType.Image, layers=live_layers)
    return PresentationConfig(slides=[plain, live, plain.model_copy()], resolution=RESOLUTION)


@pytest.fixture
def qapp():
    from manimcue.slides.qt_utils import qapp

    return qapp()


@pytest.fixture
def player_for(qapp, tmp_path):
    """Fabryka playera na slajdzie z warstwą; po teście wszystkie procesy odebrane."""
    from qtpy.QtCore import Qt

    from manimcue.slides.config import Config
    from manimcue.slides.present.player import Player

    players = []

    def make(scene: str, rect=RECT, extra: tuple = ()):
        player = Player(
            Config(),
            [deck(tmp_path, [(scene, rect), *extra])],
            slide_index=1,
            aspect_ratio_mode=Qt.AspectRatioMode.KeepAspectRatio,
        )
        player.resize(*RESOLUTION)
        super(Player, player).show()
        players.append(player)
        return player

    yield make
    for player in players:
        player.live.shutdown()
        player.info.close()
    assert mp.active_children() == []


def pump(qapp, until, timeout: float = READY_TIMEOUT, what: str = "") -> None:
    deadline = time.monotonic() + timeout
    while not until():
        if time.monotonic() > deadline:
            pytest.fail(f"timeout {timeout} s: {what}")
        qapp.processEvents()
        time.sleep(0.003)


def layer_pixel(player, fx: float, fy: float) -> tuple[int, int, int]:
    """Piksel obrazu warstwy 0 w punkcie (ułamki obrazu warstwy)."""
    from qtpy.QtGui import QColor

    image = player.composition.layer_items[0].pixmap().toImage()
    color = QColor(image.pixel(int(fx * (image.width() - 1)), int(fy * (image.height() - 1))))
    return color.red(), color.green(), color.blue()


def near(actual, expected, tolerance: int = 50) -> bool:
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected, strict=True))


def corner(player) -> tuple[int, int, int]:
    """Lewy górny narożnik `LiveGLCorners` (czerwony kwadrat)."""
    from scenes.live_gl import FRAME_HEIGHT, FRAME_WIDTH

    return layer_pixel(player, 1 / FRAME_WIDTH, 1 / FRAME_HEIGHT)


def ready(player) -> bool:
    return player.live.sessions[0].state == "ready"


def key(player, code, *, autorepeat: bool = False, via_info: bool = False) -> None:
    from qtpy.QtCore import QEvent, Qt
    from qtpy.QtGui import QKeyEvent

    event = QKeyEvent(QEvent.Type.KeyPress, code, Qt.KeyboardModifier.NoModifier, "", autorepeat)
    (player.info.keyPressEvent if via_info else player.keyPressEvent)(event)


def click(player, fx: float, fy: float) -> None:
    """Prawdziwy klik myszy w viewport okna głównego, w punkcie kadru (ułamki)."""
    from qtpy.QtCore import QPointF, Qt
    from qtpy.QtTest import QTest

    width, height = RESOLUTION
    point = player.view.mapFromScene(QPointF(fx * width, fy * height))
    QTest.mouseClick(
        player.view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point
    )


def mouse(player, kind, fx: float, fy: float, middle: bool = False) -> None:
    """Surowe zdarzenie myszy w viewporcie, jak z prawdziwej myszy."""
    from qtpy.QtCore import QEvent, QPointF, Qt
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication

    width, height = RESOLUTION
    local = QPointF(player.view.mapFromScene(QPointF(fx * width, fy * height)))
    event_type, button, buttons = {
        "press": (
            QEvent.Type.MouseButtonPress,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        ),
        "move": (QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton),
        "release": (
            QEvent.Type.MouseButtonRelease,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
        ),
        "double": (
            QEvent.Type.MouseButtonDblClick,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
        ),
    }[kind]
    if middle:
        if button == Qt.MouseButton.LeftButton:
            button = Qt.MouseButton.MiddleButton
        if buttons == Qt.MouseButton.LeftButton:
            buttons = Qt.MouseButton.MiddleButton
    viewport = player.view.viewport()
    event = QMouseEvent(
        event_type,
        local,
        viewport.mapToGlobal(local),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport, event)


def recorded_sends(session) -> list[str]:
    sent = []
    original = session.send

    def send(command):
        sent.append(command)
        original(command)

    session.send = send
    return sent


@pytest.mark.gpu
def test_entering_slide_replaces_thumbnail_with_first_frame(qapp, player_for) -> None:
    player = player_for("LiveGLCorners")
    assert near(layer_pixel(player, 0.5, 0.5), MAGENTA)
    pump(qapp, lambda: near(corner(player), (255, 0, 0)), what="pierwsza klatka live")


@pytest.mark.gpu
def test_leaving_slide_reaps_process_and_reentry_is_fresh(qapp, player_for) -> None:
    player = player_for("LiveGLCorners")
    pump(qapp, lambda: ready(player))
    first = player.live.sessions[0]
    shm_name = first._shm.name

    player.load_previous_slide()
    assert player.live.sessions == {}
    pump(qapp, lambda: not player.live.stopping, what="odbiór procesu")
    # Ciepłe workery puli D48 żyją dalej z założenia; osierocona sesja nie.
    warm = {worker.process for worker in player.live.pool.workers}
    assert [p for p in mp.active_children() if p not in warm] == []

    player.load_next_slide()
    assert player.live.sessions[0] is not first
    assert player.live.sessions[0]._shm.name != shm_name
    pump(qapp, lambda: near(corner(player), (255, 0, 0)), what="pierwsza klatka po powrocie")


@pytest.mark.gpu
def test_quick_leave_and_return_keeps_sessions_apart(qapp, player_for) -> None:
    player = player_for("LiveGLCorners")
    pump(qapp, lambda: ready(player))
    player.load_previous_slide()
    player.load_next_slide()
    # Stara sesja jeszcze w odbiorze; nowa ma własną warstwę i własną miniaturę na starcie.
    assert len(player.live.stopping) == 1
    assert near(layer_pixel(player, 0.5, 0.5), MAGENTA)
    pump(qapp, lambda: near(corner(player), (255, 0, 0)) and not player.live.stopping)


@pytest.mark.gpu
def test_click_routes_arrows_to_layer_and_esc_returns_them(qapp, player_for) -> None:
    from qtpy.QtCore import Qt
    from scenes.live_gl import FRAME_WIDTH

    player = player_for("LiveGLAddRemoveBack")
    pump(qapp, lambda: ready(player))
    circle = (0.5 + 3 / FRAME_WIDTH, 0.5)
    assert not near(layer_pixel(player, *circle), (0, 0, 255))

    click(player, 0.75, 0.25)
    assert player.live.active == 0
    key(player, Qt.Key.Key_Right, via_info=True)
    pump(qapp, lambda: near(layer_pixel(player, *circle), (0, 0, 255)), what="cue swap")
    assert player.current_slide_index == 1

    key(player, Qt.Key.Key_Escape)
    assert player.live.active is None
    key(player, Qt.Key.Key_Right)
    assert player.current_slide_index == 2


@pytest.mark.gpu
def test_click_outside_layer_releases(qapp, player_for) -> None:
    player = player_for("LiveGLCorners")
    pump(qapp, lambda: ready(player))
    click(player, 0.75, 0.25)
    assert player.live.active == 0
    click(player, 0.25, 0.75)
    assert player.live.active is None


@pytest.mark.gpu
def test_keys_before_ready_are_consumed_not_queued(qapp, player_for) -> None:
    from qtpy.QtCore import Qt

    player = player_for("LiveGLSlowBuild")
    sent = recorded_sends(player.live.sessions[0])
    click(player, 0.75, 0.25)
    assert player.live.active == 0
    key(player, Qt.Key.Key_Right)
    assert player.current_slide_index == 1
    pump(qapp, lambda: ready(player), what="READY po wolnym budowaniu")
    assert "next" not in sent


@pytest.mark.gpu
def test_autorepeat_is_not_sent(qapp, player_for) -> None:
    from qtpy.QtCore import Qt

    player = player_for("LiveGLCorners")
    pump(qapp, lambda: ready(player))
    sent = recorded_sends(player.live.sessions[0])
    click(player, 0.75, 0.25)
    key(player, Qt.Key.Key_Right, autorepeat=True)
    key(player, Qt.Key.Key_Right)
    assert sent.count("next") == 1
    assert player.current_slide_index == 1


@pytest.mark.gpu
def test_cue_error_marks_layer_and_returns_keys(qapp, player_for) -> None:
    from qtpy.QtCore import Qt

    from manimcue.live_layers import ERROR_COLOR

    player = player_for("LiveGLCueRaises")
    errors = []
    player.live.error.connect(errors.append)
    pump(qapp, lambda: ready(player))
    click(player, 0.75, 0.25)
    key(player, Qt.Key.Key_Right)
    pump(qapp, lambda: 0 in player.live.failed, what="ERROR z cue")
    assert "boom from cue" in errors[0]
    assert player.live.active is None
    assert player.live.border.pen().color() == ERROR_COLOR
    key(player, Qt.Key.Key_Right)
    assert player.current_slide_index == 2


@pytest.mark.gpu
def test_build_error_before_ready_is_reported(qapp, player_for) -> None:
    player = player_for("LiveGLBuildRaises")
    errors = []
    player.live.error.connect(errors.append)
    pump(qapp, lambda: errors, what="ERROR z build_objects")
    assert "boom from build" in errors[0]
    click(player, 0.75, 0.25)
    assert player.live.active is None


@pytest.mark.gpu
def test_application_deactivation_releases_layer(qapp, player_for) -> None:
    from qtpy.QtCore import Qt

    player = player_for("LiveGLCorners")
    pump(qapp, lambda: ready(player))
    click(player, 0.75, 0.25)
    player.application_state_changed(Qt.ApplicationState.ApplicationInactive)
    assert player.live.active is None


@pytest.mark.gpu
def test_view_navigation_changes_and_resets_camera(qapp, player_for) -> None:
    player = player_for("LiveGLThreeD", rect=(0.0, 0.0, 1.0, 1.0))
    pump(qapp, lambda: ready(player))
    pump(qapp, lambda: not near(layer_pixel(player, 0.5, 0.5), MAGENTA), what="pierwsza klatka")
    start = player.composition.layer_items[0].pixmap().toImage()

    # Klik nadaje fokus; kolejny press MMB rozpoczyna capture, dwuklik LMB resetuje.
    click(player, 0.5, 0.5)
    mouse(player, "press", 0.5, 0.5, middle=True)
    assert player.live.active == 0
    mouse(player, "move", 0.5, 0.5, middle=True)
    mouse(player, "move", 0.62, 0.5, middle=True)
    mouse(player, "release", 0.62, 0.5, middle=True)
    pump(
        qapp,
        lambda: player.composition.layer_items[0].pixmap().toImage() != start,
        what="obrót kamery",
    )
    mouse(player, "double", 0.5, 0.5)
    pump(
        qapp,
        lambda: player.composition.layer_items[0].pixmap().toImage() == start,
        what="reset widoku",
    )


@pytest.mark.gpu
def test_gui_path_keeps_up_with_live_frames(qapp, player_for) -> None:
    from qtpy.QtCore import Qt
    from scenes.live_gl import MOVE_RUN_TIME

    player = player_for("LiveGLMoveFiveSeconds")
    pump(qapp, lambda: ready(player))
    updates = []
    original = player.composition.set_layer_image

    def counted(index, image):
        updates.append(time.monotonic())
        original(index, image)

    player.composition.set_layer_image = counted
    click(player, 0.75, 0.25)
    key(player, Qt.Key.Key_Right)
    # Stałe okno w środku cue, mierzone zegarem — po cue scena nie publikuje (runda 10, p. 5).
    window = MOVE_RUN_TIME - 1.0
    pump(qapp, lambda: updates and time.monotonic() - updates[0] > window + 0.5)
    inside = [t for t in updates if t - updates[0] <= window]
    rate = (len(inside) - 1) / window
    assert rate >= 0.8 * 60, rate


@pytest.mark.gpu
def test_view_after_sequence_end_does_not_break_barrier(qapp, player_for) -> None:
    from qtpy.QtCore import QPointF, Qt
    from scenes.live_gl import FRAME_WIDTH

    player = player_for("LiveGLAddRemoveBack")
    pump(qapp, lambda: ready(player))
    click(player, 0.75, 0.25)
    key(player, Qt.Key.Key_Right)
    pump(qapp, lambda: near(layer_pixel(player, 0.5 + 3 / FRAME_WIDTH, 0.5), (0, 0, 255)))
    # Zwykła klatka nawigacji po ostatniej granicy, potem `next` za końcem sekwencji.
    # Koniec cue (FadeIn trwa jeszcze po zbliżeniu do niebieskiego): inaczej zmianę obrazu
    # dałyby klatki animacji, a nawigacja weszłaby do klatki granicznej cue.
    settle = time.monotonic() + 1.0
    pump(qapp, lambda: time.monotonic() > settle)
    before = player.composition.layer_items[0].pixmap().toImage()
    player.live.click(0)
    player.live.drag(QPointF(400, 50), False)
    player.live.drag(QPointF(420, 50), False)
    pump(
        qapp,
        lambda: player.composition.layer_items[0].pixmap().toImage() != before,
        what="klatka nawigacji przed next",
    )
    key(player, Qt.Key.Key_Right)
    deadline = time.monotonic() + 2.5
    pump(qapp, lambda: time.monotonic() > deadline)
    assert player.live.failed == set()
    assert ready(player)


@pytest.mark.gpu
def test_slide_change_with_failed_and_active_layers(qapp, player_for) -> None:
    player = player_for(
        "LiveGLCorners",
        rect=(0.5, 0.0, 0.5, 0.5),
        extra=(("LiveGLBuildRaises", (0.0, 0.5, 0.5, 0.5)),),
    )
    pump(qapp, lambda: 1 in player.live.failed and ready(player))
    click(player, 0.75, 0.25)
    assert player.live.active == 0
    player.load_next_slide()
    assert player.live.active is None
    assert not player.live.border.isVisible()


def test_qt_gesture_focus_capture_cancel_reserved_ce_noop(qt_gestures):
    from types import SimpleNamespace

    from qtpy.QtCore import QPointF, QRectF

    controller, session, commands, _ = qt_gestures
    controller.drag(QPointF(10, 20), False)
    controller.drag(QPointF(20, 40), False)
    assert commands == []
    controller.click(0)
    controller.drag(QPointF(10, 20), False)
    controller.drag(QPointF(200, 400), False)
    assert commands == ["view orbit 1.90000 1.90000"]
    controller.end_drag()
    controller.drag(QPointF(30, 60), False)
    assert len(commands) == 1
    controller.click(0)
    controller.histories[session] = SimpleNamespace(reserved=True)
    controller.drag(QPointF(10, 20), False)
    controller.histories[session].reserved = False
    controller.drag(QPointF(20, 40), False)
    assert len(commands) == 1
    controller.identities[0] = ("ce-cairo",)
    controller.click(0)
    controller.drag(QPointF(10, 20), False)
    controller.drag(QPointF(20, 40), False)
    controller.wheel(1)
    controller.double_click(0)
    assert len(commands) == 1
    controller.identities[0] = ("manimgl",)
    controller.double_click(0)
    assert commands[-1] == "view reset"
    controller.composition.layer_rects[0] = QRectF(0, 0, 0, 0)
    controller.wheel(1)
    assert commands[-1] == "view reset"
    controller.release()
    assert controller.active is None and controller.drag_from is None


def test_qt_wheel_angle_pixel_delta_and_pointer_signal(qt_gestures):
    from qtpy.QtCore import QEvent, QPoint, QPointF, Qt
    from qtpy.QtGui import QMouseEvent, QWheelEvent

    from manimcue.composition import SlideView

    controller, _, commands, _ = qt_gestures
    view = SlideView(controller.composition)
    view.wheel_turned.connect(controller.wheel)
    point = QPointF(view.mapFromScene(QPointF(10, 20)))
    for angle, pixel in ((120, 0), (0, 20), (-60, 10)):
        view.wheelEvent(
            QWheelEvent(
                point,
                point,
                QPoint(0, pixel),
                QPoint(0, angle),
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
                Qt.ScrollPhase.NoScrollPhase,
                False,
            )
        )
    assert commands == ["view zoom 1", "view zoom 0.5", "view zoom -0.5"]
    dragged = []
    view.pointer_dragged.connect(lambda *args: dragged.append(args))
    view.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            point,
            point,
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.MiddleButton,
            Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier,
        )
    )
    assert len(dragged) == 1 and dragged[0][1:] == (True, "middle", True)
    view.mouseReleaseEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            point,
            point,
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    assert view.pointer_button is None
    view.close()


@pytest.mark.parametrize("kind", ["focus_window", "application_state"])
def test_qt_event_loss_cancels_capture(qt_gestures, kind):
    from qtpy.QtCore import QEvent, QPointF, Qt
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication

    from manimcue.composition import SlideView

    controller, _, commands, app = qt_gestures
    view = SlideView(controller.composition)
    view.layer_clicked.connect(controller.click)
    view.pointer_dragged.connect(controller.drag)
    view.pointer_released.connect(controller.end_drag)
    point = QPointF(view.mapFromScene(QPointF(10, 20)))
    target = view.viewport()

    def mouse(kind, offset=0):
        QApplication.sendEvent(
            target,
            QMouseEvent(
                kind,
                point + QPointF(offset, offset),
                point,
                Qt.MouseButton.MiddleButton
                if kind == QEvent.Type.MouseButtonPress
                else Qt.MouseButton.NoButton,
                Qt.MouseButton.MiddleButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )

    try:
        mouse(QEvent.Type.MouseButtonPress)
        mouse(QEvent.Type.MouseMove, 5)
        assert commands and controller.drag_from is not None
        if kind == "focus_window":
            app.focusWindowChanged.emit(None)
        else:
            app.applicationStateChanged.emit(Qt.ApplicationState.ApplicationInactive)
        assert view.pointer_button is None and controller.drag_from is None
        before = list(commands)
        mouse(QEvent.Type.MouseMove, 10)
        assert commands == before
        mouse(QEvent.Type.MouseButtonPress)
        mouse(QEvent.Type.MouseMove, 15)
        assert len(commands) == len(before) + 1
    finally:
        view.close()
