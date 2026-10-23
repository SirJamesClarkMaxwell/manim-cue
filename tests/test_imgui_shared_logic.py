"""Nazwane przypadki bramki wykonywane z tego samego źródła na PC/Pyodide."""

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "experiments/f10a_gate/imports.py"
SPEC = importlib.util.spec_from_file_location("f10_shared_cases", PATH)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


@pytest.mark.parametrize(
    "name",
    [
        "clock_pause",
        "navigation_table",
        "geometry_clip",
        "stale_entry",
        "manifest_validation",
    ],
)
def test_shared_case(name):
    assert GATE.run_shared_cases()[name]
