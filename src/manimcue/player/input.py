"""Czysty router zdarzeń obu okien, niezależny od backendu GUI."""

from .geometry import hit_test
from .keys import bindings


def route(event: dict, state: dict) -> list[dict]:
    """Zachowaj pierwszeństwo edycji, rezerwacji i cue przed akcjami playera."""
    kind = event.get("type")
    if kind == "close":
        return [{"type": "quit"}]
    if kind == "activity":
        return [] if event.get("application_active", True) else [{"type": "release_focus"}]
    if state.get("editing_text") or state.get("editing_markdown"):
        return []
    if kind == "click":
        target = hit_test(state.get("commands", []), event["point"])
        live = state.get("live_indices", [])
        return (
            [{"type": "focus_live", "index": target}]
            if target in live
            else [{"type": "release_focus"}]
        )
    if kind in ("drag", "wheel", "double_click"):
        if state.get("reserved") or state.get("active_live") is None:
            return []
        if kind == "drag" and not event.get("shift") and not event.get("orbit", True):
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
    if state.get("active_live") is not None and action in ("next", "previous"):
        if state.get("reserved") or event.get("repeat"):
            return []
        return [{"type": "cue", "direction": "next" if action == "next" else "back"}]
    return [{"type": action}]
