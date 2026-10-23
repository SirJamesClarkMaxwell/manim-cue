"""Minimalne testy PoC ImGui: układ (czysty Python) i dymne uruchomienie na PC i w przeglądarce.

uv run --frozen --with imgui-bundle==1.93.0 --with pyopengl python -m pytest experiments/f5i_imgui -q -p no:cacheprovider
Testy dymne otwierają prawdziwe okno (PC) i headless Edge/Chrome; przy braku przeglądarki skip.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from serve import find_browser
from stage import fit, interval_stats, layer_box

HERE = Path(__file__).resolve().parent


def test_fit_letterbox_and_pillarbox():
    assert fit(16 / 9, 0, 0, 1600, 900) == (0, 0, 1600, 900)
    assert fit(16 / 9, 0, 0, 1600, 1000) == (0, 50, 1600, 900)  # pasy u góry i dołu
    assert fit(16 / 9, 10, 0, 2000, 900) == (210, 0, 1600, 900)  # pasy po bokach
    assert fit(16 / 9, 0, 0, 0, 900)[2:] == (0.0, 0.0)


def test_layer_box_uses_frame_fractions_from_top_left():
    assert layer_box((100, 50, 1600, 900), (0.25, 0.5, 0.5, 0.25)) == (500, 500, 800, 225)


def test_interval_stats_window_only():
    times = [0.0, 1.0, 1.5, 2.0, 2.5, 9.0]
    stats = interval_stats(times, 1.0, 3.0)
    assert stats["count"] == 4 and stats["fps"] == 2.0
    assert stats["p50_ms"] == 500.0 and stats["max_ms"] == 500.0


def run_json(command, timeout):
    completed = subprocess.run(
        command, check=False, capture_output=True, text=True, encoding="utf-8", timeout=timeout
    )
    assert completed.returncode == 0, completed.stderr[-3000:]
    return json.loads(completed.stdout[completed.stdout.index("{") :])


def check_streams(result, names):
    assert "error" not in result, result
    for name in names:
        assert result["streams"][name]["fps"] > 20, (name, result["streams"][name])
    assert result["render"]["fps"] > 20


def test_desktop_smoke_one_clip_with_info():
    result = run_json(
        [
            sys.executable,
            str(HERE / "desktop.py"),
            "--clips",
            "1",
            "--no-live",
            "--warmup",
            "0.5",
            "--seconds",
            "2",
            "--window",
            "640x360",
        ],
        300,
    )
    check_streams(result, ["base", "clip_1", "preview_base", "preview_clip_1"])


@pytest.mark.skipif(find_browser() is None, reason="brak Edge/Chrome")
def test_web_smoke_same_stage_in_browser():
    result = run_json(
        [
            sys.executable,
            str(HERE / "serve.py"),
            "--clips",
            "1",
            "--headless",
            "--warmup",
            "0.5",
            "--seconds",
            "2",
            "--timeout",
            "240",
        ],
        300,
    )
    check_streams(result, ["base", "clip_1", "preview_base", "preview_clip_1"])
    assert result["platform"] == "web"
