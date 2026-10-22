"""Testy korpusu scen: spójność presetów i prerender F1 przez CLI.

Test statyczny nie wymaga okna ani GPU. Testy prerender odpalają `manimcue.slides render`
w katalogu tymczasowym i sprawdzają JSON oraz klipy; wariant GL wymaga GPU.
"""

import importlib
import inspect
import json
import subprocess
import sys
from pathlib import Path, PureWindowsPath

import av
import pytest

SCENES_DIR = Path(__file__).parent / "scenes"

LIVE_SCENE_NAMES = sorted(
    [
        "LiveGLFirstFrame",
        "LiveGLCorners",
        "LiveGLMoveFiveSeconds",
        "LiveGLInterruptTwoPlays",
        "LiveGLAddRemoveBack",
        "LiveGLUpdaterWait",
        "LiveGLStaticWait",
        "LiveGLIdleUpdater",
        "LiveGLLoopBoundary",
        "LiveGLThreeD",
        "LiveGLTex",
        "LiveGLSlowBuild",
        "LiveGLCueRaises",
        "LiveGLBuildRaises",
    ]
)


def test_live_scenes_presets_are_consistent() -> None:
    module = importlib.import_module("scenes.live_gl")
    scenes = {
        name: cls
        for name, cls in vars(module).items()
        if inspect.isclass(cls)
        and issubclass(cls, module.CorpusScene)
        and cls is not module.CorpusScene
    }

    assert sorted(scenes) == LIVE_SCENE_NAMES
    for cls in scenes.values():
        # Każde cue z sekwencji i każda pętla muszą mieć preset, inaczej scena jest martwa.
        assert set(cls.SEQUENCE) <= set(cls.PRESETS), cls.__name__
        assert cls.LOOPS <= set(cls.PRESETS), cls.__name__


def _render(tmp_path: Path, renderer_args: list[str], scene_file: Path, scene: str) -> None:
    """Odpala `manimcue.slides render` w `tmp_path` i sprawdza exit code."""
    completed = subprocess.run(
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
        text=True,
        timeout=600,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _check_two_slides(tmp_path: Path, scene: str) -> None:
    """Wspólna weryfikacja wyniku prerender: JSON z dwoma slajdami i czytelne klipy."""
    slides_json = tmp_path / "slides" / f"{scene}.json"
    assert slides_json.is_file()

    slides = json.loads(slides_json.read_text(encoding="utf-8"))["slides"]
    assert [slide["notes"] for slide in slides] == ["slide 1", "slide 2"]

    for slide in slides:
        # Ścieżki w JSON są zapisane z odwrotnymi ukośnikami (Windows), względem tmp_path.
        clip = tmp_path / Path(*PureWindowsPath(slide["file"]).parts)
        assert clip.is_file(), clip
        with av.open(str(clip)) as container:
            assert any(True for _ in container.decode(video=0))


def test_prerender_ce_two_slides(tmp_path: Path) -> None:
    _render(tmp_path, [], SCENES_DIR / "prerender_ce.py", "PrerenderCETwoSlides")
    _check_two_slides(tmp_path, "PrerenderCETwoSlides")


@pytest.mark.gpu
def test_prerender_gl_two_slides(tmp_path: Path) -> None:
    _render(tmp_path, ["--GL"], SCENES_DIR / "prerender_gl.py", "PrerenderGLTwoSlides")
    _check_two_slides(tmp_path, "PrerenderGLTwoSlides")
