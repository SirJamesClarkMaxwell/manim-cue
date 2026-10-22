"""F5c: proporcje po kompozycji, placeholder i wspólny stan prelegenta."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw
from pydantic import ValidationError
from test_clip_layers import image_deck, make_clip, make_player, near, png

from manimcue.slides.config import ClipLayer, Config, Key, Keys, key_id


@pytest.fixture
def qapp():
    from manimcue.slides.qt_utils import qapp

    return qapp()


def test_clip_aspect_all_representations_and_container(qapp, tmp_path):
    from qtpy.QtCore import QPointF
    from qtpy.QtGui import QImage

    from manimcue.composition import SlideComposition, SlideView

    source = tmp_path / "circle.png"
    image = Image.new("RGB", (160, 90), "black")
    ImageDraw.Draw(image).ellipse((60, 25, 100, 65), fill="red")
    image.save(source)
    composition = SlideComposition((320, 180))
    composition.show_image(png(tmp_path / "base.png", (0, 0, 255)))
    layer = ClipLayer(file=source, rect=(0.36, 0.15, 0.28, 0.6))
    view = SlideView(composition)
    view.resize(640, 360)
    view.show()
    for video, at_end in ((False, False), (False, True)):
        composition.set_layers([layer], video=video, at_end=at_end)
        for rect in (layer.rect, (0.2, 0.1, 0.4, 0.7)):
            composition.set_layer_rect(0, rect)
            qapp.processEvents()
            item = composition.layer_items[0]
            assert item.transform().m11() == item.transform().m22()
            raster = view.viewport().grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            pixels = np.frombuffer(raster.constBits(), dtype=np.uint8).reshape(
                raster.height(), raster.width(), 4
            )
            ys, xs = np.where(
                (pixels[:, :, 0] > 180) & (pixels[:, :, 1] < 40) & (pixels[:, :, 2] < 40)
            )
            assert abs(np.ptp(xs) - np.ptp(ys)) <= 2
            container = composition.layer_rects[0]
            margin = container.topLeft() + QPointF(2, 2)
            assert view.layer_at(view.mapFromScene(margin)) == 0
            color = raster.pixelColor(view.mapFromScene(margin))
            assert near((color.red(), color.green(), color.blue()), (0, 0, 255))
            assert view.layer_at(view.mapFromScene(QPointF(1, 1))) == -1
    view.close()


def test_placeholder_new_frame_error_timeout_and_stale_entry(qapp, tmp_path):
    from qtpy.QtGui import QImage
    from qtpy.QtMultimedia import QVideoFrame
    from qtpy.QtMultimediaWidgets import QGraphicsVideoItem

    clip = ClipLayer(
        file=make_clip(tmp_path / "clip.mp4", 1), thumbnail=png(tmp_path / "thumb.png", (255, 0, 0))
    )
    player = make_player([image_deck(tmp_path, [clip])], start_paused=True)
    try:
        group = player.clips
        entry = group.entry
        assert 0 in player.composition.placeholders
        assert 0 in group.pending
        group.on_frame(entry - 1, 0, QVideoFrame())
        group.on_frame(entry, 0, QVideoFrame())
        assert 0 in player.composition.placeholders
        image = QImage(64, 36, QImage.Format.Format_RGB32)
        image.fill(0xFF00FF00)
        frame = QVideoFrame(image)
        group.on_frame(entry, 0, frame)
        assert 0 not in player.composition.placeholders
        assert not group.preparing
        assert not group.running
        group.on_frame(entry, 0, QVideoFrame())
        assert group.frames[0] == frame
        player.load_current_slide()
        assert 0 in player.composition.placeholders
        group.on_frame(entry, 0, frame)
        assert 0 in player.composition.placeholders
        group.prime_timeout(group.entry)
        assert not isinstance(player.composition.layer_items[0], QGraphicsVideoItem)
        assert not group.pending
    finally:
        player.close()
        player.live.shutdown()


def test_state_overlay_shared_text_and_navigation(qapp, tmp_path):
    from qtpy.QtCore import QEvent, Qt
    from qtpy.QtGui import QKeyEvent

    player = make_player([image_deck(tmp_path, [])])
    try:
        assert player.state_overlay.isHidden()
        assert player.state_overlay.parent() is player.view.viewport()

        def press(code):
            player.keyPressEvent(
                QKeyEvent(QEvent.Type.KeyPress, code, Qt.KeyboardModifier.NoModifier)
            )
            assert player.state_overlay.text() == player.info.presenter_state.text()

        press(Qt.Key.Key_S)
        assert not player.state_overlay.isHidden()
        press(Qt.Key.Key_Left)
        assert "brak poprzedniego" in player.state_overlay.text()
        press(Qt.Key.Key_Right)
        assert "slajd 2/2" in player.state_overlay.text()
        press(Qt.Key.Key_Right)
        assert "brak następnego" in player.state_overlay.text()
        press(Qt.Key.Key_V)
        assert "reverse" in player.state_overlay.text()
        press(Qt.Key.Key_Right)
        assert "odtwarzanie do przodu" in player.state_overlay.text()
        press(Qt.Key.Key_R)
        assert "live bez powtórzenia" in player.state_overlay.text()
    finally:
        player.close()
        player.live.shutdown()


def test_state_key_effective_defaults_and_merge():
    assert key_id("S") in Config().keys.PRESENTER_STATE.ids
    with pytest.raises(ValidationError):
        Keys(NEXT=Key(ids={key_id("S")}))
    left = Keys()
    right = Keys(NEXT=Key(ids={key_id("T")}), PRESENTER_STATE=Key(ids={key_id("Right")}))
    with pytest.raises(ValueError):
        left.merge_with(right)
    assert left.NEXT.ids == {key_id("Right")}


@pytest.mark.gpu
def test_narrow_live_thumbnail_geometry_and_view_reset(qapp, tmp_path):
    import time

    from test_live_corpus import is_ready
    from test_live_corpus import pump as live_pump

    from manimcue.live_session import LiveSession, LiveSpec, capture_first_frame

    scene = Path(__file__).parent / "scenes" / "live_gl.py"
    spec = LiveSpec(str(scene.resolve()), "LiveGLFirstFrame", 180, 216)
    thumbnail = capture_first_frame(spec)

    def bounds(frame):
        pixels = np.frombuffer(frame.pixels, dtype=np.uint8).reshape(frame.height, frame.width, 4)
        ys, xs = np.where((pixels[:, :, 0] > 180) & (pixels[:, :, 1] < 40))
        return np.ptp(xs), np.ptp(ys)

    width, height = bounds(thumbnail)
    assert abs(int(width) - int(height)) <= 2
    session = LiveSession()
    session.start(spec)
    try:
        _, frames = live_pump(session, lambda e, f: is_ready(e, f) and bool(f), 30)
        baseline = frames[-1]
        assert baseline.pixels == thumbnail.pixels
        for command in ("view orbit .1 .1", "view pan .1 0", "view pan 0 .1", "view zoom 1"):
            session.send(command)
            _, changed = live_pump(session, lambda e, f: bool(f), 5)
            assert changed[-1].pixels != baseline.pixels
            session.send("view reset")
            _, _restored = live_pump(
                session, lambda e, f: bool(f) and f[-1].pixels == baseline.pixels, 5
            )
    finally:
        session.request_stop()
        until = time.monotonic() + 5
        while session.running and time.monotonic() < until:
            session.poll()
            time.sleep(0.01)


@pytest.mark.gpu
def test_demo_repeated_cue_has_same_end_and_real_animation(qapp):
    import time

    from test_live_corpus import is_ready, names
    from test_live_corpus import pump as live_pump

    from manimcue.live_session import LiveSession, LiveSpec

    session = LiveSession()
    session.start(
        LiveSpec(
            str((Path(__file__).parents[1] / "examples/live_three.py").resolve()),
            "ThreePanel",
            180,
            216,
        )
    )
    try:
        live_pump(session, is_ready, 30)
        ends = []
        for _ in range(3):
            session.send("flip")
            events, frames = live_pump(session, lambda e, f: "CUE_DONE flip" in names(e), 8)
            assert len({f.pixels for f in frames}) > 10
            start = next(t for t, n in events if n == "CUE_START flip")
            end = next(t for t, n in events if n == "CUE_DONE flip")
            assert 1.8 < end - start < 3
            ends.append(frames[-1].pixels)
        assert ends[0] == ends[1] == ends[2]
        # Reset po cue i po back ma przywracać kadr graniczny także w wąskim panelu.
        for command in ("view reset", "back"):
            if command == "back":
                session.send(command)
                _, boundary = live_pump(session, lambda e, f: bool(f) and f[-1].boundary, 5)
                home = boundary[-1].pixels
            else:
                home = ends[-1]
            for movement in ("view orbit .1 .1", "view pan .1 0", "view pan 0 .1", "view zoom 1"):
                session.send(movement)
                live_pump(session, lambda e, f, home=home: bool(f) and f[-1].pixels != home, 5)
                session.send("view reset")
                live_pump(session, lambda e, f, home=home: bool(f) and f[-1].pixels == home, 5)
    finally:
        session.request_stop()
        until = time.monotonic() + 5
        while session.running and time.monotonic() < until:
            session.poll()
            time.sleep(0.01)


def test_state_preparing_pause_timeout_and_focus(qapp, tmp_path):
    from types import SimpleNamespace

    from qtpy.QtCore import QEvent, Qt
    from qtpy.QtGui import QKeyEvent

    player = make_player([image_deck(tmp_path, [])])
    try:
        group = player.clips
        group.preparing = True
        group.requested_playing = True
        group.pending = {"live"}
        player.live.sessions = {0: SimpleNamespace(state="starting")}
        player.live.active = 0
        player.update_presenter_state()
        assert "start zamówiony" in player.state_overlay.text()
        assert "fokus: live 1" in player.state_overlay.text()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
        player.keyPressEvent(event)
        assert "zignorowano przed READY" in player.state_overlay.text()
        group.toggle()
        assert "start w pauzie" in player.state_overlay.text()
        group.prime_timeout(group.entry)
        assert "cue pominięte" in player.state_overlay.text()
        assert "live: 1: start" in player.state_overlay.text()
        player.live.sessions[0].state = "ready"
        player.live.changed.emit()
        assert "gotowe" in player.state_overlay.text()
        assert "cue pominięte" in player.state_overlay.text()
        player.live.release()
        assert "fokus: slajdy" in player.state_overlay.text()
        player.live.observed.emit("live 1: koniec sekwencji")
        assert "koniec sekwencji" in player.state_overlay.text()
    finally:
        player.live.sessions = {}
        player.close()
        player.live.shutdown()


def test_video_letterbox_margin_is_transparent_after_decode(qapp, tmp_path):
    from qtpy.QtCore import QPointF
    from qtpy.QtGui import QColor
    from test_clip_layers import pump

    clip = ClipLayer(file=make_clip(tmp_path / "wide.mp4", 1), rect=(0.36, 0.15, 0.28, 0.6))
    player = make_player([image_deck(tmp_path, [clip])], start_paused=True)
    try:
        pump(qapp, lambda: not player.clips.preparing)
        assert not player.composition.placeholders
        player.view.resize(640, 360)
        player.view.show()
        qapp.processEvents()
        image = player.view.viewport().grab().toImage()
        rect = player.composition.layer_rects[0]
        margin = player.view.mapFromScene(rect.topLeft() + QPointF(3, 3))
        center = player.view.mapFromScene(rect.center())

        def rgb(point):
            c = QColor(image.pixel(point))
            return c.red(), c.green(), c.blue()

        assert near(rgb(margin), (0, 0, 60))
        assert near(rgb(center), (255, 0, 0))
    finally:
        player.close()
        player.live.shutdown()
