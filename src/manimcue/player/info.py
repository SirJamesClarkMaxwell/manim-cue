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
    """Kolumna miniatur i dwa podglądy zwracają akcje bez bezpośredniej nawigacji."""
    from imgui_bundle import imgui, imgui_md

    actions = []
    style = imgui.get_style()
    thumbnail_width, thumbnail_height = (
        128 * style.font_size_base / 16,
        72 * style.font_size_base / 16,
    )
    view_state = preview.setdefault("view_state", {})
    target = tuple(snapshot["index"])
    target_changed = view_state.get("thumbnail_target") != target
    view_state["thumbnail_target"] = target
    imgui.begin_child(
        "presenter_thumbnails",
        (
            thumbnail_width
            + 2 * style.frame_padding.x
            + 2 * style.window_padding.x
            + style.scrollbar_size,
            0,
        ),
        child_flags=imgui.ChildFlags_.always_use_window_padding,
        window_flags=imgui.WindowFlags_.always_vertical_scrollbar,
    )
    deck, current = snapshot["index"]
    slides = snapshot["manifest"]["presentations"][deck]["slides"]
    visible = []
    for index in range(len(slides)):
        label = f"{'> ' if index == current else ''}{index + 1}##slide_{index}"
        thumbnail = snapshot.get("thumbnails", {}).get(index, {})
        texture = thumbnail.get("texture")
        clicked = (
            imgui.image_button(
                label, imgui.ImTextureRef(texture), (thumbnail_width, thumbnail_height)
            )
            if texture is not None
            else imgui.button(label, (thumbnail_width, thumbnail_height))
        )
        item_visible = imgui.is_item_visible()
        if item_visible:
            visible.append(index)
        if index == current and target_changed and not item_visible:
            imgui.set_scroll_here_y()
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
    imgui.same_line()
    imgui.begin_child("presenter_details", (0, 0))
    imgui.text_wrapped(state_text(snapshot))
    available = imgui.get_content_region_avail()
    height = max(1, available.y)
    spacing = imgui.get_style().item_spacing.x
    left = max(1, (available.x - spacing) * 0.6)
    imgui.begin_child("presenter_current", (left, height))
    imgui.text(f"{datetime.now():%H:%M:%S} · elapsed {snapshot.get('elapsed', 0):.1f} s")
    paused = snapshot.get("presenter_timer", {}).get("paused", False)
    if imgui.button("Wznów czas" if paused else "Pauza czasu"):
        actions.append({"type": "timer_pause"})
    if imgui.get_content_region_avail().x - imgui.get_item_rect_size().x >= (
        imgui.calc_text_size("Restart czasu").x + 2 * style.frame_padding.x + style.item_spacing.x
    ):
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
    if preview.get("runtime"):
        if imgui.button("Podgląd" if view_state.get("editing") else "Edytuj"):
            if view_state.get("editing"):
                flush_notes(preview["runtime"], preview["now"])
                view_state["editing_markdown"] = False
                view_state["popup"] = []
            view_state["editing"] = not view_state.get("editing")
        imgui.same_line()
    imgui.text(f"{snapshot.get('notes_size', 28)} px")
    imgui.begin_child(
        "presenter_notes", (0, 0), window_flags=imgui.WindowFlags_.always_vertical_scrollbar
    )
    imgui.push_font(None, imgui.get_style().font_size_base * snapshot.get("notes_size", 28) / 16)
    try:
        render_notes = preview.get("render_notes")
        status = render_notes_status(snapshot, preview) if preview.get("runtime") else None
        if view_state.get("editing") and preview.get("runtime"):
            render_editor(snapshot, preview, status)
        elif render_notes:
            render_notes(snapshot.get("notes", ""), snapshot.get("notes_size", 28))
        else:
            imgui_md.render(snapshot.get("notes", ""))
    finally:
        imgui.pop_font()
    imgui.end_child()
    imgui.end_child()
    imgui.end_child()
    return actions


def editor_text(editor):
    """get_text gubi rozróżnienie ostatniego pustego wiersza."""
    return "\n".join(editor.get_line_text(i) for i in range(editor.get_line_count()))


def refresh_notes(manifest, path, overlay):
    from .notes_overlay import apply, canonical_path

    for deck in manifest["presentations"]:
        if deck.get("notes_file") and canonical_path(deck["notes_file"]) == canonical_path(path):
            notes, _ = apply([slide.get("rendered_notes", "") for slide in deck["slides"]], overlay)
            for slide, text in zip(deck["slides"], notes):
                slide["notes"] = text


def capture_notes(runtime, now):
    from .notes_overlay import validate_text

    state = runtime.get("notes_edit", {})
    if not state.get("target"):
        return
    text = editor_text(state["editor"])
    if text != state["text"]:
        state["text"], state["changed"] = text, now
        try:
            validate_text(text)
        except ValueError as error:
            state["status"] = str(error)
            state["invalid"] = True
            return
        state["invalid"] = False
        path, number = state["target"]
        runtime["dirty_notes"].set(path, number, text)
        state["status"] = "zapisywanie…"


def flush_notes(runtime, now, *, exiting=False):
    """Każdy wyzwalacz czyta widget przed próbą zapisu wszystkich zachowanych buforów."""
    import sys

    from .notes_overlay import canonical_path, read_overlay

    capture_notes(runtime, now)
    state = runtime.get("notes_edit", {})
    dirty = runtime["dirty_notes"]
    manifest = runtime["app"].manifest
    paths = dict.fromkeys(path for path, _ in dirty.buffers)
    for path in paths:
        deck = next(
            d
            for d in manifest["presentations"]
            if d.get("notes_file") and canonical_path(d["notes_file"]) == path
        )
        rendered = [slide.get("rendered_notes", "") for slide in deck["slides"]]
        try:
            dirty.flush(path, rendered)
            runtime.get("notes_overlays", {}).pop(path, None)
            refresh_notes(manifest, path, read_overlay(path))
            if not state.get("invalid"):
                state["status"] = "zapisano"
        except (OSError, ValueError) as error:
            state["status"] = str(error)
            if exiting:
                target, text = dirty.rescue(path, rendered)
                if target is None:
                    from imgui_bundle import imgui

                    print(text, file=sys.stderr)
                    imgui.set_clipboard_text(text)
                    print("Ratunek notatek: stderr i schowek", file=sys.stderr)
                else:
                    print(f"Ratunek notatek: {target}", file=sys.stderr)
    state["changed"] = None


def enter_notes(runtime, index, now):
    """Jedno wejście na slajd resetuje undo, nigdy nie tworzy brudnego bufora."""
    from imgui_bundle import imgui_color_text_edit as edit

    deck_index, slide_index = index
    deck = runtime["app"].manifest["presentations"][deck_index]
    path = deck.get("notes_file")
    state = runtime.setdefault("notes_edit", {})
    target = (path, slide_index + 1) if path else None
    if state.get("index") == tuple(index) and state.get("target") == target:
        return state
    flush_notes(runtime, now)
    editor = state.get("editor")
    if editor is None:
        editor = edit.TextEditor()
        editor.set_language(edit.TextEditor.Language.markdown())
        editor.set_word_wrap_enabled(True)
        editor.set_show_line_numbers_enabled(False)
        editor.set_palette(edit.TextEditor.get_dark_palette())
    text = (
        runtime["dirty_notes"]
        .pending(path)
        .get(slide_index + 1, deck["slides"][slide_index].get("notes", ""))
        if path
        else deck["slides"][slide_index].get("notes", "")
    )
    editor.set_text(text)
    state.update(
        editor=editor,
        index=tuple(index),
        target=target,
        text=text,
        changed=None,
        invalid=False,
        status=state.get("status", "zapisano") if runtime["dirty_notes"].buffers else "zapisano",
        popup=[],
        focus=False,
    )
    return state


def replace_notes(editor, replacement):
    from imgui_bundle import imgui_color_text_edit as edit

    start, end, text, cursor = replacement
    editor.replace_section_text(edit.TextEditor.DocPos(*start), edit.TextEditor.DocPos(*end), text)
    editor.set_cursor(edit.TextEditor.DocPos(*cursor))


def render_notes_status(snapshot, preview):
    """Adapter widgetu: trwałe bufory są w runtime, fokus i popup należą do widoku."""
    from pathlib import Path

    from imgui_bundle import imgui

    from . import notes_complete as complete
    from .notes_overlay import notes_hash, read_overlay, save_overlay

    runtime, now = preview["runtime"], preview["now"]
    view = preview["view_state"]
    previous = runtime.get("notes_edit", {}).get("index")
    state = enter_notes(runtime, snapshot["index"], now)
    if previous != tuple(snapshot["index"]):
        view["popup"] = []
        view.pop("signature", None)
        view.pop("dismissed", None)
    editor = state["editor"]
    deck = runtime["app"].manifest["presentations"][snapshot["index"][0]]
    path = deck.get("notes_file")
    blocked = not path
    if path:
        try:
            # Odczyt pliku raz, nie co klatkę (D46); zapis i „Zastosuj” unieważniają cache.
            cache = runtime.setdefault("notes_overlays", {})
            if path not in cache:
                cache[path] = read_overlay(path), Path(path).exists()
            overlay, exists = cache[path]
            if overlay.read_only:
                blocked = True
                imgui.text_wrapped("Tylko do odczytu: " + "; ".join(overlay.errors))
            elif exists and overlay.count != len(deck["slides"]):
                blocked = True
                imgui.text_wrapped(
                    f"nakładka wstrzymana: było {overlay.count} slajdów, jest {len(deck['slides'])}"
                )
                if imgui.button("Zastosuj do obecnych slajdów"):
                    updated = save_overlay(
                        path,
                        [s.get("rendered_notes", "") for s in deck["slides"]],
                        {},
                        acknowledge=True,
                    )
                    refresh_notes(runtime["app"].manifest, path, updated)
                    cache.pop(path, None)
                    state.pop("index", None)
                    state = enter_notes(runtime, snapshot["index"], now)
            else:
                slide = deck["slides"][snapshot["index"][1]]
                number = snapshot["index"][1] + 1
                if any(
                    s.number == number
                    and s.base.lower() != notes_hash(slide.get("rendered_notes", ""))
                    for s in overlay.sections
                ):
                    imgui.text_wrapped("notatki w kodzie zmienione po edycji")
                    imgui.begin_disabled(editor.get_number_of_cursors() != 1)
                    if imgui.button("Z renderu"):
                        view["editing"] = True
                        text = editor_text(editor)
                        replace_notes(
                            editor,
                            (
                                (0, 0),
                                complete.position(text, len(text)),
                                slide.get("rendered_notes", ""),
                                (0, 0),
                            ),
                        )
                    imgui.end_disabled()
        except (OSError, ValueError) as error:
            blocked = True
            state["status"] = str(error)
    else:
        imgui.text_wrapped("Tylko do odczytu: brak pliku notatek")
    imgui.text_wrapped(state["status"])
    return state, blocked


def render_editor(snapshot, preview, status=None):
    from imgui_bundle import imgui

    from . import notes_complete as complete

    runtime, now = preview["runtime"], preview["now"]
    view = preview["view_state"]
    state, blocked = status if status is not None else render_notes_status(snapshot, preview)
    editor = state["editor"]
    editor.set_read_only_enabled(blocked)
    io = imgui.get_io()
    owner = imgui.get_id("notes-completion-owner")
    keys = (
        imgui.Key.up_arrow,
        imgui.Key.down_arrow,
        imgui.Key.enter,
        imgui.Key.tab,
        imgui.Key.escape,
    )
    if blocked or editor.get_number_of_cursors() != 1 or io.app_focus_lost:
        view["popup"] = []
    popup = view.get("popup", []) if view.get("editing_markdown") else []
    consumed = view.setdefault("consumed", set())
    accepted = None
    if popup:
        for key in keys:
            if imgui.internal.is_key_pressed(key, imgui.InputFlags_.repeat, owner):
                choice = view.get("choice", 0)
                if key in (imgui.Key.up_arrow, imgui.Key.down_arrow):
                    view["choice"] = (choice + (1 if key == imgui.Key.down_arrow else -1)) % len(
                        popup
                    )
                else:
                    if key != imgui.Key.escape:
                        accepted = popup[choice % len(popup)]
                    consumed.add(key)
                    view["dismissed"] = view.get("signature")
                    view["popup"] = []
                    editor.set_focus()
            imgui.internal.set_key_owner(
                key, owner, imgui.internal.InputFlagsPrivate_.lock_this_frame
            )
    elif view.get("editing_markdown") and imgui.is_key_pressed(imgui.Key.escape):
        imgui.set_window_focus(None)
    for key in list(consumed):
        if imgui.is_key_down(key):
            imgui.internal.set_key_owner(
                key, owner, imgui.internal.InputFlagsPrivate_.lock_this_frame
            )
        else:
            consumed.remove(key)
    explicit = False
    if view.get("editing_markdown") and not blocked:
        for name in ("b", "i", "space"):
            template = complete.shortcut(
                name, io.key_ctrl, io.key_alt, editor.get_number_of_cursors()
            )
            key = getattr(imgui.Key, name)
            if template and imgui.is_key_pressed(key):
                imgui.internal.set_key_owner(
                    key, owner, imgui.internal.InputFlagsPrivate_.lock_this_frame
                )
                if template == "popup":
                    explicit = True
                    view.pop("dismissed", None)
                else:
                    text = editor_text(editor)
                    selection = editor.get_cursor_selection(0)
                    bounds = (
                        complete.offset(text, (selection.start.line, selection.start.index)),
                        complete.offset(text, (selection.end.line, selection.end.index)),
                    )
                    replace_notes(
                        editor, complete.insertion(text, *bounds, template, selection=bounds)
                    )
    if accepted:
        text = editor_text(editor)
        _, start, end, template = accepted
        selection = view.get("selection")
        replace_notes(editor, complete.insertion(text, start, end, template, selection=selection))
        cursor = editor.get_cursor_position(0)
        view["dismissed"] = (editor_text(editor), cursor.line, cursor.index)
    visible = imgui.begin_child("notes-editor-host", (0, 0))
    if visible:
        imgui.push_font(runtime.get("editor_font"), snapshot.get("notes_size", 28))
        editor.render("notes-editor", (0, 0), True)
        imgui.pop_font()
        focused = imgui.is_window_focused(imgui.FocusedFlags_.child_windows)
        view["editing_markdown"] = focused and not io.app_focus_lost
        text = editor_text(editor)
        cursor = editor.get_cursor_position(0)
        signature = (text, cursor.line, cursor.index)
        if signature != view.get("signature") or explicit:
            view["signature"] = signature
            view["choice"] = 0
            selection = editor.get_cursor_selection(0)
            view["selection"] = (
                (
                    complete.offset(text, (selection.start.line, selection.start.index)),
                    complete.offset(text, (selection.end.line, selection.end.index)),
                )
                if explicit
                else None
            )
            view["popup"] = (
                complete.suggestions(
                    text,
                    (cursor.line, cursor.index),
                    explicit=explicit,
                    cursors=editor.get_number_of_cursors(),
                )
                if focused and not blocked
                else []
            )
        if view.get("dismissed") == signature:
            view["popup"] = []
        popup = view.get("popup", [])
        if (
            popup
            and view.get("dismissed") != signature
            and editor.is_doc_pos_visible(cursor)
            and not io.app_focus_lost
        ):
            point = editor.doc_pos2_screen_pos(cursor)
            imgui.set_next_window_pos((point.x, point.y + snapshot.get("notes_size", 28)))
            imgui.set_next_window_viewport(imgui.get_window_viewport().id_)
            imgui.begin(
                "Podpowiedzi##notes",
                flags=imgui.WindowFlags_.no_focus_on_appearing
                | imgui.WindowFlags_.always_auto_resize,
            )
            imgui.internal.bring_window_to_display_front(imgui.internal.get_current_window())
            view["editing_markdown"] |= imgui.is_window_focused()
            if not view["editing_markdown"]:
                view["popup"] = []
            for index, item in enumerate(popup):
                clicked, _ = imgui.selectable(item[0], index == view.get("choice", 0))
                if clicked:
                    _, start, end, template = item
                    replace_notes(
                        editor,
                        complete.insertion(
                            text, start, end, template, selection=view.get("selection")
                        ),
                    )
                    view["popup"] = []
                    cursor = editor.get_cursor_position(0)
                    view["dismissed"] = (editor_text(editor), cursor.line, cursor.index)
                    editor.set_focus()
            imgui.end()
    else:
        view["editing_markdown"] = False
    imgui.end_child()
    autosave_notes(runtime, now)


def autosave_notes(runtime, now):
    capture_notes(runtime, now)
    state = runtime.get("notes_edit", {})
    if (
        state.get("changed") is not None
        and not state.get("invalid")
        and now - state["changed"] >= 0.5
    ):
        flush_notes(runtime, now)
