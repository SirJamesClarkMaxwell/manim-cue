"""Testy tłumaczenia kodów Qt na klawisze ImGui."""

import subprocess
import sys

import pytest

imgui = pytest.importorskip("imgui_bundle").imgui

from manimcue.player.keys import QT_KEYS, QT_TO_IMGUI, UnknownKeyError, imgui_key


def test_qt_keys_match_qt():
    """Wartości z tabeli zgadzają się z Qt::Key z qtpy."""
    from qtpy.QtCore import Qt

    for name, code in QT_KEYS.items():
        assert code == getattr(Qt, "Key_" + name), name
    from manimcue.slides.config import key_id

    assert key_id("MediaPlay") == Qt.Key_MediaPlay


def test_default_bindings_map():
    """Domyślne klawisze prezentera mapują się na oczekiwane klawisze ImGui."""
    from manimcue.slides.config import Keys

    expected = {
        "QUIT": "q",
        "PLAY_PAUSE": "space",
        "NEXT": "right_arrow",
        "PREVIOUS": "left_arrow",
        "REVERSE": "v",
        "REPLAY": "r",
        "FULL_SCREEN": "f",
        "HIDE_MOUSE": "h",
        "PRESENTER_STATE": "s",
    }
    keys = Keys()
    for field, attr in expected.items():
        (code,) = getattr(keys, field).ids
        assert imgui_key(code) == getattr(imgui.Key, attr), field


def test_mapped_names_exist_in_imgui():
    """Każda wartość QT_TO_IMGUI to istniejący atrybut imgui.Key."""
    for code, name in QT_TO_IMGUI.items():
        assert hasattr(imgui.Key, name), (code, name)


def test_unknown_code_raises_with_hex():
    """Nieznany kod podnosi UnknownKeyError z kodem w hex."""
    with pytest.raises(UnknownKeyError, match="0x1FFFFFF"):
        imgui_key(0x01FFFFFF)


def test_unmapped_known_name_is_in_message(monkeypatch):
    """Znany klawisz Qt bez odpowiednika w ImGui pojawia się nazwą w komunikacie."""
    # Wszystkie klawisze z QT_KEYS mają odpowiednik, więc usuwamy jeden wpis na czas testu.
    code = QT_KEYS["Escape"]
    monkeypatch.delitem(QT_TO_IMGUI, code)
    with pytest.raises(UnknownKeyError, match="Escape"):
        imgui_key(code)


def test_import_does_not_load_qt():
    """Import manimcue.player.keys nie ładuje qtpy."""
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, manimcue.player.keys; assert 'qtpy' not in sys.modules",
        ],
        check=True,
    )


def test_config_without_qt_and_numeric_toml(tmp_path):
    script = """
import sys
from pathlib import Path
from manimcue.slides.config import Config
config = Config()
assert not any(n.startswith(('qtpy', 'PySide6', 'PyQt6')) for n in sys.modules)
path = Path(sys.argv[1])
config.to_file(path)
assert Config.from_file(path) == config
assert '16777236' in path.read_text()
"""
    subprocess.run([sys.executable, "-c", script, str(tmp_path / "keys.toml")], check=True)


def test_bindings_custom_unknown():
    from manimcue.player.keys import bindings

    assert bindings({"NEXT": {"ids": [ord("T")]}})[("t", frozenset())] == "next"
    with pytest.raises(UnknownKeyError, match=r"NEXT.*33554431.*0x1FFFFFF"):
        bindings({"NEXT": {"ids": [0x1FFFFFF]}})
