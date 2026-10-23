"""Odbiór programowy prawdziwych okien; brak sterownika jest błędem bramki."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.gpu


@pytest.fixture(scope="module")
def gate(tmp_path_factory):
    if sys.platform != "win32":
        pytest.skip("Bramka Windows wymaga Windows")
    output = tmp_path_factory.mktemp("windows-gate") / "result.json"
    info_monitor = int(os.environ.get("F10_INFO_MONITOR", "0"))
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "experiments/f10a_gate/windows.py"),
            "--info-monitor",
            str(info_monitor),
            "--output",
            str(output),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    assert output.exists(), process.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert process.returncode == 0, (result, process.stderr)
    result["info_monitor"] = info_monitor
    return result


def test_two_native_windows(gate):
    windows = gate["windows"]["before"]
    assert windows["main"]["handle"] != windows["info"]["handle"]
    assert windows["main"]["native_handle"] != windows["info"]["native_handle"]
    assert all(window["native_handle"] for window in windows.values())
    assert gate["viewport_ids"]["main"] != gate["viewport_ids"]["info"]
    for name, index in (("main", 0), ("info", gate["info_monitor"])):
        monitor = gate["monitors"][index]
        assert windows[name]["position"] == [value + 80 for value in monitor["position"]]
        assert all(value > 0 for value in windows[name]["size"])


def test_fullscreen_roundtrip(gate):
    for name, index in (("main", 0), ("info", gate["info_monitor"])):
        before = gate["windows"]["before"][name]
        fullscreen = gate["windows"]["fullscreen"][name]
        after = gate["windows"]["after"][name]
        assert fullscreen["position"] == gate["monitors"][index]["position"]
        assert fullscreen["size"] == gate["monitors"][index]["size"]
        assert not fullscreen["decorated"]
        assert fullscreen["exclusive_monitor"] is None
        for key in ("position", "size", "decorated", "handle", "native_handle"):
            assert after[key] == before[key]


def test_cursor_and_backend(gate):
    assert gate["backend"] == "Glfw - OpenGL3"
    assert gate["windows"]["fullscreen"]["main"]["cursor"] == 0x34002
    assert gate["windows"]["fullscreen"]["info"]["cursor"] == 0x34001
    assert gate["windows"]["after"]["main"]["cursor"] == 0x34001
    for name in ("main", "info"):
        assert gate["swaps"][name]["interval_requested"] == 1
        assert len(gate["swaps"][name]["duration_ms"]) == 3
        assert all(value >= 0 for value in gate["swaps"][name]["duration_ms"])
