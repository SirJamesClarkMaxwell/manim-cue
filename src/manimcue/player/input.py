"""Czysty router zdarzeń obu okien, niezależny od backendu GUI."""

from .geometry import hit_test
from .keys import bindings


def gesture_mode(button: str, shift: bool = False, alt: bool = False) -> str | None:
    """Wspólna macierz myszy i touchpada dla Qt oraz ImGui."""
    if button == "middle" or button == "left" and alt:
        return "pan" if shift else "orbit"
    if button == "right" and alt:
        return "zoom"
    return None


def route(event: dict, state: dict) -> list[dict]:
    """Zachowaj pierwszeństwo edycji, rezerwacji i cue przed akcjami playera."""
    kind = event.get("type")
    if kind == "close":
        return [{"type": "quit"}]
    if kind == "activity":
        return [] if event.get("application_active", True) else [{"type": "release_focus"}]
    capture = state.get("capture")
    if kind == "pointer_up":
        return [{"type": "release_pointer"}]
    if (
        capture
        and kind in ("click", "drag", "wheel", "double_click")
        and (
            state.get("reserved")
            or capture.get("entry_id") != state.get("entry_id")
            or capture.get("index") != state.get("active_live")
        )
    ):
        return [{"type": "release_pointer"}]
    if state.get("editing_text") or state.get("editing_markdown"):
        return []
    if kind == "click":
        target = hit_test(state.get("commands", []), event["point"])
        live = state.get("live_indices", [])
        buttons = event.get("buttons", [event.get("button", "left")])
        if len(buttons) != 1:
            return [{"type": "release_pointer"}]
        mode = gesture_mode(buttons[0], event.get("shift", False), event.get("alt", False))
        if (
            mode
            and target in live
            and target == state.get("active_live")
            and not state.get("reserved")
        ):
            return [
                {
                    "type": "capture_pointer",
                    "index": target,
                    "button": buttons[0],
                    "mode": mode,
                    "entry_id": state.get("entry_id"),
                }
            ]
        return (
            [{"type": "focus_live", "index": target}]
            if target in live
            else [{"type": "release_focus"}]
        )
    if kind in ("drag", "wheel", "double_click"):
        if state.get("reserved") or state.get("active_live") is None:
            return []
        if kind == "drag":
            if not capture:
                return []
            if len(event.get("buttons", [capture["button"]])) != 1:
                return [{"type": "release_pointer"}]
            event = {**event, "mode": capture["mode"]}
        elif (
            (
                hit_test(state.get("commands", []), event.get("point", (-1, -1)))
                != state["active_live"]
            )
            or kind == "double_click"
            and (event.get("button", "left") != "left" or event.get("alt"))
        ):
            return []
        return [{**event, "type": "view", "gesture": kind}]
    if kind != "key":
        return []
    key = event.get("key")
    if key == "escape":
        return [{"type": "release_focus"}]
    mapping = state.get("bindings")
    if mapping is None:
        mapping = bindings(state.get("config", {}))
    shifted = "shift" in event.get("modifiers", [])
    if shifted and key in {
        "_0",
        "_1",
        "_2",
        "_3",
        "_4",
        "_5",
        "_6",
        "_7",
        "_9",
        "minus",
        "comma",
        "period",
        "slash",
        "semicolon",
        "apostrophe",
        "left_bracket",
        "right_bracket",
        "backslash",
        "grave_accent",
    }:
        return []
    # TOML przechowuje Qt::Key, bez modyfikatorów; Shift zmienia Plus/Asterisk.
    modifiers = frozenset({"shift"}) if shifted and key in ("equal", "_8") else frozenset()
    action = mapping.get((key, modifiers))
    if action is None:
        return []
    if action in ("next", "previous") and event.get("repeat"):
        return []
    if state.get("active_live") is not None and action in ("next", "previous"):
        if state.get("reserved") or event.get("repeat"):
            return []
        return [{"type": "cue", "direction": "next" if action == "next" else "back"}]
    return [{"type": action}]
