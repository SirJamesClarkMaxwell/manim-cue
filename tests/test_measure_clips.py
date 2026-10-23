"""Dymny pomiar prawdziwego dekodowania Qt offscreen."""

import importlib
import json
import os
import subprocess
import sys
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.gpu
@pytest.mark.parametrize(
    ("clips", "flags", "info_visible", "pixel_probe"),
    [("1", [], True, False), ("2,3", ["--no-info", "--pixel-probe"], False, True)],
)
def test_measure_clips_smoke(clips, flags, info_visible, pixel_probe):
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "examples/measure_clips.py"),
            "--clips",
            clips,
            *flags,
            "--seconds",
            "2",
            "--warmup",
            "0.2",
            "--resolution",
            "320x180",
            "--no-live",
        ],
        check=False,
        cwd=root,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["pixel_probe"] is pixel_probe
    assert result["info"] is info_visible
    assert len(result["results"]) == len(clips.split(","))
    for row in result["results"]:
        assert row["info_visible"] is info_visible
        assert row["qt_timer_samples"] > 10
        assert row["duration_seconds"] >= 2
        assert row["start_spread_ms"] is not None
        assert not row["errors"]
        for stream in row["streams"].values():
            assert stream["received_frames"] > 10
            assert stream["changed_frames"] > 10


def test_video_stamp_does_not_map_frame(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "examples"))
    measure = importlib.import_module("measure_clips")

    class Frame:
        def startTime(self):
            return 16667

        def endTime(self):
            return 33333

        def toImage(self):
            raise AssertionError("Lekka sonda nie moze odczytywac pikseli")

    frame = Frame()
    assert measure.video_stamp(frame) == (16667, 33333)
    frame.startTime = lambda: 33333
    assert measure.video_stamp(frame) == (33333, 33333)
    monkeypatch.setattr(measure, "video_bytes", lambda frame: b"pixels")
    assert measure.video_stamp(frame, pixel_probe=True) == zlib.crc32(b"pixels")
    monkeypatch.setattr(measure, "video_bytes", lambda frame: None)
    assert measure.video_stamp(frame, pixel_probe=True) is None


@pytest.mark.skipif(os.name != "nt", reason="Kod bledu Windows dla zakonczonego PID")
def test_timeout_after_live_process_already_exited(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "examples"))
    measure = importlib.import_module("measure_clips")
    (tmp_path / "case-2.pids.json").write_text("[123456789]", encoding="utf-8")

    class Process:
        waits = 0
        killed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def wait(self, timeout=None):
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("probe", timeout)
            return 0

        def kill(self):
            self.killed = True

    def missing_pid(pid, sig):
        error = OSError("Proces juz zakonczony")
        error.winerror = 87
        raise error

    process = Process()
    monkeypatch.setattr(measure.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(measure.os, "kill", missing_pid)
    args = SimpleNamespace(
        seconds=1,
        warmup=0,
        resolution=(320, 180),
        no_live=True,
        no_info=False,
        pixel_probe=False,
    )
    result = measure.measure_separately(2, args, tmp_path)
    assert result["streams"] == {}
    assert "Timeout procesu" in result["errors"][0]
    assert process.killed
    assert process.waits == 2
