"""Faza 3: model warstwy live, miniatura w renderze, kompozycja w playerze.

Testy modelu i Qt idą offscreen bez GPU; render z miniaturą uruchamia scenę GL (`gpu`).
"""

import json
import multiprocessing as mp
import subprocess
import sys
from pathlib import Path, PureWindowsPath

import pytest
from PIL import Image
from pydantic import ValidationError

from manimcue.slides.config import (
    FORMAT_VERSION,
    LiveLayer,
    PresentationConfig,
    SlideConfig,
    SlideType,
)

SCENES_DIR = Path(__file__).parent / "scenes"
UPSTREAM_JSON = Path(__file__).parent / "slides" / "data" / "slides" / "BasicSlide.json"
LIVE_FILE = SCENES_DIR / "live_gl.py"
RED = (255, 0, 0)


def png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (64, 36)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def near(actual, expected, tolerance: int = 40) -> bool:
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected, strict=False))


# --- model -----------------------------------------------------------------------------


def test_upstream_json_reads_and_saves_current_version(tmp_path: Path) -> None:
    config = PresentationConfig.from_file(UPSTREAM_JSON)
    assert config.version == FORMAT_VERSION
    assert all(slide.layers == [] for slide in config.slides)

    saved = tmp_path / "slides" / "Basic.json"
    saved.parent.mkdir()
    config.to_file(saved)
    assert json.loads(saved.read_text(encoding="utf-8"))["version"] == FORMAT_VERSION


def test_newer_version_is_rejected(tmp_path: Path) -> None:
    obj = json.loads(UPSTREAM_JSON.read_text(encoding="utf-8"))
    obj["version"] = FORMAT_VERSION + 1
    path = tmp_path / "slides" / "Future.json"
    path.parent.mkdir()
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValidationError, match="nowszym"):
        PresentationConfig.from_file(path)


@pytest.mark.parametrize(
    "rect",
    [(0.6, 0.0, 0.5, 0.5), (0.0, 0.0, 0.0, 0.5), (-0.1, 0.0, 0.5, 0.5), (0.0, float("nan"), 1, 1)],
)
def test_layer_rect_outside_frame_is_rejected(rect) -> None:
    with pytest.raises(ValidationError, match=r"rect \("):
        LiveLayer(scene_file=LIVE_FILE, scene_name="LiveGLCorners", rect=rect)


def test_layer_size_has_at_least_one_pixel() -> None:
    layer = LiveLayer(scene_file=LIVE_FILE, scene_name="X", rect=(0.0, 0.0, 1e-6, 0.5))
    assert layer.size((1920, 1080)) == (1, 540)


def test_layer_paths_resolve_relative_to_json_from_other_cwd(tmp_path, monkeypatch) -> None:
    deck = tmp_path / "deck"
    (deck / "slides" / "files").mkdir(parents=True)
    png(deck / "slides" / "files" / "clip.png", RED)
    png(deck / "slides" / "files" / "thumb.png", RED)
    (deck / "panel.py").write_text("", encoding="utf-8")
    slide = {
        "file": "slides/files/clip.png",
        "rev_file": "slides/files/clip.png",
        "type": "image",
        "layers": [
            {
                "scene_file": "panel.py",
                "scene_name": "Panel",
                "thumbnail": "slides/files/thumb.png",
            }
        ],
    }
    path = deck / "slides" / "Deck.json"
    path.write_text(json.dumps({"slides": [slide]}), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    layer = PresentationConfig.from_file(Path("deck/slides/Deck.json")).slides[0].layers[0]
    assert layer.scene_file.resolve() == (deck / "panel.py").resolve()
    assert layer.thumbnail.resolve() == (deck / "slides" / "files" / "thumb.png").resolve()


def live_presentation(tmp_path: Path, resolution=(320, 180)) -> PresentationConfig:
    """Dwa slajdy-obrazy: drugi z warstwą live w prawym górnym rogu i czerwoną miniaturą."""
    base = png(tmp_path / "base.png", (0, 0, 80), resolution)
    thumbnail = png(tmp_path / "thumb.png", RED)
    layer = LiveLayer(
        scene_file=LIVE_FILE,
        scene_name="LiveGLCorners",
        rect=(0.5, 0.0, 0.5, 0.5),
        thumbnail=thumbnail,
    )
    slides = [
        SlideConfig(file=base, rev_file=base, type=SlideType.Image),
        SlideConfig(file=base, rev_file=base, type=SlideType.Image, layers=[layer]),
    ]
    return PresentationConfig(slides=slides, resolution=resolution)


def test_converters_and_copy_reject_live_layers(tmp_path: Path) -> None:
    from manimcue.slides.convert import RevealJS

    config = live_presentation(tmp_path)
    with pytest.raises(ValidationError, match="Prezentacja 1, slajd 2.*LiveGLCorners"):
        RevealJS(presentation_configs=[config])
    with pytest.raises(ValueError, match="slajd 2"):
        config.copy_to(tmp_path)


# --- kompozycja i player (Qt offscreen) -----------------------------------------------


@pytest.fixture
def qapp():
    from manimcue.slides.qt_utils import qapp

    return qapp()


def make_player(configs, **kw):
    from qtpy.QtCore import Qt

    from manimcue.slides.config import Config
    from manimcue.slides.present.player import Player

    options = {
        "aspect_ratio_mode": Qt.AspectRatioMode.KeepAspectRatio,
        "hide_info_window": False,
        **kw,
    }
    return Player(Config(), configs, **options)


def view_pixel(view, fx: float, fy: float) -> tuple[int, int, int]:
    """Piksel widoku w punkcie kadru (ułamki); widok ma proporcje kadru, więc bez pasów."""
    from qtpy.QtGui import QColor

    image = view.grab().toImage()
    color = QColor(image.pixel(int(fx * (image.width() - 1)), int(fy * (image.height() - 1))))
    return color.red(), color.green(), color.blue()


def test_composition_draws_thumbnail_in_layer_rect(qapp, tmp_path: Path) -> None:
    from manimcue.composition import SlideComposition, SlideView

    config = live_presentation(tmp_path)
    composition = SlideComposition(config.resolution)
    composition.show_image(config.slides[1].file)
    composition.set_layers(config.slides[1].layers)
    views = [SlideView(composition), SlideView(composition)]
    for view, size in zip(views, [(640, 360), (320, 180)], strict=True):
        view.resize(*size)
        view.show()
    qapp.processEvents()

    rect = composition.layer_items[0].sceneBoundingRect()
    assert rect.getRect() == (160, 0, 160, 90)
    for view in views:
        assert near(view_pixel(view, 0.75, 0.25), RED)
        assert near(view_pixel(view, 0.25, 0.75), (0, 0, 80))


def test_set_layer_image_keeps_rect(qapp, tmp_path: Path) -> None:
    from qtpy.QtGui import QImage

    from manimcue.composition import SlideComposition

    config = live_presentation(tmp_path)
    composition = SlideComposition(config.resolution)
    composition.set_layers(config.slides[1].layers)
    before = composition.layer_items[0].sceneBoundingRect()
    image = QImage(17, 9, QImage.Format.Format_RGBA8888)
    image.fill(0xFF00FF00)
    composition.set_layer_image(0, image)
    assert composition.layer_items[0].sceneBoundingRect() == before


def test_player_info_shares_composition_and_previews_layers(qapp, tmp_path: Path) -> None:
    player = make_player([live_presentation(tmp_path)])
    assert player.info.main_view.scene() is player.composition
    assert player.composition.layer_items == []
    # Podgląd pokazuje warstwę następnego slajdu, zanim prelegent na niego wejdzie.
    assert len(player.preview.layer_items) == 1

    player.load_next_slide()
    assert len(player.composition.layer_items) == 1
    rect = player.composition.layer_items[0].sceneBoundingRect()
    assert rect.getRect() == (160, 0, 160, 90)


def test_player_switches_resolution_between_presentations(qapp, tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    small = live_presentation(tmp_path / "a")
    large = live_presentation(tmp_path / "b", resolution=(640, 360))
    player = make_player([small, large])
    # Ostatni slajd pierwszej prezentacji: podgląd ma już kadr drugiej.
    player.load_next_slide()
    assert player.preview.sceneRect().getRect() == (0, 0, 640, 360)
    player.load_next_slide()
    assert player.composition.sceneRect().getRect() == (0, 0, 640, 360)


def test_frame_changed_reuses_only_valid_previous_frame(qapp, tmp_path: Path) -> None:
    from qtpy.QtGui import QImage
    from qtpy.QtMultimedia import QVideoFrame

    player = make_player([live_presentation(tmp_path)])
    # Brak poprawnej poprzedniej klatki: pusta nie wraca do sinka (rekurencja sygnału).
    player.frame_changed(QVideoFrame())
    assert not player.frame.isValid()

    image = QImage(8, 8, QImage.Format.Format_RGBA8888)
    image.fill(0xFF0000FF)
    valid = QVideoFrame(image)
    player.frame_changed(valid)
    player.frame_changed(QVideoFrame())
    assert player.video_sink.videoFrame().isValid()


def test_hide_mouse_reaches_view(qapp, tmp_path: Path) -> None:
    from qtpy.QtCore import Qt

    player = make_player([live_presentation(tmp_path)], hide_mouse=True)
    assert player.view.viewport().cursor().shape() == Qt.CursorShape.BlankCursor


# --- render z miniaturą (GPU) ----------------------------------------------------------


def render(tmp_path: Path, renderer_args: list[str], scene_file: Path, scene: str):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "manimcue.slides",
            "render",
            *renderer_args,
            str(scene_file.resolve()),
            scene,
            *(["-ql"] if "--GL" not in renderer_args else ["-l"]),
        ],
        cwd=tmp_path,
        capture_output=True,
        # Rich drukuje traceback ze źródłem (polskie komentarze, ramki) — kodowanie systemowe
        # Windows (cp1252) gubiłoby całe wyjście, a test szuka w nim treści błędu.
        encoding="utf-8",
        errors="replace",
        timeout=600,
        check=False,
    )


def check_thumbnail(tmp_path: Path, scene: str) -> Path:
    """Slajd 2 ma warstwę z miniaturą `LiveGLCorners`: narożniki w swoich kolorach."""
    slides = json.loads((tmp_path / "slides" / f"{scene}.json").read_text(encoding="utf-8"))
    assert slides["version"] == FORMAT_VERSION
    assert slides["slides"][0]["layers"] == []
    (layer,) = slides["slides"][1]["layers"]
    assert layer["scene_name"] == "LiveGLCorners"
    thumbnail = tmp_path / Path(*PureWindowsPath(layer["thumbnail"]).parts)
    image = Image.open(thumbnail).convert("RGB")
    width, height = image.size
    resolution = tuple(slides["resolution"])
    assert (width, height) == (round(resolution[0] / 2), round(resolution[1] / 2))

    from scenes.live_gl import FRAME_HEIGHT, FRAME_WIDTH

    def at(x: float, y: float):
        return image.getpixel(
            (int((0.5 + x / FRAME_WIDTH) * width), int((0.5 - y / FRAME_HEIGHT) * height))
        )

    dx, dy = FRAME_WIDTH / 2 - 1, FRAME_HEIGHT / 2 - 1
    assert near(at(-dx, dy), RED)
    assert near(at(dx, dy), (0, 255, 0))
    assert near(at(-dx, -dy), (0, 0, 255))
    assert near(at(dx, -dy), (255, 255, 255))
    return thumbnail


@pytest.mark.gpu
def test_render_ce_writes_layer_thumbnail_and_caches_it(tmp_path: Path) -> None:
    completed = render(tmp_path, [], SCENES_DIR / "layers_ce.py", "LayersCE")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    thumbnail = check_thumbnail(tmp_path, "LayersCE")

    stamp = thumbnail.stat().st_mtime_ns
    completed = render(tmp_path, [], SCENES_DIR / "layers_ce.py", "LayersCE")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert thumbnail.stat().st_mtime_ns == stamp


@pytest.mark.gpu
def test_render_gl_writes_layer_thumbnail(tmp_path: Path) -> None:
    completed = render(tmp_path, ["--GL"], SCENES_DIR / "layers_gl.py", "LayersGL")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    check_thumbnail(tmp_path, "LayersGL")


@pytest.mark.gpu
def test_render_fails_when_layer_scene_raises(tmp_path: Path) -> None:
    completed = render(tmp_path, [], SCENES_DIR / "layers_ce.py", "LayersCEBuildRaises")
    assert completed.returncode != 0
    assert "boom from build" in completed.stdout + completed.stderr
    assert not (tmp_path / "slides" / "LayersCEBuildRaises.json").exists()


@pytest.mark.gpu
def test_capture_times_out_on_slow_build_and_reaps_worker() -> None:
    from manimcue.live_session import LiveSpec, capture_first_frame

    spec = LiveSpec(str(LIVE_FILE.resolve()), "LiveGLSlowBuild", 64, 36)
    with pytest.raises(TimeoutError):
        capture_first_frame(spec, timeout=0.5)
    assert mp.active_children() == []
