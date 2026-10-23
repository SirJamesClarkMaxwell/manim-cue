"""Faza 5: warstwy z plików, ruch, wspólny start, walidacja długości, reverse (D29-D31).

Model, ruch i walidacja — deterministycznie. Wspólny start i reverse — z prawdziwym
dekodowaniem Qt offscreen na syntetycznych klipach (mpeg4), z timeoutem.
"""

import json
import time
from pathlib import Path

import av
import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from manimcue.media import check_layer_durations, video_info
from manimcue.slides.config import (
    FORMAT_VERSION,
    BaseSlideConfig,
    ClipLayer,
    Keyframe,
    LiveLayer,
    PresentationConfig,
    PreSlideConfig,
    SlideConfig,
    SlideType,
    slide_file,
)

LIVE_FILE = Path(__file__).parent / "scenes" / "live_gl.py"
RESOLUTION = (320, 180)
RED, GREEN, BLUE = (255, 0, 0), (0, 255, 0), (0, 0, 255)


def png(path: Path, color, size=(32, 18)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def make_clip(path: Path, seconds: float, fps: int = 30, color=RED, size=(64, 36)) -> Path:
    """Klip jednego koloru; ostatnia klatka zielona (do sprawdzania końca)."""
    count = round(seconds * fps)
    with av.open(str(path), "w") as out:
        stream = out.add_stream("mpeg4", rate=fps)
        stream.width, stream.height = size
        stream.pix_fmt = "yuv420p"
        array = np.zeros((size[1], size[0], 3), np.uint8)
        for index in range(count):
            array[:] = color if index < count - 1 else GREEN
            for packet in stream.encode(av.VideoFrame.from_ndarray(array, format="rgb24")):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return path


def near(actual, expected, tolerance: int = 40) -> bool:
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected, strict=False))


# --- model -----------------------------------------------------------------------------


def test_v2_layer_without_kind_reads_as_live(tmp_path: Path) -> None:
    (tmp_path / "slides").mkdir()
    base = png(tmp_path / "slides" / "base.png", RED)
    layer = {"scene_file": str(LIVE_FILE), "scene_name": "LiveGLCorners"}
    slide = {"file": str(base), "rev_file": str(base), "type": "image", "layers": [layer]}
    path = tmp_path / "slides" / "Old.json"
    path.write_text(json.dumps({"version": 2, "slides": [slide]}), encoding="utf-8")
    config = PresentationConfig.from_file(path)
    assert isinstance(config.slides[0].layers[0], LiveLayer)

    config.to_file(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["version"] == FORMAT_VERSION
    assert saved["slides"][0]["layers"][0]["kind"] == "live"


def test_mixed_layers_survive_slide_pipeline(tmp_path: Path) -> None:
    """next_slide → PreSlideConfig → SlideConfig → JSON → from_file, mieszane rodzaje."""
    (tmp_path / "slides").mkdir()
    base = png(tmp_path / "slides" / "base.png", RED)
    clip = make_clip(tmp_path / "clip.mp4", 1.0)
    layers = [
        ClipLayer(
            file=clip,
            rect=(-0.5, 0.0, 0.5, 0.5),
            keyframes=[
                Keyframe(t=0, rect=(-0.5, 0, 0.5, 0.5)),
                Keyframe(t=1, rect=(0.5, 0, 0.5, 0.5)),
            ],
        ),
        LiveLayer(scene_file=LIVE_FILE, scene_name="LiveGLCorners", rect=(0, 0, 0.5, 0.5)),
        {"kind": "clip", "file": str(base), "rect": (0.5, 0.5, 0.5, 0.5)},
    ]
    pre = PreSlideConfig.from_base_slide_config_and_animation_indices(
        BaseSlideConfig(layers=layers), 0, 1
    )
    slide = SlideConfig.from_pre_slide_config_and_files(pre, base, base)
    path = tmp_path / "slides" / "Mixed.json"
    PresentationConfig(slides=[slide]).to_file(path)
    loaded = PresentationConfig.from_file(path).slides[0].layers
    assert [type(layer) for layer in loaded] == [ClipLayer, LiveLayer, ClipLayer]
    assert loaded[0].is_video and not loaded[2].is_video
    assert loaded[0].keyframes[1].rect == (0.5, 0, 0.5, 0.5)


@pytest.mark.parametrize(
    "layer",
    [
        {"kind": "clip", "rect": (0, 0, 1, 1)},
        {"kind": "live", "file": "x.png"},
        {"kind": "other", "file": "x.png"},
    ],
)
def test_invalid_layers_are_rejected(layer, tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        BaseSlideConfig(layers=[layer])


def test_keyframes_and_rates_are_validated(tmp_path: Path) -> None:
    image = png(tmp_path / "i.png", RED)
    with pytest.raises(ValidationError, match="rosnąć"):
        ClipLayer(
            file=image,
            keyframes=[Keyframe(t=1, rect=(0, 0, 1, 1)), Keyframe(t=1, rect=(0, 0, 1, 1))],
        )
    with pytest.raises(ValidationError, match="nieujemne"):
        Keyframe(t=float("nan"), rect=(0, 0, 1, 1))
    with pytest.raises(ValidationError, match="dodatnie"):
        ClipLayer(file=image, playback_rate=0)
    # Klip może wjechać spoza kadru; live nie, bo prostokąt wyznacza rozdzielczość renderu.
    ClipLayer(file=image, rect=(-0.5, 0, 0.5, 0.5))
    with pytest.raises(ValidationError):
        LiveLayer(scene_file=LIVE_FILE, scene_name="X", rect=(-0.5, 0, 0.5, 0.5))


def test_rect_at_interpolates_and_clamps(tmp_path: Path) -> None:
    layer = ClipLayer(
        file=png(tmp_path / "i.png", RED),
        keyframes=[Keyframe(t=1, rect=(0, 0, 0.2, 0.2)), Keyframe(t=3, rect=(0.4, 0.2, 0.6, 0.6))],
    )
    assert layer.rect_at(0) == (0, 0, 0.2, 0.2)
    assert layer.rect_at(2) == pytest.approx((0.2, 0.1, 0.4, 0.4))
    assert layer.rect_at(9) == (0.4, 0.2, 0.6, 0.6)


def test_slide_file_from_other_cwd(tmp_path: Path, monkeypatch) -> None:
    deck = tmp_path / "deck"
    (deck / "slides" / "files").mkdir(parents=True)
    png(deck / "slides" / "files" / "a1b2.png", RED)
    slide = {"file": "slides/files/a1b2.png", "rev_file": "slides/files/a1b2.png", "type": "image"}
    (deck / "slides" / "Other.json").write_text(json.dumps({"slides": [slide]}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert (
        slide_file("deck/slides/Other.json", 0)
        == (deck / "slides" / "files" / "a1b2.png").resolve()
    )


# --- walidacja długości ------------------------------------------------------------------


def slide_with(base: Path, layers, base_type=SlideType.Video) -> SlideConfig:
    return SlideConfig(file=base, rev_file=base, type=base_type, layers=layers)


def test_durations_equal_unequal_and_exempt(tmp_path: Path) -> None:
    base = make_clip(tmp_path / "base.mp4", 2.0, fps=30)
    same = make_clip(tmp_path / "same.mp4", 2.0, fps=24)
    short = make_clip(tmp_path / "short.mp4", 1.0)
    assert video_info(same) == pytest.approx((2.0, 24.0), abs=0.05)

    check_layer_durations(slide_with(base, [ClipLayer(file=same)]))
    check_layer_durations(slide_with(base, [ClipLayer(file=short, playback_rate=0.5)]))
    with pytest.raises(ValueError, match=r"short\.mp4.*1\.000 s.*base\.mp4 2\.000 s"):
        check_layer_durations(slide_with(base, [ClipLayer(file=short)]), "Slajd 1: ")
    # Zwolnione: pętla, obraz, baza statyczna.
    check_layer_durations(slide_with(base, [ClipLayer(file=short, loop=True)]))
    check_layer_durations(slide_with(base, [ClipLayer(file=png(tmp_path / "i.png", RED))]))
    image_base = png(tmp_path / "b.png", RED)
    check_layer_durations(slide_with(image_base, [ClipLayer(file=short)], SlideType.Image))


# --- kompozycja, ruch, wspólny start (Qt offscreen) --------------------------------------


@pytest.fixture
def qapp():
    from manimcue.slides.qt_utils import qapp

    return qapp()


def pump(qapp, until, timeout: float = 10.0, what: str = "") -> None:
    deadline = time.monotonic() + timeout
    while not until():
        if time.monotonic() > deadline:
            pytest.fail(f"timeout {timeout} s: {what}")
        qapp.processEvents()
        time.sleep(0.002)


def view_pixel(view, fx: float, fy: float):
    from qtpy.QtGui import QColor

    image = view.grab().toImage()
    color = QColor(image.pixel(int(fx * (image.width() - 1)), int(fy * (image.height() - 1))))
    return color.red(), color.green(), color.blue()


def test_mixed_layers_compose_in_list_order(qapp, tmp_path: Path) -> None:
    from manimcue.composition import SlideComposition, SlideView

    red = png(tmp_path / "red.png", RED)
    blue = png(tmp_path / "blue.png", BLUE)
    green = png(tmp_path / "green.png", GREEN)
    layers = [
        ClipLayer(file=red, rect=(0, 0, 1, 1)),
        LiveLayer(scene_file=LIVE_FILE, scene_name="A", rect=(0.0, 0.0, 0.5, 0.5), thumbnail=green),
        ClipLayer(file=blue, rect=(0.25, 0.25, 0.5, 0.5)),
        LiveLayer(scene_file=LIVE_FILE, scene_name="B", rect=(0.5, 0.5, 0.5, 0.5), thumbnail=green),
    ]
    composition = SlideComposition(RESOLUTION)
    composition.set_layers(layers)
    views = [SlideView(composition), SlideView(composition)]
    for view in views:
        view.resize(*RESOLUTION)
        view.show()
    qapp.processEvents()
    for view in views:
        assert near(view_pixel(view, 0.1, 0.1), GREEN)  # live A nad czerwonym klipem
        assert near(view_pixel(view, 0.4, 0.4), BLUE)  # klip 2 nad live A
        assert near(view_pixel(view, 0.9, 0.9), GREEN)  # live B nad wszystkim
        assert near(view_pixel(view, 0.9, 0.1), RED)  # sam klip 0

    from qtpy.QtCore import QPoint

    view = views[0]
    assert view.layer_at(QPoint(int(0.1 * 320), int(0.1 * 180))) == 1
    assert view.layer_at(QPoint(int(0.9 * 320), int(0.9 * 180))) == 3


def image_deck(tmp_path: Path, layers) -> PresentationConfig:
    base = png(tmp_path / "base.png", (0, 0, 60), RESOLUTION)
    plain = SlideConfig(file=base, rev_file=base, type=SlideType.Image)
    with_layers = SlideConfig(file=base, rev_file=base, type=SlideType.Image, layers=layers)
    return PresentationConfig(slides=[with_layers, plain], resolution=RESOLUTION)


def make_player(configs, **kw):
    from qtpy.QtCore import Qt

    from manimcue.slides.config import Config
    from manimcue.slides.present.player import Player

    options = {"aspect_ratio_mode": Qt.AspectRatioMode.KeepAspectRatio, **kw}
    return Player(Config(), configs, **options)


def test_motion_follows_clock_pause_and_replay(qapp, tmp_path: Path) -> None:
    moving = ClipLayer(
        file=png(tmp_path / "i.png", RED),
        keyframes=[Keyframe(t=0, rect=(0, 0, 0.5, 0.5)), Keyframe(t=1, rect=(0.5, 0.5, 0.5, 0.5))],
    )
    player = make_player([image_deck(tmp_path, [moving])])
    group = player.clips
    assert group.static_active and group.running

    group.seconds = lambda: 0.5
    group.move()
    assert player.composition.layer_rects[0].getRect() == pytest.approx((80, 45, 160, 90))

    del group.seconds  # prawdziwy zegar
    player.play_pause()
    assert not group.running
    frozen = group.seconds()
    time.sleep(0.05)
    assert group.seconds() == frozen
    player.play_pause()
    assert group.running
    player.replay()
    assert group.seconds() < 0.05


def video_deck(tmp_path: Path, clips, seconds: float = 1.0) -> PresentationConfig:
    base = make_clip(tmp_path / "base.mp4", seconds, color=(0, 0, 60), size=RESOLUTION)
    with_layers = SlideConfig(file=base, rev_file=base, type=SlideType.Video, layers=clips)
    plain = SlideConfig(file=base, rev_file=base, type=SlideType.Video)
    return PresentationConfig(slides=[with_layers, plain], resolution=RESOLUTION)


def count_frames(sink, counter: list, index: int) -> None:
    sink.videoFrameChanged.connect(
        lambda frame: frame.isValid() and counter.__setitem__(index, counter[index] + 1)
    )


def test_group_starts_together_after_first_frames(qapp, tmp_path: Path) -> None:
    from qtpy.QtMultimedia import QMediaPlayer

    clips = [
        ClipLayer(file=make_clip(tmp_path / "a.mp4", 2.0), rect=(0, 0, 0.5, 0.5)),
        ClipLayer(file=make_clip(tmp_path / "b.mp4", 2.0, color=BLUE), rect=(0.5, 0, 0.5, 0.5)),
    ]
    player = make_player([video_deck(tmp_path, clips, 2.0)])
    group = player.clips
    sinks = [player.composition.video_item.videoSink()] + [
        player.composition.layer_items[i].videoSink() for i in (0, 1)
    ]
    # Klatki docierają przez pętlę zdarzeń, więc liczniki podłączone tuż po konstrukcji
    # widzą wszystko, co dekodery dały w przygotowaniu.
    before = [0] * len(sinks)
    for index, sink in enumerate(sinks):
        count_frames(sink, before, index)
    pump(qapp, lambda: not group.preparing, what="przygotowanie grupy")
    # Przygotowanie = co najwyżej klatka-dwie na klip (pauza działa z opóźnieniem dekodera),
    # nie odtwarzanie przed gotowością wszystkich.
    assert all(1 <= count <= 2 for count in before[1:]), before

    released = group.released_at
    firsts = [None] * len(sinks)
    for index, sink in enumerate(sinks):
        sink.videoFrameChanged.connect(
            lambda frame, i=index: (
                frame.isValid() and firsts[i] is None and firsts.__setitem__(i, time.perf_counter())
            )
        )
    pump(qapp, lambda: all(firsts), what="pierwsze klatki po starcie")
    # Miara dostarczenia do wątku GUI (pompa co 2 ms), nie wyświetlenia — to mierzy PoC.
    assert max(firsts) - min(firsts) <= 0.05, [f - released for f in firsts]

    player.play_pause()
    pump(
        qapp,
        lambda: all(
            p.playbackState() == QMediaPlayer.PlaybackState.PausedState
            for p in [player.media_player, *group.players.values()]
        ),
        what="wspólna pauza",
    )


def test_restored_base_frame_does_not_release_barrier(qapp, tmp_path: Path) -> None:
    from qtpy.QtGui import QImage
    from qtpy.QtMultimedia import QVideoFrame

    clips = [ClipLayer(file=make_clip(tmp_path / "a.mp4", 1.0), rect=(0, 0, 0.5, 0.5))]
    player = make_player([video_deck(tmp_path, clips)])
    image = QImage(8, 8, QImage.Format.Format_RGBA8888)
    image.fill(0xFF0000FF)
    old = QVideoFrame(image)
    # Źródło bazy już załadowane; baza sztucznie znów czeka — izoluje rozpoznanie przywróconej.
    group = player.clips
    pump(qapp, lambda: not group.preparing)
    player.frame = old  # to, co frame_changed wstrzyknąłby po pustej klatce zmiany źródła
    assert group.restored(old)
    assert not group.restored(QVideoFrame(image))
    group.preparing, group.pending = True, {"base"}
    group.on_base_frame(old)
    assert "base" in group.pending
    group.on_base_frame(QVideoFrame(image))
    assert not group.pending and not group.preparing


def test_broken_clip_does_not_block_group(qapp, tmp_path: Path) -> None:
    from qtpy.QtWidgets import QGraphicsPixmapItem

    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video")
    clips = [
        ClipLayer(file=broken, rect=(0, 0, 0.5, 0.5), thumbnail=png(tmp_path / "t.png", RED)),
        ClipLayer(file=make_clip(tmp_path / "ok.mp4", 1.0), rect=(0.5, 0, 0.5, 0.5)),
    ]
    player = make_player([video_deck(tmp_path, clips)])
    pump(qapp, lambda: not player.clips.preparing, timeout=8, what="start mimo błędnego klipu")
    assert 0 not in player.clips.players and 1 in player.clips.players
    # Zamiast pustego elementu wideo — miniatura.
    assert isinstance(player.composition.layer_items[0], QGraphicsPixmapItem)


def test_pause_during_preparation_is_kept(qapp, tmp_path: Path) -> None:
    from qtpy.QtMultimedia import QMediaPlayer

    clips = [ClipLayer(file=make_clip(tmp_path / "a.mp4", 1.0), rect=(0, 0, 0.5, 0.5))]
    player = make_player([video_deck(tmp_path, clips)])
    assert player.clips.preparing
    player.play_pause()
    player.replay()  # w trakcie przygotowania: bez puszczania samej bazy
    pump(qapp, lambda: not player.clips.preparing)
    sinks = [
        player.composition.video_item.videoSink(),
        player.composition.layer_items[0].videoSink(),
    ]
    after = [0, 0]
    for index, sink in enumerate(sinks):
        count_frames(sink, after, index)
    settle = time.monotonic() + 0.3
    pump(qapp, lambda: time.monotonic() > settle)
    playing = QMediaPlayer.PlaybackState.PlayingState
    assert player.media_player.playbackState() != playing
    assert all(p.playbackState() != playing for p in player.clips.players.values())
    assert after == [0, 0] and not player.clips.running


def test_replay_in_pause_resumes_for_both_base_kinds(qapp, tmp_path: Path) -> None:
    (tmp_path / "v").mkdir()
    clips = [ClipLayer(file=make_clip(tmp_path / "v" / "a.mp4", 1.0), rect=(0, 0, 0.5, 0.5))]
    video = make_player([video_deck(tmp_path / "v", clips)])
    pump(qapp, lambda: not video.clips.preparing)
    video.play_pause()
    pump(qapp, lambda: not video.clips.running)
    video.replay()
    pump(qapp, lambda: video.clips.running, what="replay wznawia grupę nad wideo")

    moving = ClipLayer(
        file=png(tmp_path / "i.png", RED),
        keyframes=[Keyframe(t=0, rect=(0, 0, 1, 1)), Keyframe(t=1, rect=(0, 0, 0.5, 0.5))],
    )
    static = make_player([image_deck(tmp_path, [moving])])
    static.play_pause()
    assert not static.clips.running
    static.replay()
    assert static.clips.running and static.clips.seconds() < 0.05


def test_next_on_static_loop_slide_advances(qapp, tmp_path: Path) -> None:
    moving = ClipLayer(
        file=png(tmp_path / "i.png", RED),
        keyframes=[Keyframe(t=0, rect=(0, 0, 1, 1)), Keyframe(t=1, rect=(0, 0, 0.5, 0.5))],
    )
    deck = image_deck(tmp_path, [moving])
    deck.slides[0].loop = True
    player = make_player([deck], next_terminates_loop=True)
    assert player.clips.running
    player.next()
    assert player.current_slide_index == 1


def test_active_border_follows_moving_live_layer(qapp, tmp_path: Path) -> None:
    live = LiveLayer(
        scene_file=LIVE_FILE,
        scene_name="A",
        rect=(0, 0, 0.5, 0.5),
        thumbnail=png(tmp_path / "t.png", GREEN),
        keyframes=[Keyframe(t=0, rect=(0, 0, 0.5, 0.5)), Keyframe(t=1, rect=(0.5, 0.5, 0.5, 0.5))],
    )
    player = make_player([image_deck(tmp_path, [live])])
    controller = player.live
    # Bez procesu: do geometrii obwódki sesja nie jest potrzebna.
    controller.shutdown()
    from manimcue.live_session import LiveSession
    session = LiveSession()
    session.state = "ready"
    controller.sessions = {0: session}
    controller.click(0)
    player.clips.seconds = lambda: 1.0
    player.clips.move()
    assert controller.border.rect().center() == player.composition.layer_rects[0].center()


def test_reverse_shows_clip_end_frame_in_final_rect(qapp, tmp_path: Path) -> None:
    from qtpy.QtGui import QColor

    end = png(tmp_path / "end.png", GREEN)
    clip = ClipLayer(
        file=make_clip(tmp_path / "a.mp4", 1.0),
        end_thumbnail=end,
        keyframes=[
            Keyframe(t=0, rect=(0, 0, 0.25, 0.25)),
            Keyframe(t=1, rect=(0.5, 0.5, 0.5, 0.5)),
        ],
    )
    config = video_deck(tmp_path, [clip])
    # Start na drugim slajdzie: slajd z klipem nie był wcześniej odtwarzany.
    player = make_player([config], slide_index=1)
    player.reverse()
    assert player.current_slide_index == 0
    assert player.current_file == config.slides[0].rev_file
    item = player.composition.layer_items[0]
    assert player.composition.layer_rects[0].getRect() == (160, 90, 160, 90)
    color = QColor(item.pixmap().toImage().pixel(5, 5))
    assert near((color.red(), color.green(), color.blue()), GREEN)
    assert player.clips.players == {}
    # Baza naprawdę gra cofnięty klip.
    frames = [0]
    count_frames(player.composition.video_item.videoSink(), frames, 0)
    pump(qapp, lambda: frames[0] > 3, what="klatki cofanej bazy")
