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


def render_info(snapshot: dict, preview: dict) -> None:
    """Markdown i czasy Info nie zależą od pauzy mediów."""
    from imgui_bundle import imgui, imgui_md

    imgui.text_wrapped(state_text(snapshot))
    imgui.text(f"{datetime.now():%H:%M:%S} · elapsed {snapshot.get('elapsed', 0):.1f} s")
    imgui_md.render(snapshot.get("notes", ""))
    render = preview.get("render")
    if render:
        imgui.text("bieżący")
        render(snapshot.get("composition", []))
        imgui.text("następny")
        render(preview.get("composition", []))
