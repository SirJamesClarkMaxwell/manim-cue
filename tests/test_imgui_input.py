"""Testy priorytetów wejścia bez kontekstu ImGui."""

import pytest

from manimcue.player.input import route
from manimcue.player.keys import DEFAULT_KEYS, QT_KEYS, QT_TO_IMGUI, bindings


@pytest.mark.parametrize("action,name", DEFAULT_KEYS.items())
def test_actions(action, name):
    expected = "pause" if action == "PLAY_PAUSE" else action.lower()
    event = {"type": "key", "key": QT_TO_IMGUI[QT_KEYS[name]]}
    assert route(event, {}) == [{"type": expected}]
    assert route({**event, "repeat": True}, {}) == [{"type": expected}]
    assert route(event, {"editing_text": True}) == []
    assert route(event, {"reserved": True}) == [{"type": expected}]
    assert route({**event, "modifiers": ["ctrl", "shift"]}, {}) == [{"type": expected}]


def test_live_priority_and_repeat():
    event = {"type": "key", "key": "right_arrow"}
    state = {"active_live": "scene"}
    assert route(event, state) == [{"type": "cue", "direction": "next"}]
    assert route({**event, "repeat": True}, state) == []
    assert route(event, {**state, "reserved": True}) == []
    assert route({"type": "key", "key": "escape"}, state) == [{"type": "release_focus"}]
    assert route({"type": "close"}, {"editing_text": True}) == [{"type": "quit"}]


def test_plus_asterisk_modifiers():
    state = {"bindings": bindings({"NEXT": {"ids": [43]}, "PREVIOUS": {"ids": [42]}})}
    for key, modifiers, action in [
        ("equal", ["shift"], "next"),
        ("keypad_add", [], "next"),
        ("_8", ["shift"], "previous"),
        ("keypad_multiply", [], "previous"),
    ]:
        assert route({"type": "key", "key": key, "modifiers": modifiers}, state) == [
            {"type": action}
        ]
    assert route({"type": "key", "key": "equal"}, state) == []
    assert route({"type": "key", "key": "equal", "modifiers": ["shift", "ctrl"]}, state) == [
        {"type": "next"}
    ]


def test_custom_live_bindings_and_focus_both_windows():
    state = {"active_live": "scene", "config": {"NEXT": {"ids": [ord("T")]}}}
    for window in ("main", "info"):
        assert route({"type": "key", "key": "t", "window": window}, state) == [
            {"type": "cue", "direction": "next"}
        ]
    assert route({"type": "key", "key": "right_arrow"}, state) == []
    assert route({"type": "activity", "application_active": True}, state) == []
    assert route({"type": "activity", "application_active": False}, state) == [
        {"type": "release_focus"}
    ]


def test_margin_blocks_and_view_normalization():
    from manimcue.player.live import view

    commands = [
        {"source": "0", "container": (0, 0, 100, 100), "clip": (0, 0, 100, 100)},
        {"source": "1", "container": (20, 20, 50, 50), "clip": (20, 20, 50, 50)},
    ]
    state = {"commands": commands, "live_indices": ["0"]}
    assert route({"type": "click", "point": (30, 30)}, state) == [{"type": "release_focus"}]
    assert route({"type": "click", "point": (10, 10)}, state) == [
        {"type": "focus_live", "index": "0"}
    ]
    event = {"type": "drag", "delta": (10, -20), "shift": True}
    assert view(event, (0, 0, 100, 200)) == {"command": "view pan 0.10000 -0.10000"}
    assert view({**event, "engine": "ce-cairo"}, (0, 0, 100, 200)) == {}
    assert route(event, {"active_live": "0", "reserved": True}) == []
    assert view({"type": "wheel", "steps": 2}, (0, 0, 1, 1)) == {"command": "view zoom 2"}
    assert view({"type": "double_click"}, (0, 0, 1, 1)) == {"command": "view reset"}
