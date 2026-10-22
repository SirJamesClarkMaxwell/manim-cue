"""Faza 6a: `SceneView` — klatki gotowego klipu w scenie-gospodarzu (CE i manimgl, D32).

Render gospodarza w osobnym procesie (`manim-cue render`), próbki pikseli z klatek wyjścia.
Oś czasu gospodarza w `tests/scenes/scene_view_ce.py`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path, PureWindowsPath

import av
import numpy as np
import pytest

from manimcue.frame_source import FrameSource

SCENES_DIR = Path(__file__).parent / "scenes"
COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
BLACK = (0, 0, 0)


def segments_clip(path: Path, fps: int = 30) -> Path:
    """2 s: czerwony, zielony, niebieski, biały — po 0,5 s."""
    per = fps // 2
    with av.open(str(path), "w") as out:
        stream = out.add_stream("mpeg4", rate=fps)
        stream.width, stream.height = 64, 36
        stream.pix_fmt = "yuv420p"
        for index in range(4 * per):
            array = np.zeros((36, 64, 3), np.uint8)
            array[:] = COLORS[index // per]
            for packet in stream.encode(av.VideoFrame.from_ndarray(array, format="rgb24")):
                out.mux(packet)
        for packet in stream.encode():
            out.mux(packet)
    return path


def near(actual, expected, tolerance: int = 60) -> bool:
    return all(abs(int(a) - e) <= tolerance for a, e in zip(actual, expected, strict=False))


# --- czas → klatka ------------------------------------------------------------------------


@pytest.mark.parametrize("fps", [24, 60])
def test_frame_source_boundaries_loop_and_seek(tmp_path: Path, fps: int) -> None:
    source = FrameSource(segments_clip(tmp_path / "c.mp4", fps))
    per = fps // 2
    # Granica 0,5 s ± ε: ostatnia klatka czerwieni i pierwsza zieleni.
    assert source.index_at(0.5 - 1e-3) == per - 1
    assert source.index_at(0.5) == per
    assert near(source.rgba(0.5 - 1e-3)[5, 5], COLORS[0])
    assert near(source.rgba(0.5)[5, 5], COLORS[1])
    # Koniec bez pętli: ostatnia klatka; cofnięcie czasu po końcu działa.
    assert near(source.rgba(9.0)[5, 5], COLORS[3])
    assert near(source.rgba(0.1)[5, 5], COLORS[0])
    looped = FrameSource(source.file, loop=True)
    assert near(looped.rgba(2.6)[5, 5], COLORS[1])


def test_playback_clock_pause_seek_and_rate() -> None:
    from manimcue.scene_view import Playback

    clock = [10.0]
    playback = Playback(source=None, clock=lambda: clock[0], rate=2.0)
    assert playback.now() == 0  # start przy pierwszym odczycie
    clock[0] = 11.0
    assert playback.now() == 2.0
    playback.pause()
    clock[0] = 15.0
    assert playback.now() == 2.0
    playback.resume()
    clock[0] = 15.5
    assert playback.now() == 3.0
    playback.seek(0.25)
    assert playback.now() == 0.25
    clock[0] = 16.0
    assert playback.now() == 1.25


# --- render gospodarza ---------------------------------------------------------------------


def render(tmp_path: Path, renderer_args: list[str], scene_file: Path, scene: str, clip: Path):
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "manimcue.slides",
            "render",
            *renderer_args,
            str(scene_file),
            scene,
            *(["-ql"] if "--GL" not in renderer_args else ["-l"]),
        ],
        cwd=tmp_path,
        env={**os.environ, "MANIMCUE_TEST_CLIP": str(clip)},
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    slides = json.loads((tmp_path / "slides" / f"{scene}.json").read_text(encoding="utf-8"))
    return [tmp_path / Path(*PureWindowsPath(s["file"]).parts) for s in slides["slides"]]


class Clip:
    """Klatki wyjścia gospodarza po czasie i piksel w punkcie sceny (jednostki Manima)."""

    def __init__(self, file: Path) -> None:
        with av.open(str(file)) as container:
            stream = container.streams.video[0]
            self.fps = float(stream.average_rate)
            self.frames = [frame.to_ndarray(format="rgb24") for frame in container.decode(stream)]
        self.height, self.width = self.frames[0].shape[:2]

    def pixel(self, t: float, x: float = 0.0, y: float = 0.0):
        frame = self.frames[min(round(t * self.fps), len(self.frames) - 1)]
        frame_width = 8.0 * self.width / self.height
        px = int((0.5 + x / frame_width) * (self.width - 1))
        py = int((0.5 - y / 8.0) * (self.height - 1))
        return tuple(frame[py, px])


def check_timeline(files: list[Path]) -> None:
    first, second = Clip(files[0]), Clip(files[1])
    red, green, blue = COLORS[:3]
    faded = first.pixel(0.25)
    assert 50 < faded[0] < 210 and faded[1] < 50 and faded[2] < 50, faded  # FadeIn w połowie
    assert near(first.pixel(0.75), green)  # zwykłe wait — wideo gra
    # Po przesunięciu i skali widok jest w x = 3, a stare miejsce to tło.
    assert near(first.pixel(2.25, x=3), red)  # pętla: 2,25 s → 0,25 s klipu
    assert near(first.pixel(2.25), BLACK)
    assert near(first.pixel(2.75, x=3), green)
    assert near(first.pixel(3.25, x=3), blue)  # pauza od 3,0 s → 1,0 s klipu
    # Slajd 2: wznowienie bez resetu — 3,75 s gospodarza to wciąż 1,25 s klipu (nie czerwień).
    assert near(second.pixel(0.25, x=3), blue)


def test_scene_view_ce_timeline(tmp_path: Path) -> None:
    clip = segments_clip(tmp_path / "clip.mp4")
    files = render(tmp_path, [], SCENES_DIR / "scene_view_ce.py", "ViewTimingCE", clip)
    check_timeline(files)


@pytest.mark.gpu
def test_scene_view_gl_timeline(tmp_path: Path) -> None:
    clip = segments_clip(tmp_path / "clip.mp4")
    files = render(tmp_path, ["--GL"], SCENES_DIR / "scene_view_gl.py", "ViewTimingGL", clip)
    check_timeline(files)


def check_two_views(files: list[Path]) -> None:
    clip = Clip(files[0])
    assert near(clip.pixel(0.25, x=-3), COLORS[0])  # 0,25 s klipu
    assert near(clip.pixel(0.25, x=3), COLORS[2])  # 1,25 s klipu


def test_two_views_ce(tmp_path: Path) -> None:
    clip = segments_clip(tmp_path / "clip.mp4")
    check_two_views(render(tmp_path, [], SCENES_DIR / "scene_view_ce.py", "TwoViewsCE", clip))


@pytest.mark.gpu
def test_two_views_gl(tmp_path: Path) -> None:
    clip = segments_clip(tmp_path / "clip.mp4")
    files = render(tmp_path, ["--GL"], SCENES_DIR / "scene_view_gl.py", "TwoViewsGL", clip)
    check_two_views(files)


def test_ce_cache_follows_new_source_render(tmp_path: Path) -> None:
    """Nowy render źródła pod tą samą ścieżką: drugi render gospodarza nie bierze starego klipu.

    CE przed `Wait` woła `update_mobjects(0)`, więc hash zawiera klatki widoczne na starcie
    `play()`. Zmieniony jest tylko segment, który prawy widok osiąga dopiero w trakcie `wait` —
    bez klucza źródła w `playback_id` hash byłby ten sam i CE wziąłby stary klip z cache.
    """
    clip = segments_clip(tmp_path / "clip.mp4")
    files = render(tmp_path, [], SCENES_DIR / "scene_view_ce.py", "TwoViewsCE", clip)
    assert near(Clip(files[0]).pixel(0.75, x=3), COLORS[3])  # 1,75 s klipu
    # Identyczny render ma użyć segmentów CE bez ponownego zapisu.
    segments = list((tmp_path / "media").rglob("partial_movie_files/**/*.mp4"))
    assert segments
    stamps = {path: path.stat().st_mtime_ns for path in segments}
    files = render(tmp_path, [], SCENES_DIR / "scene_view_ce.py", "TwoViewsCE", clip)
    assert {path: path.stat().st_mtime_ns for path in segments} == stamps
    assert set((tmp_path / "media").rglob("partial_movie_files/**/*.mp4")) == set(segments)
    assert near(Clip(files[0]).pixel(0.75, x=3), COLORS[3])
    original = COLORS[:]
    COLORS[3] = (0, 255, 0)
    try:
        segments_clip(clip)
        files = render(tmp_path, [], SCENES_DIR / "scene_view_ce.py", "TwoViewsCE", clip)
        assert near(Clip(files[0]).pixel(0.75, x=3), COLORS[3])
    finally:
        COLORS[:] = original
