"""Oddzielny interpreter sprawdza importy; Pyodide jest obowiązkową bramką."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "experiments/f10a_gate/imports.py"


def test_pc_shared_imports():
    process = subprocess.run(
        [sys.executable, "-I", str(GATE), "--pc"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    result = json.loads(process.stdout)
    assert result["forbidden_imports"] == []
    assert set(result["cases"]) == {
        "clock_pause",
        "navigation_table",
        "geometry_clip",
        "stale_entry",
        "manifest_validation",
    }


def test_pyodide_shared_imports(tmp_path):
    output = tmp_path / "imports.json"
    process = subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "--with",
            "playwright",
            "python",
            str(GATE),
            "--channel",
            "msedge",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        env={**os.environ, "UV_NO_SYNC": "1"},
        capture_output=True,
        text=True,
        check=False,
        timeout=150,
    )
    assert process.returncode == 0, process.stderr or process.stdout
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "ok"
    assert result["pc"] == result["pyodide"]
