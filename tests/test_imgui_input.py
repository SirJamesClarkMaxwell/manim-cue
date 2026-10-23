"""Testy priorytetów wejścia bez kontekstu ImGui."""

import pytest

from manimcue.player.input import route
from manimcue.player.keys import DEFAULT_KEYS, QT_KEYS, QT_TO_IMGUI, bindings


@pytest.fixture
def qt_gestures():
    from types import SimpleNamespace

    from qtpy.QtCore import QRectF
    from test_imgui_live import Session

    from manimcue.composition import SlideComposition
    from manimcue.live_layers import LiveLayerController
    from manimcue.slides.qt_utils import qapp

    app = qapp()
    composition = SlideComposition((100, 200))
    composition.layer_rects = [QRectF(0, 0, 100, 200)]
    controller = LiveLayerController(composition)
    commands = []
    session = Session()
    session.commands = commands
    controller.sessions = {0: session}
    controller.identities = {0: ("manimgl",)}
    controller.layers = [SimpleNamespace(active_border=None)]
    controller.click(0)
    yield controller, session, commands, app
    controller.timer.stop()


@pytest.mark.parametrize("adapter", ["qt", "imgui"])
@pytest.mark.parametrize(
    "button,shift,alt,expected",
    [
        ("middle", False, False, "view orbit 0.10000 -0.10000"),
        ("middle", True, False, "view pan 0.10000 -0.10000"),
        ("left", False, True, "view orbit 0.10000 -0.10000"),
        ("left", True, True, "view pan 0.10000 -0.10000"),
        ("right", False, True, "view zoom 2"),
        ("left", False, False, None),
        ("left", True, False, None),
        ("right", False, False, None),
    ],
)
def test_gesture_matrix(adapter, button, shift, alt, expected, qt_gestures):
    from qtpy.QtCore import QPointF

    from manimcue.player.live import view

    controller, _, commands, _ = qt_gestures
    if adapter == "qt":
        controller.click(0)
        controller.drag(QPointF(10, 20), shift, button, alt)
        controller.drag(QPointF(20, 0), shift, button, alt)
    else:
        state = {
            "active_live": "0",
            "live_indices": ["0"],
            "entry_id": 1,
            "commands": [{"source": "0", "container": (0, 0, 100, 200), "clip": (0, 0, 100, 200)}],
        }
        effects = route(
            {"type": "click", "point": (10, 20), "button": button, "shift": shift, "alt": alt},
            state,
        )
        capture = next((e for e in effects if e["type"] == "capture_pointer"), None)
        for effect in route({"type": "drag", "delta": (10, -20)}, {**state, "capture": capture}):
            converted = view(effect, (0, 0, 100, 200))
            if converted:
                commands.append(converted["command"])
    assert commands == ([expected] if expected else [])


def test_gesture_focus_capture_cancel():
    state = {
        "active_live": None,
        "live_indices": ["0"],
        "entry_id": 1,
        "commands": [{"source": "0", "container": (0, 0, 100, 100), "clip": (0, 0, 100, 100)}],
    }
    press = {"type": "click", "point": (10, 10), "button": "middle"}
    assert route(press, state) == [{"type": "focus_live", "index": "0"}]
    assert route({"type": "wheel", "point": (10, 10), "steps": 1}, state) == []
    state["active_live"] = "0"
    state["capture"] = route(press, state)[0]
    assert (
        route({"type": "drag", "point": (1000, 1000), "delta": (1, 1)}, state)[0]["type"] == "view"
    )
    for changed in ({"reserved": True}, {"entry_id": 2}, {"active_live": None}):
        assert route({"type": "drag", "delta": (1, 1)}, {**state, **changed}) == [
            {"type": "release_pointer"}
        ]
    assert route({"type": "drag", "buttons": ["middle", "left"]}, state) == [
        {"type": "release_pointer"}
    ]
    assert route({"type": "pointer_up"}, state) == [{"type": "release_pointer"}]


def test_dpi_fps_invariant_and_zero_container():
    from manimcue.player.live import view

    for dpi in (1, 1.5, 2):
        for fps in (30, 60, 144):
            assert view(
                {"type": "drag", "delta": (10, -20), "button": "middle", "dpi": dpi, "fps": fps},
                (0, 0, 100, 200),
            ) == {"command": "view orbit 0.10000 -0.10000"}
    assert view({"type": "wheel", "steps": 1}, (0, 0, 0, 0)) == {}


def test_focus_cancels_navigation_already_waiting_after_ack():
    from manimcue.player.live import LiveController

    controller = LiveController()
    controller.events = [
        {"type": "navigate", "direction": "next", "entry_id": 1},
        {"type": "assigned", "index": 0},
    ]
    controller.cancel_steps()
    assert controller.events == [{"type": "assigned", "index": 0}]


@pytest.mark.parametrize("action,name", DEFAULT_KEYS.items())
def test_actions(action, name):
    expected = "pause" if action == "PLAY_PAUSE" else action.lower()
    event = {"type": "key", "key": QT_TO_IMGUI[QT_KEYS[name]]}
    assert route(event, {}) == [{"type": expected}]
    assert route({**event, "repeat": True}, {}) == (
        [] if expected in ("next", "previous") else [{"type": expected}]
    )
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
