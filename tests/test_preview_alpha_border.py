"""F5d-f: piksele podglądu, alfa GL/PNG, ciągi i role obwódki."""

import math
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError
from test_clip_layers import make_clip, png
from test_live_layers import pump

from manimcue.slides.config import (
    BorderStyle,
    ClipLayer,
    Config,
    Keyframe,
    LiveLayer,
    PresentationConfig,
    SlideConfig,
    SlideType,
)

SCENE = Path(__file__).parent / "scenes" / "live_alpha.py"


@pytest.fixture
def qapp():
    from manimcue.slides.qt_utils import qapp

    return qapp()


@pytest.mark.parametrize("value", [-1, 1.1, math.inf, math.nan])
def test_opacity_and_border_validation(value):
    with pytest.raises(ValidationError):
        LiveLayer(scene_file=SCENE, scene_name="EmptyAlpha", background_opacity=value)
    with pytest.raises(ValidationError):
        BorderStyle(opacity=value)
    if value < 0 or not math.isfinite(value):
        with pytest.raises(ValidationError):
            BorderStyle(width=value)


def test_models_without_qt_and_roundtrip(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from manimcue.slides import BorderStyle; "
                "BorderStyle(color='rgba(12, 34, 56, 0.5)'); "
                "assert not any(x.startswith(('qtpy', 'PySide6')) for x in sys.modules)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    base = png(tmp_path / "base.png", (0, 0, 255))
    layer = LiveLayer(
        scene_file=SCENE,
        scene_name="EmptyAlpha",
        session_id="a",
        active_border=BorderStyle(color="#00ffff80", width=9, opacity=0.5),
    )
    slide = SlideConfig(file=base, rev_file=base, layers=[layer])
    deck = PresentationConfig(slides=[slide, slide.model_copy(deep=True)])
    assert PresentationConfig.model_validate_json(deck.model_dump_json()) == deck
    deck.slides[1].layers[0].background_opacity = 0
    with pytest.raises(ValidationError, match="niespójna"):
        PresentationConfig.model_validate(deck.model_dump())
    deck.slides.insert(1, SlideConfig(file=base, rev_file=base))
    PresentationConfig.model_validate(deck.model_dump())
    assert LiveLayer(scene_file=SCENE, scene_name="EmptyAlpha").active_border.width == 6


@pytest.mark.gpu
@pytest.mark.parametrize("opacity", [0, 0.5, 1])
@pytest.mark.parametrize("scene,rgb", [("EmptyAlpha", (51, 102, 153)), ("EmptyBlack", (0, 0, 0))])
def test_gl_background_bars_and_composition(qapp, opacity, scene, rgb):
    from qtpy.QtCore import QRectF
    from qtpy.QtGui import QColor, QImage, QPainter

    from manimcue.live_session import LiveSpec, capture_first_frame

    frame = capture_first_frame(LiveSpec(str(SCENE.resolve()), scene, 160, 160, 60, opacity))
    image = QImage(frame.pixels, 160, 160, 640, QImage.Format.Format_RGBA8888).copy().mirrored()
    for y in (5, 80, 155):
        assert abs(image.pixelColor(80, y).alpha() - round(255 * opacity)) <= 1
        assert image.pixelColor(80, y).getRgb()[:3] == rgb
    target = QImage(160, 160, QImage.Format.Format_RGBA8888)
    target.fill(QColor(200, 100, 50))
    painter = QPainter(target)
    painter.drawImage(QRectF(0, 0, 160, 160), image)
    painter.end()
    expected = tuple(round(a * opacity + b * (1 - opacity)) for a, b in zip(rgb, (200, 100, 50)))
    for y in (5, 80, 155):
        assert all(abs(a - b) <= 2 for a, b in zip(target.pixelColor(80, y).getRgb()[:3], expected))


@pytest.mark.gpu
def test_thumbnail_cache_tracks_opacity(tmp_path):
    from types import SimpleNamespace

    from manimcue.slides.slide.base import BaseSlide

    holder = SimpleNamespace(_resolution=(160, 160))
    layer = LiveLayer(scene_file=SCENE, scene_name="EmptyAlpha", background_opacity=0)
    first = BaseSlide._live_thumbnail(holder, layer, tmp_path, True)
    layer.background_opacity = 0.5
    second = BaseSlide._live_thumbnail(holder, layer, tmp_path, True)
    assert first != second
    for y in (5, 80, 155):
        assert Image.open(first).getpixel((80, y))[3] == 0
        assert abs(Image.open(second).getpixel((80, y))[3] - 128) <= 1


def test_border_roles_motion_none_and_small_container(qapp):
    from manimcue.composition import SlideComposition
    from manimcue.live_layers import LiveLayerController

    composition = SlideComposition((160, 90))
    a = LiveLayer(
        scene_file=SCENE,
        scene_name="EmptyAlpha",
        rect=(0, 0, 0.5, 1),
        error_border=BorderStyle(color="red", width=12),
    )
    b = a.model_copy(update={"active_border": BorderStyle(color="cyan", width=10, opacity=0.5)})
    composition.set_layers([a, b])
    controller = LiveLayerController(composition)
    controller.layers = [a, b]
    controller.sessions = {0: object(), 1: object()}
    controller.fail(0, "test")
    controller.click(1)
    assert controller.border.pen().color().getRgb() == (0, 255, 255, 128)
    from qtpy.QtGui import QImage, QPainter

    image = QImage(160, 90, QImage.Format.Format_RGBA8888)
    image.fill(0)
    painter = QPainter(image)
    composition.render(painter)
    painter.end()
    assert all(
        abs(a - b) <= 2 for a, b in zip(image.pixelColor(40, 5).getRgb()[:3], (20, 148, 148))
    )
    assert image.pixelColor(40, 15).getRgb()[:3] == (40, 40, 40)
    composition.set_layer_rect(1, (0.5, 0, 0.5, 1))
    controller.follow_layer(1)
    assert controller.border.rect().x() == 85
    assert controller.border.pen().widthF() == 10
    controller.release()
    assert controller.framed == 0 and controller.border.pen().widthF() == 12
    b.active_border = None
    controller.click(1)
    assert controller.active == 1 and not controller.border.isVisible()
    a.error_border = None
    controller.release()
    assert not controller.border.isVisible()
    a.active_border = BorderStyle(width=1000)
    controller.frame_layer(0, "active")
    assert controller.border.rect().width() >= 0
    controller.sessions = {}


def test_preview_video_pixels_rates_cleanup_and_reverse(qapp, tmp_path):
    from qtpy.QtGui import QImage, QPainter

    from manimcue.slides.present.player import Player

    base = png(tmp_path / "base.png", (0, 0, 255), (320, 180))
    short = make_clip(tmp_path / "short.mp4", 0.4)
    long = make_clip(tmp_path / "long.mp4", 1.2)
    thumb = png(tmp_path / "thumb.png", (255, 0, 255))
    layer = ClipLayer(
        file=short,
        rect=(0, 0, 0.5, 1),
        thumbnail=thumb,
        keyframes=[Keyframe(t=0, rect=(0, 0, 0.5, 1)), Keyframe(t=1, rect=(0.5, 0, 0.5, 1))],
    )
    slides = [
        SlideConfig(file=base, rev_file=base, type=SlideType.Image),
        SlideConfig(
            file=base,
            rev_file=base,
            type=SlideType.Image,
            layers=[layer, ClipLayer(file=long, rect=(0.5, 0, 0.5, 1), playback_rate=2)],
        ),
    ]
    player = Player(Config(), [PresentationConfig(slides=slides, resolution=(320, 180))])
    colors = set()

    def changed():
        image = QImage(320, 180, QImage.Format.Format_RGBA8888)
        image.fill(0)
        painter = QPainter(image)
        player.preview.render(painter)
        painter.end()
        pixel = image.pixelColor(80, 90)
        if pixel.green() > 180:
            colors.add("green")
        if pixel.red() > 180 and pixel.blue() < 50:
            colors.add("red")
        return len(colors) == 2

    try:
        pump(qapp, changed, timeout=8)
        assert player.preview_clips.players[1].playbackRate() == 2
        assert player.preview.layer_rects[0].x() == 0
        from qtpy.QtCore import QCoreApplication, QEvent
        from qtpy.QtMultimedia import QMediaPlayer

        for _ in range(20):
            player.preview_next_slide()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert len(player.preview_clips.players) == 2
            assert len(player.preview_clips.findChildren(QMediaPlayer)) == 2
        player.preview_clips.failed(player.preview_clips.entry, 0)
        assert 0 not in player.preview_clips.players
        assert player.preview.layer_items[0].pixmap().toImage().pixelColor(0, 0).getRgb()[:3] == (
            255,
            0,
            255,
        )
        player.preview_next_slide()
        player.current_slide_index = 1
        player.preview_next_slide()
        assert not player.preview_clips.players and not player.preview.layer_items
        player.playing_reversed_slide = True
        player.preview_next_slide()
        assert Path(player.preview_clips.players[0].source().toLocalFile()) == short.resolve()
        old = player.preview_clips.entry
        player.preview_clips.clear()
        player.preview_clips.failed(old, 0)
    finally:
        player.close()
        player.live.shutdown()


@pytest.mark.gpu
def test_retained_alpha_remixes_after_index_and_base_change(qapp, tmp_path):
    from qtpy.QtGui import QImage, QPainter

    from manimcue.slides.present.player import Player

    a = png(tmp_path / "a.png", (200, 100, 50), (160, 160))
    b = png(tmp_path / "b.png", (20, 40, 80), (160, 160))
    layer = LiveLayer(
        scene_file=SCENE, scene_name="EmptyAlpha", background_opacity=0.5, session_id="alpha"
    )
    clip = ClipLayer(file=a, rect=(0, 0, 0.1, 0.1))
    deck = PresentationConfig(
        resolution=(160, 160),
        slides=[
            SlideConfig(file=a, rev_file=a, type=SlideType.Image, layers=[layer, clip]),
            SlideConfig(
                file=b, rev_file=b, type=SlideType.Image, layers=[clip, layer.model_copy()]
            ),
        ],
    )
    player = Player(Config(), [deck])

    def pixel():
        target = QImage(160, 160, QImage.Format.Format_RGBA8888)
        target.fill(0)
        painter = QPainter(target)
        player.composition.render(painter)
        painter.end()
        return target.pixelColor(80, 80).getRgb()[:3]

    try:
        pump(qapp, lambda: bool(player.live.last_frames))
        session = player.live.sessions[0]
        frame = player.live.last_frames[session]
        first = pixel()
        player.load_next_slide(reason="previous")
        assert player.live.sessions[1] is session
        assert player.live.last_frames[session] is frame
        second = pixel()
        assert first != second
        expected = tuple(
            round(a * 128 / 255 + b * 127 / 255) for a, b in zip((51, 102, 153), (20, 40, 80))
        )
        assert all(abs(a - b) <= 2 for a, b in zip(second, expected))
    finally:
        player.close()
        player.live.shutdown()


def test_preview_cross_presentation_resolution_and_hidden_info(qapp, tmp_path):
    from manimcue.slides.present.player import Player

    a = png(tmp_path / "a.png", (0, 0, 255))
    clip = make_clip(tmp_path / "clip.mp4", 0.5)
    slide = SlideConfig(file=a, rev_file=a, type=SlideType.Image, layers=[ClipLayer(file=clip)])
    decks = [
        PresentationConfig(slides=[SlideConfig(file=a, rev_file=a)], resolution=(160, 90)),
        PresentationConfig(slides=[slide], resolution=(320, 240)),
    ]
    player = Player(Config(), decks, hide_info_window=True)
    try:
        assert player.preview.sceneRect().width() == 320
        assert player.preview.sceneRect().height() == 240
        assert not player.preview_clips.players
        player.hide_info_window = False
        player.preview_next_slide()
        assert len(player.preview_clips.players) == 1
        player.playing_reversed_slide = True
        player.preview_next_slide()
        assert player.preview.sceneRect().width() == 160
        assert not player.preview_clips.players
    finally:
        player.close()
        player.live.shutdown()
