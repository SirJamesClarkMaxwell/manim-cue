"""Info korzysta z tego samego snapshotu co nakładka S."""

from copy import deepcopy
from datetime import datetime


def preview_target(manifest: dict, index: tuple) -> dict | None:
    """Następny normalny slajd, także przez granicę decku; live tylko miniatura."""
    deck, slide = index
    decks = manifest["presentations"]
    slide += 1
    if slide == len(decks[deck]["slides"]):
        deck, slide = deck + 1, 0
    if deck >= len(decks):
        return None
    result = deepcopy(decks[deck]["slides"][slide])
    result["resolution"] = list(decks[deck].get("resolution", manifest["resolution"]))
    result["index"] = [deck, slide]
    return result


def state_text(snapshot: dict) -> str:
    """Jeden opis stanu dla Info oraz S; degradacja ma pierwszeństwo nad READY."""
    deck, slide = snapshot["index"]
    phase = (
        "przygotowanie"
        if snapshot["preparing"]
        else "koniec"
        if snapshot["ended"]
        else "pauza"
        if snapshot["paused"]
        else "odtwarzanie"
    )
    flags = [
        f"scena {deck + 1}, slajd {slide + 1}",
        phase,
        "reverse" if snapshot["reverse"] else "normalny",
        ("start zamówiony" if snapshot["requested_playing"] else "start w pauzie")
        if snapshot["preparing"]
        else "",
        f"fokus: {'slajdy' if snapshot.get('active_live') is None else 'live ' + str(snapshot['active_live'] + 1)}",
    ]
    if snapshot.get("loop"):
        flags.append("pętla")
    for clip in snapshot.get("clips", []):
        flags.append(f"klip {clip['index']}: {clip.get('error') or clip['status']}")
    for name in ("loop_exit_requested", "termination_achieved"):
        if snapshot.get(name):
            flags.append(name)
    for history in snapshot.get("histories", []):
        flags.append(history.get("degraded") or history.get("status", ""))
        flags.extend(history.get("cue_states", []))
    flags.extend(snapshot.get("errors", []))
    return " · ".join(str(value) for value in flags if value)


def timer_elapsed(state: dict, now: float) -> float:
    """Czas prelegenta ma własną kotwicę monotoniczną."""
    return state["elapsed"] + (0 if state["paused"] else max(0, now - state["anchor"]))


def update_timer(state: dict, action: str, now: float) -> dict:
    """Restart zachowuje pauzę, przełączenie pauzy zachowuje upływ czasu."""
    result = dict(state)
    result["elapsed"] = 0 if action == "timer_restart" else timer_elapsed(state, now)
    result["anchor"] = now
    if action == "timer_pause":
        result["paused"] = not state["paused"]
    return result


def render_info(snapshot: dict, preview: dict) -> list[dict]:
    """Dwie kolumny i kontrolki zwracają akcje, bez bezpośredniej nawigacji."""
    from imgui_bundle import imgui, imgui_md

    actions = []
    imgui.text_wrapped(state_text(snapshot))
    available = imgui.get_content_region_avail()
    height = max(100, available.y - 110)
    spacing = imgui.get_style().item_spacing.x
    left = max(1, (available.x - spacing) * 0.6)
    imgui.begin_child("presenter_current", (left, height))
    imgui.text(f"{datetime.now():%H:%M:%S} · elapsed {snapshot.get('elapsed', 0):.1f} s")
    paused = snapshot.get("presenter_timer", {}).get("paused", False)
    if imgui.button("Wznów czas" if paused else "Pauza czasu"):
        actions.append({"type": "timer_pause"})
    imgui.same_line()
    if imgui.button("Restart czasu"):
        actions.append({"type": "timer_restart"})
    render = preview.get("render")
    if render:
        imgui.text("bieżący")
        render(snapshot.get("composition", []))
    imgui.end_child()
    imgui.same_line()
    imgui.begin_child("presenter_next_notes", (0, height))
    imgui.text("następny")
    if render and preview.get("composition"):
        render(preview.get("composition", []))
    else:
        imgui.text_wrapped("Brak następnego slajdu")
    for label, delta in (("A−", -2), ("A+", 2)):
        if imgui.button(label):
            actions.append({"type": "notes_scale", "delta": delta})
        imgui.same_line()
    imgui.text(f"{snapshot.get('notes_size', 24)} px")
    imgui.begin_child(
        "presenter_notes", (0, 0), window_flags=imgui.WindowFlags_.always_vertical_scrollbar
    )
    imgui.push_font(None, imgui.get_style().font_size_base * snapshot.get("notes_size", 24) / 16)
    try:
        render_notes = preview.get("render_notes")
        if render_notes:
            render_notes(snapshot.get("notes", ""), snapshot.get("notes_size", 24))
        else:
            imgui_md.render(snapshot.get("notes", ""))
    finally:
        imgui.pop_font()
    imgui.end_child()
    imgui.end_child()
    imgui.begin_child(
        "presenter_thumbnails", (0, 100), window_flags=imgui.WindowFlags_.horizontal_scrollbar
    )
    deck, current = snapshot["index"]
    slides = snapshot["manifest"]["presentations"][deck]["slides"]
    visible = []
    for index in range(len(slides)):
        if index:
            imgui.same_line()
        label = f"{'▶ ' if index == current else ''}{index + 1}##slide_{index}"
        thumbnail = snapshot.get("thumbnails", {}).get(index, {})
        texture = thumbnail.get("texture")
        clicked = (
            imgui.image_button(label, imgui.ImTextureRef(texture), (128, 72))
            if texture is not None
            else imgui.button(label, (128, 72))
        )
        if imgui.is_item_visible():
            visible.append(index)
        if texture is not None:
            a, b = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            draw_list = imgui.get_window_draw_list()
            if index == current:
                draw_list.add_rect(a, b, 0xFF00C8FF, thickness=2)
            draw_list.add_rect_filled(a, (a.x + 28, a.y + 20), 0xCC000000)
            draw_list.add_text(a, 0xFFFFFFFF, str(index + 1))
        if clicked:
            actions.append({"type": "start_at", "index": [deck, index]})
    if visible:
        actions.append(
            {
                "type": "thumbnail_range",
                "indices": list(range(max(0, visible[0] - 1), min(len(slides), visible[-1] + 2))),
            }
        )
    imgui.end_child()
    return actions
