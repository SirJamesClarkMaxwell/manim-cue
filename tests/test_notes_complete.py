"""Edytor bez okien, podpowiedzi w glifach i ratunek po błędach zapisu."""

from types import SimpleNamespace

import pytest
from imgui_bundle import imgui_color_text_edit as edit

from manimcue.player import info
from manimcue.player import notes_complete as complete
from manimcue.player import notes_overlay as overlay


def runtime_for(path):
    deck = {
        "notes_file": str(path),
        "slides": [{"notes": "a", "rendered_notes": "a"}, {"notes": "b", "rendered_notes": "b"}],
    }
    from copy import deepcopy

    return {
        "dirty_notes": overlay.DirtyBuffers(),
        "app": SimpleNamespace(manifest={"presentations": [deck, deepcopy(deck)]}),
    }


def active_notes(runtime, index, now):
    state = info.enter_notes(runtime, index, now)
    if state.get("span") is None:
        info.activate_block(
            {"runtime": runtime, "now": now, "view_state": {}}, (0, len(state["text"]))
        )
    return state


@pytest.mark.parametrize("text", ["", "a", "a\n", "a\n\n"])
def test_enter_does_not_dirty(tmp_path, text):
    runtime = runtime_for(tmp_path / "Scene.notes.md")
    runtime["app"].manifest["presentations"][0]["slides"][0]["notes"] = text
    state = active_notes(runtime, [0, 0], 0)
    info.capture_notes(runtime, 1)
    assert info.editor_text(state["editor"]) == text
    assert not runtime["dirty_notes"].buffers


@pytest.mark.parametrize("reason", ["slide", "preview", "hide", "exit"])
def test_flush_reads_lines_before_delay(tmp_path, reason):
    runtime = runtime_for(tmp_path / "Scene.notes.md")
    state = active_notes(runtime, [0, 0], 0)
    state["editor"].set_text("zażółć\n\n")
    if reason == "slide":
        active_notes(runtime, [0, 1], 0.1)
    else:
        info.flush_notes(runtime, 0.1, exiting=reason == "exit")
    assert overlay.read_overlay(tmp_path / "Scene.notes.md").sections[0].text == "zażółć\n\n"
    assert not runtime["dirty_notes"].buffers
    for deck in runtime["app"].manifest["presentations"]:
        assert deck["slides"][0]["notes"] == "zażółć\n\n"


def test_failure_two_slides_hide_exit_rescue(tmp_path, monkeypatch):
    path = tmp_path / "Scene.notes.md"
    runtime = runtime_for(path)
    state = active_notes(runtime, [0, 0], 0)
    state["editor"].set_text("edycja A")
    monkeypatch.setattr(
        overlay,
        "save_overlay",
        lambda *a, **k: (_ for _ in ()).throw(PermissionError("zablokowany")),
    )
    state = active_notes(runtime, [0, 1], 0.1)
    state["editor"].set_text("edycja B")
    info.flush_notes(runtime, 0.2)
    runtime.pop("notes_edit")
    info.flush_notes(runtime, 0.3, exiting=True)
    rescued = list(tmp_path.glob("*.unsaved-*.md"))
    assert len(rescued) == 1
    assert [s.text for s in overlay.read_overlay(rescued[0]).sections] == ["edycja A", "edycja B"]
    assert not runtime["dirty_notes"].buffers


def test_failed_rescue_stderr_clipboard(tmp_path, monkeypatch, capsys):
    from imgui_bundle import imgui

    runtime = runtime_for(tmp_path / "Scene.notes.md")
    state = active_notes(runtime, [0, 0], 0)
    state["editor"].set_text("gęślą")
    monkeypatch.setattr(
        overlay, "save_overlay", lambda *a, **k: (_ for _ in ()).throw(OSError("błąd"))
    )
    monkeypatch.setattr(overlay, "rescue", lambda *a: (None, "pełny ratunek"))
    copied = []
    monkeypatch.setattr(imgui, "set_clipboard_text", copied.append)
    info.flush_notes(runtime, 0.1, exiting=True)
    assert copied == ["pełny ratunek"]
    assert "pełny ratunek" in capsys.readouterr().err
    assert runtime["dirty_notes"].buffers


def test_reserved_marker_does_not_enter_dirty_buffer(tmp_path):
    runtime = runtime_for(tmp_path / "Scene.notes.md")
    state = active_notes(runtime, [0, 0], 0)
    state["editor"].set_text("<!-- manim-cue coś -->")
    info.capture_notes(runtime, 0.1)
    assert state["invalid"] and not runtime["dirty_notes"].buffers


@pytest.mark.parametrize("prefix", ["#", "-", "*", ">", "1", "`", "$"])
def test_block_triggers(prefix):
    text = "  " + prefix
    assert complete.suggestions(text, (0, len(text)))
    assert not complete.suggestions("tekst " + prefix, (0, 6 + len(prefix)))


@pytest.mark.parametrize(
    "text,cursor", [(r"\fr", 3), (r"\$\fr", 5), (r"`$\fr$`", 5), (r"```$\fr$```", 7)]
)
def test_no_latex_outside_math(text, cursor):
    assert not complete.suggestions(text, (0, cursor))


@pytest.mark.parametrize(
    "text,cursor,expected",
    [
        ("Wzór $\\fr", (0, 9), [r"\frac"]),
        ("$$\nx + \\sq", (1, 7), [r"\sqrt"]),
        ("$a$ i \\fr", (0, 9), []),
        ("cena \\$ i \\fr", (0, 13), []),
    ],
)
def test_latex_in_unclosed_math(text, cursor, expected):
    # Zwykłe pisanie: zamykający $ jeszcze nie istnieje.
    assert [item[0] for item in complete.suggestions(text, cursor)] == expected


def test_latex_prefix_limit_and_unicode_insertion():
    text = "żółć $\\fr$"
    items = complete.suggestions(text, (0, 9))
    assert [item[0] for item in items] == [r"\frac"]
    _, start, end, template = items[0]
    assert complete.insertion(text, start, end, template) == ((0, 6), (0, 9), r"\frac{}{}", (0, 12))
    assert len(complete.suggestions("$\\ $", (0, 2))) == 8
    assert not complete.suggestions(text, (0, 9), cursors=2)


def test_inline_wrap_and_shortcuts():
    assert len(complete.suggestions("", (0, 0), explicit=True)) == 5
    assert complete.insertion("żółć", 0, 4, "**|**", selection=(4, 0)) == (
        (0, 0),
        (0, 4),
        "**żółć**",
        (0, 6),
    )
    assert complete.insertion("", 0, 0, "*|*") == ((0, 0), (0, 0), "**", (0, 1))
    assert complete.shortcut("b", True, False) == "**|**"
    assert complete.shortcut("i", True, False) == "*|*"
    assert complete.shortcut("space", True, False) == "popup"
    assert complete.shortcut("b", True, True) is None
    assert complete.shortcut("i", True, False, 2) is None


def test_math_tokens_compatible():
    from manimcue.player.notes_math import math_tokens

    text = r"`$code$` ```$$code$$``` \$cash $\alpha$ $$\frac{x}{y}$$"
    matches = [
        m for m in complete.TOKEN.finditer(text) if m.group(1) is not None or m.group(2) is not None
    ]
    assert [(m.span(), m.groups()) for m in matches] == [
        (m.span(), m.groups()) for m in math_tokens(text)
    ]


@pytest.mark.parametrize("native", [False, True])
def test_all_latex_renderers(native):
    from pathlib import Path

    import imgui_bundle
    from imgui_bundle import imgui_microtex

    from manimcue.player.notes_math import clear_cache, render_formula

    fonts = Path(imgui_bundle.__file__).parent / "assets" / "fonts" / "latex"
    imgui_microtex.init(str(fonts / "latinmodern-math.clm1"), str(fonts / "latinmodern-math.otf"))
    clear_cache()
    try:
        for label, _, example in complete.LATEX:
            assert render_formula(example, 28, 1, "inline", native=native)["error"] is None, label
    finally:
        clear_cache()


def test_rendered_replacement_one_undo_redo():
    editor = edit.TextEditor()
    editor.set_text("żółć\nłąka")
    editor.set_cursor(edit.TextEditor.DocPos(1, 2))
    info.replace_notes(editor, ((0, 0), (1, 4), "z renderu\n", (0, 0)))
    assert info.editor_text(editor) == "z renderu\n"
    editor.undo()
    assert info.editor_text(editor) == "żółć\nłąka"
    editor.redo()
    assert info.editor_text(editor) == "z renderu\n"


def test_autosave_debounces_last_change(tmp_path):
    runtime = runtime_for(tmp_path / "Scene.notes.md")
    state = active_notes(runtime, [0, 0], 0)
    state["editor"].set_text("pierwsza")
    info.autosave_notes(runtime, 1)
    info.autosave_notes(runtime, 1.499)
    assert not (tmp_path / "Scene.notes.md").exists()
    state["editor"].set_text("druga")
    info.autosave_notes(runtime, 1.5)
    info.autosave_notes(runtime, 1.999)
    assert not (tmp_path / "Scene.notes.md").exists()
    info.autosave_notes(runtime, 2)
    assert overlay.read_overlay(tmp_path / "Scene.notes.md").sections[0].text == "druga"


def test_acknowledge_and_rendered_removes_section(tmp_path):
    path = tmp_path / "Scene.notes.md"
    path.write_text(
        overlay.serialize(overlay.Overlay(1, [overlay.Section(1, "00000000", "nakładka")])),
        encoding="utf-8",
    )
    runtime = runtime_for(path)
    updated = overlay.save_overlay(path, ["a", "b"], {}, acknowledge=True)
    info.refresh_notes(runtime["app"].manifest, path, updated)
    assert all(
        d["slides"][0]["notes"] == "nakładka" for d in runtime["app"].manifest["presentations"]
    )
    state = active_notes(runtime, [0, 0], 0)
    info.replace_notes(state["editor"], ((0, 0), (0, 8), "a", (0, 1)))
    info.flush_notes(runtime, 0.1)
    assert not overlay.read_overlay(path).sections


def test_editor_widget_without_windows(tmp_path):
    from imgui_bundle import imgui

    runtime = runtime_for(tmp_path / "Scene.notes.md")
    preview = {"runtime": runtime, "now": 0, "view_state": {}}
    active_notes(runtime, [0, 0], 0)
    context = imgui.create_context()
    try:
        io = imgui.get_io()
        io.display_size = (960, 800)
        io.delta_time = 1 / 60
        io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
        io.set_ini_filename(None)
        for index in range(3):
            imgui.new_frame()
            imgui.set_next_window_size((800, 700))
            imgui.begin("Info")
            info.render_editor({"index": [0, 0], "notes_size": 28}, preview)
            if index == 0:
                runtime["notes_edit"]["editor"].set_text("$\\fr$ żółć")
                runtime["notes_edit"]["editor"].set_cursor(edit.TextEditor.DocPos(0, 4))
                runtime["notes_edit"]["editor"].set_focus()
            imgui.end()
            imgui.render()
            for texture in imgui.get_platform_io().textures:
                if texture.status == imgui.ImTextureStatus.want_create:
                    texture.set_tex_id(99)
                    texture.set_status(imgui.ImTextureStatus.ok)
        assert preview["view_state"].get("popup")
        editor = runtime["notes_edit"]["editor"]
        original = info.editor_text(editor)
        cursor = editor.get_cursor_position(0)
        before = (cursor.line, cursor.index)
        for key in (imgui.Key.down_arrow, imgui.Key.up_arrow, imgui.Key.escape):
            io.add_key_event(key, True)
            imgui.new_frame()
            imgui.begin("Info")
            info.render_editor({"index": [0, 0], "notes_size": 28}, preview)
            imgui.end()
            imgui.render()
            assert info.editor_text(editor) == original
            cursor = editor.get_cursor_position(0)
            assert (cursor.line, cursor.index) == before
            io.add_key_event(key, False)
            imgui.new_frame()
            imgui.begin("Info")
            info.render_editor({"index": [0, 0], "notes_size": 28}, preview)
            imgui.end()
            imgui.render()
        assert not preview["view_state"].get("popup")
        assert runtime["dirty_notes"].pending(tmp_path / "Scene.notes.md") == {1: "$\\fr$ żółć"}
    finally:
        imgui.destroy_context(context)


@pytest.mark.parametrize(
    "event",
    [
        {"type": "key", "key": "q"},
        {"type": "key", "key": "right_arrow"},
        {"type": "key", "key": "space"},
        {"type": "click", "point": (0, 0)},
        {"type": "wheel", "point": (0, 0), "steps": 1},
        {"type": "drag", "buttons": ["left"], "delta": (1, 1)},
    ],
)
def test_editing_markdown_blocks_router(event):
    from manimcue.player.input import route

    assert route(event, {"editing_markdown": True}) == []


@pytest.mark.parametrize("hide", [True, False])
def test_desktop_flush_and_focus_invalidation(tmp_path, monkeypatch, hide):
    from imgui_bundle import imgui, immapp
    from test_imgui_info import FakeSource, manifest

    from manimcue.player import desktop
    from manimcue.player.app import App

    class Windows:
        def __init__(self):
            self.monitors = [(0, 0, 1000, 800)]
            self.handles = {}
            self.close_requested = False

        def attach(self, name, handle, monitor):
            self.handles[name] = handle

    applications, states, runtimes = [], [], []
    path = tmp_path / "Scene.notes.md"
    model = manifest()
    model["presentations"][0]["notes_file"] = str(path)
    model["presentations"][0]["slides"][0]["rendered_notes"] = "**notes**"

    def make_app(model, options):
        app = App(
            model, options, FakeSource, lambda _: SimpleNamespace(texture=1, close=lambda: None)
        )
        applications.append(app)
        return app

    def render(snapshot, preview):
        runtime = preview["runtime"]
        runtimes.append(runtime)
        view = preview["view_state"]
        if not runtime.get("notes_edit"):
            state = active_notes(runtime, [0, 0], preview["now"])
            state["editor"].set_text("edycja przed flush")
        view["editing_markdown"] = not imgui.get_io().app_focus_lost
        return []

    def route(event, state):
        states.append(dict(state))
        return []

    monkeypatch.setattr(desktop, "Windows", Windows)
    monkeypatch.setattr(desktop, "App", make_app)
    monkeypatch.setattr(desktop, "render_info", render)
    monkeypatch.setattr(desktop, "route", route)
    monkeypatch.setattr(imgui, "is_key_pressed", lambda key, *args: key == imgui.Key.q)

    def run(params, add_ons=None):
        context = imgui.create_context()
        try:
            io = imgui.get_io()
            io.display_size = (960, 800)
            io.delta_time = 1 / 60
            io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
            io.set_ini_filename(None)
            params.callbacks.setup_imgui_config()
            params.callbacks.post_init()
            for index in range(4):
                if index == 2:
                    if hide:
                        applications[0].set_info_visible(False)
                    else:
                        io.add_focus_event(False)
                if index == 3:
                    runtimes[0]["windows"].close_requested = True
                imgui.new_frame()
                params.callbacks.show_gui()
                imgui.render()
                for texture in imgui.get_platform_io().textures:
                    if texture.status == imgui.ImTextureStatus.want_create:
                        texture.set_tex_id(99)
                        texture.set_status(imgui.ImTextureStatus.ok)
                params.callbacks.after_swap()
            assert params.app_shall_exit
        finally:
            imgui.destroy_context(context)

    monkeypatch.setattr(immapp, "run", run)
    desktop.run_desktop(model, {"hide_info_window": "never"})
    assert [state["editing_markdown"] for state in states] == [False, True, False, False]
    assert overlay.read_overlay(path).sections[0].text == "edycja przed flush"


@pytest.mark.parametrize("action", ["acknowledge", "rendered", "readonly"])
def test_status_buttons_in_preview(tmp_path, monkeypatch, action):
    from imgui_bundle import imgui

    path = tmp_path / "Scene.notes.md"
    runtime = runtime_for(path)
    if action == "readonly":
        path.write_bytes(b"\xff")
    else:
        path.write_text(
            overlay.serialize(
                overlay.Overlay(
                    1 if action == "acknowledge" else 2,
                    [overlay.Section(1, "00000000", "nakładka")],
                )
            ),
            encoding="utf-8",
        )
    if action == "rendered":
        info.refresh_notes(runtime["app"].manifest, path, overlay.read_overlay(path))
    context = imgui.create_context()
    labels = []
    actual_button = imgui.button

    def button(label, *args):
        labels.append(label)
        return label == ("Zastosuj do obecnych slajdów" if action == "acknowledge" else "Z renderu")

    monkeypatch.setattr(imgui, "button", button)
    try:
        io = imgui.get_io()
        io.display_size = (960, 800)
        io.delta_time = 1 / 60
        io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
        io.set_ini_filename(None)
        imgui.new_frame()
        imgui.begin("Info")
        preview = {"runtime": runtime, "now": 0, "view_state": {}}
        state, blocked = info.render_notes_status({"index": [0, 0]}, preview)
        imgui.end()
        imgui.render()
        if action == "readonly":
            assert blocked and path.read_bytes() == b"\xff"
            assert not labels
        elif action == "acknowledge":
            assert "Zastosuj do obecnych slajdów" in labels
            assert overlay.read_overlay(path).count == 2
            assert info.editor_text(state["editor"]) == "nakładka"
        else:
            assert "Z renderu" in labels
            assert state["span"] == (0, len("nak?adka"))
            assert info.editor_text(state["editor"]) == "a"
            state["editor"].undo()
            assert info.editor_text(state["editor"]) == "nakładka"
    finally:
        monkeypatch.setattr(imgui, "button", actual_button)
        imgui.destroy_context(context)


@pytest.mark.parametrize(
    "text,parts",
    [
        ("", [""]),
        ("a", ["a"]),
        ("a\n", ["a"]),
        ("\n\na\n\n\nb", ["a", "b"]),
        ("a\n \t\nb", ["a", "b"]),
        ("```py\na\n\nb\n```\n\nc", ["```py\na\n\nb\n```", "c"]),
        ("$$\na\n\nb\n$$\n\nc", ["$$\na\n\nb\n$$", "c"]),
        ("```\na\n\nb\n", ["```\na\n\nb\n"]),
        ("$$\na\n\nb", ["$$\na\n\nb"]),
        ("\\$\n\na", ["\\$", "a"]),
        ("`$$`\n\na", ["`$$`", "a"]),
        ("\n\n", [""]),
        (" \t\n", [""]),
        ("żółć\n\nłąka", ["żółć", "łąka"]),
    ],
)
def test_blocks_exact_roundtrip(text, parts):
    ranges = complete.blocks(text)
    assert [text[a:b] for a, b in ranges] == parts
    for span in ranges:
        assert complete.compose(text, span, text[slice(*span)]) == text
    if not text.strip():
        assert ranges == [(len(text), len(text))]
        assert complete.compose(text, ranges[0], "ż") == text + "ż"


def test_block_targets_after_edit_and_merge():
    text = "żółć\n\nśrodek\n\nłąka"
    span = complete.blocks(text)[1]
    replacement = "nowy\n\nakapit"
    full = complete.compose(text, span, replacement)
    assert complete.block_target(text, span, replacement, -1) == (full, (0, 4), 4)
    target = complete.block_target(text, span, replacement, 1)
    assert full[slice(*target[1])] == "łąka"
    assert complete.shifted_offset(text.index("łąka"), span, replacement) == full.index("łąka")
    # Jeden znak separatora: akapity łączą się wierszem, słowa nie sklejają się.
    for direction, expected, block, cursor in (
        (-1, "żółć\nśrodek\n\nłąka", "żółć\nśrodek", 5),
        (1, "żółć\n\nśrodek\nłąka", "środek\nłąka", 6),
    ):
        merged, active, join = complete.block_target(text, span, "środek", direction, merge=True)
        assert (merged, merged[slice(*active)], join) == (expected, block, cursor)
    # Dwa puste wiersze: pierwszy Backspace zostawia bloki osobno, kursor na początku.
    assert complete.block_target("a\n\n\nb", (4, 5), "b", -1, merge=True) == ("a\n\nb", (3, 4), 0)
    # Edytor zaczyna się pustym wierszem: zostaje w swoim bloku.
    assert complete.block_target("a\n\nb", (3, 4), "\nb", -1, merge=True) == ("a\n\nb", (3, 4), 0)
    assert complete.block_target(text, (0, 4), "żółć", -1) is None


def test_block_activation_flush_and_invalid_return(tmp_path, monkeypatch, capsys):
    from imgui_bundle import imgui

    runtime = runtime_for(tmp_path / "Scene.notes.md")
    runtime["app"].manifest["presentations"][0]["slides"][0]["notes"] = "żółć\n\nłąka"
    state = info.enter_notes(runtime, [0, 0], 0)
    preview = {"runtime": runtime, "now": 0.1, "view_state": {}}
    info.activate_block(preview, (0, 4))
    info.activate_block(preview, (6, 10))
    assert not runtime["dirty_notes"].buffers
    assert state["text"] == "żółć\n\nłąka"
    state["editor"].set_text("<!-- manim-cue błędne -->")
    info.activate_block(preview, (0, 4))
    invalid = state["text"]
    info.enter_notes(runtime, [0, 1], 0.2)
    state = info.enter_notes(runtime, [0, 0], 0.3)
    assert state["text"] == invalid and state["invalid"]
    copied = []
    monkeypatch.setattr(imgui, "set_clipboard_text", copied.append)
    info.flush_notes(runtime, 0.4, exiting=True)
    assert invalid in copied[0] and invalid in capsys.readouterr().err


@pytest.fixture
def block_frame(tmp_path):
    from imgui_bundle import imgui, imgui_md

    runtime = runtime_for(tmp_path / "Scene.notes.md")
    runtime["app"].manifest["presentations"][0]["slides"][0]["notes"] = (
        "pierwszy\n\ndrugi\n\ntrzeci"
    )
    preview = {"runtime": runtime, "now": 0, "view_state": {}}
    state = info.enter_notes(runtime, [0, 0], 0)
    context = imgui.create_context()
    md_context = imgui_md.create_context()
    io = imgui.get_io()
    io.display_size = (960, 800)
    io.delta_time = 1 / 60
    io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
    io.set_ini_filename(None)

    def frame(blocked=False):
        imgui.new_frame()
        imgui.set_next_window_size((600, 600))
        imgui.begin("Info")
        info.render_blocks({"index": [0, 0], "notes_size": 28}, preview, (state, blocked))
        imgui.end()
        imgui.render()
        preview["now"] += 0.01
        for texture in imgui.get_platform_io().textures:
            if texture.status == imgui.ImTextureStatus.want_create:
                texture.set_tex_id(99)
                texture.set_status(imgui.ImTextureStatus.ok)

    try:
        frame()
        info.activate_block(preview, complete.blocks(state["text"])[1])
        frame()
        frame()
        yield runtime, state, preview, frame, io
    finally:
        imgui_md.destroy_context(md_context)
        imgui.destroy_context(context)


def test_block_up_and_escape_flush(block_frame):
    from imgui_bundle import imgui

    runtime, state, preview, frame, io = block_frame
    original = state["text"]
    io.add_key_event(imgui.Key.up_arrow, True)
    frame()
    assert state["span"] == (0, 8)
    assert state["text"] == original and not runtime["dirty_notes"].buffers
    io.add_key_event(imgui.Key.up_arrow, False)
    frame()
    state["editor"].set_text("edycja")
    io.add_key_event(imgui.Key.escape, True)
    frame()
    assert state["span"] is None and not preview["view_state"]["editing_markdown"]
    assert overlay.read_overlay(state["target"][0]).sections[0].text == "edycja\n\ndrugi\n\ntrzeci"


def test_block_focus_lost_flush(block_frame):
    _, state, _, frame, io = block_frame
    state["editor"].set_text("zmiana")
    io.add_focus_event(False)
    frame()
    assert state["span"] is None
    assert (
        overlay.read_overlay(state["target"][0]).sections[0].text == "pierwszy\n\nzmiana\n\ntrzeci"
    )


def test_slide_change_flushes_full_note_and_releases_focus(block_frame):
    from imgui_bundle import imgui

    _, state, preview, _, _ = block_frame
    path = state["target"][0]
    state["editor"].set_text("nowy\n\nakapit")
    imgui.new_frame()
    imgui.begin("Info")
    state, _ = info.render_notes_status({"index": [0, 1]}, preview)
    imgui.end()
    imgui.render()
    assert state["span"] is None and not preview["view_state"]["editing_markdown"]
    assert overlay.read_overlay(path).sections[0].text == "pierwszy\n\nnowy\n\nakapit\n\ntrzeci"


@pytest.mark.parametrize("modifier", ["mod_shift", "mod_ctrl", "mod_alt", "mod_super"])
def test_block_modifiers_leave_key_to_editor(block_frame, modifier):
    from imgui_bundle import imgui

    _, state, _, frame, io = block_frame
    span = state["span"]
    io.add_key_event(getattr(imgui.Key, modifier), True)
    io.add_key_event(imgui.Key.up_arrow, True)
    frame()
    assert state["span"] == span


def test_block_merge_delete(block_frame):
    from imgui_bundle import imgui

    _, state, _, frame, io = block_frame
    state["editor"].set_cursor(edit.TextEditor.DocPos(0, 5))
    io.add_key_event(imgui.Key.delete, True)
    frame()
    assert state["text"] == "pierwszy\n\ndrugi\ntrzeci"
    assert info.editor_text(state["editor"]) == "drugi\ntrzeci"
    cursor = state["editor"].get_cursor_position(0)
    assert (cursor.line, cursor.index) == (0, 5)


@pytest.mark.parametrize("after", [False, True])
def test_click_either_side_beats_focus_loss(block_frame, monkeypatch, after):
    from imgui_bundle import imgui

    runtime, state, _, frame, _ = block_frame
    state["editor"].set_text("zmieniony blok")
    calls = iter([False, True, False] if after else [True, False, False])
    monkeypatch.setattr(imgui, "is_item_hovered", lambda: True)
    monkeypatch.setattr(imgui, "is_item_clicked", lambda *a: next(calls))
    monkeypatch.setattr(imgui, "is_window_focused", lambda *a: False)
    frame()
    assert info.editor_text(state["editor"]) == ("trzeci" if after else "pierwszy")
    assert state["text"] == "pierwszy\n\nzmieniony blok\n\ntrzeci"
    assert not runtime["dirty_notes"].buffers


def test_readonly_blocks_activation(block_frame, monkeypatch):
    from imgui_bundle import imgui

    _, state, _, frame, _ = block_frame
    monkeypatch.setattr(imgui, "is_item_hovered", lambda: True)
    monkeypatch.setattr(imgui, "is_item_clicked", lambda *a: True)
    frame(blocked=True)
    assert state["span"] is None


@pytest.mark.parametrize("guard", ["selection", "multiple", "wrapped", "popup"])
def test_block_navigation_guards(block_frame, monkeypatch, guard):
    from imgui_bundle import imgui

    _, state, preview, frame, io = block_frame
    editor = state["editor"]
    span = state["span"]
    if guard == "selection":
        editor.select_all()
    elif guard == "multiple":
        editor.set_text("x x")
        editor.select_all_occurrences_of("x")
        assert editor.get_number_of_cursors() > 1
    elif guard == "wrapped":
        editor.set_text("długi wiersz " * 40)
        frame()
        editor.set_cursor(edit.TextEditor.DocPos(0, 200))
        frame()
        assert editor.doc_pos2_vis_pos(editor.get_cursor_position(0)).row > 0
    else:
        preview["view_state"]["popup"] = [("test", 0, 0, "test")]
    io.add_key_event(imgui.Key.up_arrow, True)
    frame()
    assert state["span"][0] == span[0]
    assert "transition" not in preview["view_state"]


def test_block_repeat_crosses_once_per_frame(block_frame):
    from imgui_bundle import imgui

    _, state, preview, frame, io = block_frame
    info.activate_block(preview, complete.blocks(state["text"])[2])
    frame()
    io.delta_time = 0.1
    io.add_key_event(imgui.Key.up_arrow, True)
    frame()
    assert info.editor_text(state["editor"]) == "drugi"
    for _ in range(6):
        frame()
    assert state["span"] is not None and state["text"] == "pierwszy\n\ndrugi\n\ntrzeci"
    assert info.editor_text(state["editor"]) == "pierwszy"


def test_popup_mouse_accept_beats_focus_loss(block_frame, monkeypatch):
    from imgui_bundle import imgui

    _, state, preview, frame, _ = block_frame
    state["editor"].set_text("$\\fr$")
    state["editor"].set_cursor(edit.TextEditor.DocPos(0, 4))
    frame()
    frame()
    assert preview["view_state"]["popup"]
    monkeypatch.setattr(imgui, "is_window_focused", lambda *a: False)
    monkeypatch.setattr(edit.TextEditor, "is_doc_pos_visible", lambda *a: True)
    monkeypatch.setattr(imgui, "selectable", lambda *a: (True, False))
    frame()
    assert state["span"] is not None
    assert info.editor_text(state["editor"]) == "$\\frac{}{}$"
    state["editor"].undo()
    assert info.editor_text(state["editor"]) == "$\\fr$"


def test_formulas_share_budget_across_blocks(monkeypatch):
    from imgui_bundle import imgui, imgui_md

    from manimcue.player import notes_math

    rendered, errors = [], []
    monkeypatch.setattr(imgui_md, "has_latex", lambda: False)
    monkeypatch.setattr(imgui_md, "render", lambda text: None)
    monkeypatch.setattr(imgui, "get_style", lambda: SimpleNamespace(color_=lambda _: (1, 1, 1, 1)))
    monkeypatch.setattr(imgui, "text_wrapped", errors.append)

    def formula(source, *args, **kwargs):
        rendered.append(source)
        return {"error": "kontrolowany brak rastra"}

    monkeypatch.setattr(notes_math, "render_formula", formula)
    renderer = notes_math.NotesRenderer()
    text = "\n\n".join(f"$x_{i}$" for i in range(129))
    for _ in range(2):
        for used, (start, end) in enumerate(complete.blocks(text)):
            renderer.render(text[start:end], 28, 1, used)
    assert len(rendered) == 256 and len(set(rendered)) == 128
    assert sum("Limit 128" in error for error in errors) == 2


def test_formula_block_cache_stable(monkeypatch):
    from pathlib import Path

    import imgui_bundle
    from imgui_bundle import imgui, imgui_md, imgui_microtex

    from manimcue.player import notes_math

    fonts = Path(imgui_bundle.__file__).parent / "assets" / "fonts" / "latex"
    imgui_microtex.init(str(fonts / "latinmodern-math.clm1"), str(fonts / "latinmodern-math.otf"))
    monkeypatch.setattr(imgui_md, "has_latex", lambda: True)
    monkeypatch.setattr(imgui_md, "render", lambda text: None)
    monkeypatch.setattr(imgui_microtex, "clear_texture_cache", lambda: None)
    monkeypatch.setattr(imgui, "get_style", lambda: SimpleNamespace(color_=lambda _: (1, 1, 1, 1)))
    baked = SimpleNamespace(get_font_baked=lambda size: SimpleNamespace(ascent=100, descent=-5))
    monkeypatch.setattr(imgui_md, "get_font", lambda spec: SimpleNamespace(size=28, font=baked))
    notes_math.clear_cache()
    renderer = notes_math.NotesRenderer()
    try:
        first = None
        for _ in range(2):
            for index in range(129):
                renderer.render(f"$x_{index}$", 28, 1, index)
            current = {key: id(value) for key, value in notes_math._cache.items()}
            assert len(current) == 128
            assert first is None or current == first
            first = current
    finally:
        notes_math.clear_cache()


def test_mark_wraps_selection(tmp_path):
    from imgui_bundle import imgui

    runtime = runtime_for(tmp_path / "Scene.notes.md")
    preview = {"runtime": runtime, "now": 0, "view_state": {}}
    active_notes(runtime, [0, 0], 0)
    context = imgui.create_context()

    def frame():
        imgui.new_frame()
        imgui.set_next_window_size((800, 700))
        imgui.begin("Info")
        info.render_editor({"index": [0, 0], "notes_size": 28}, preview)
        imgui.end()
        imgui.render()
        for texture in imgui.get_platform_io().textures:
            if texture.status == imgui.ImTextureStatus.want_create:
                texture.set_tex_id(99)
                texture.set_status(imgui.ImTextureStatus.ok)

    try:
        io = imgui.get_io()
        io.display_size = (960, 800)
        io.delta_time = 1 / 60
        io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
        io.set_ini_filename(None)
        frame()
        editor = runtime["notes_edit"]["editor"]
        editor.set_text("a żółć b")
        editor.select_region(edit.TextEditor.DocPos(0, 2), edit.TextEditor.DocPos(0, 6))
        editor.set_focus()
        frame()
        frame()
        for mark, expected in (
            ("$", "a $żółć$ b"),
            ("*", "a $*żółć*$ b"),
            ("(", "a $*(żółć)*$ b"),
        ):
            io.add_input_character(ord(mark))
            frame()
            assert info.editor_text(editor) == expected
        selection = editor.get_cursor_selection(0)
        assert (selection.start.index, selection.end.index) == (5, 9)
        # Ctrl+Enter zatwierdza blok bez wstawienia nowego wiersza.
        io.add_key_event(imgui.Key.mod_ctrl, True)
        io.add_key_event(imgui.Key.left_ctrl, True)
        io.add_key_event(imgui.Key.enter, True)
        frame()
        assert preview["view_state"].get("deactivate")
        assert info.editor_text(editor) == "a $*(żółć)*$ b"
    finally:
        imgui.destroy_context(context)


def test_formula_struts(monkeypatch):
    from imgui_bundle import imgui, imgui_md, imgui_microtex

    from manimcue.player import notes_math

    rendered, spaces = [], []
    monkeypatch.setattr(imgui_md, "has_latex", lambda: True)
    monkeypatch.setattr(imgui_md, "render", rendered.append)
    monkeypatch.setattr(imgui_microtex, "is_initialized", lambda: True)
    monkeypatch.setattr(imgui_microtex, "clear_texture_cache", lambda: None)
    monkeypatch.setattr(imgui, "get_style", lambda: SimpleNamespace(color_=lambda _: (1, 1, 1, 1)))
    monkeypatch.setattr(imgui, "dummy", spaces.append)
    baked = SimpleNamespace(get_font_baked=lambda size: SimpleNamespace(ascent=20, descent=-5))
    monkeypatch.setattr(imgui_md, "get_font", lambda spec: SimpleNamespace(size=28, font=baked))
    monkeypatch.setattr(
        notes_math,
        "render_formula",
        lambda *args, **kwargs: {"error": None, "baseline": 60, "height": 80},
    )
    text = (
        "$a$ start\n- b\n- $c$\n- $e$\n- $f\n- $g$\n```\nkod\n```  \n$d$\n"
        "a | b\n--- | ---\n$h$\nTytuł\n---\n$i$"
    )
    notes_math.NotesRenderer().render(text, 28, 2)
    # Rezerwa 60 / 2 - 20 = 10; pod tekstem descent 5, pod wzorem głębokość (80 - 60) / 2.
    strut, deep = (
        rf" $\raisebox{{-{depth}px}}{{\rule{{0px}}{{{depth}px}}}}$" for depth in (30, 40)
    )
    lines = rendered[0].split("\n")
    # Pierwszy wiersz dostaje rezerwę, poprzednik $c$ rozpórkę, zamknięcie ``` nic.
    assert spaces == [(0, 10)]
    assert lines[1] == "- b" + strut
    assert lines[2].endswith("}$" + deep)
    # Niesparowany $ w poprzednim wierszu: bez rozpórki.
    assert lines[4] == "- $f"
    # Zamknięcie ``` ze spacjami, separator tabeli i podkreślenie Setext bez rozpórki.
    assert lines[8] == "```  "
    assert lines[11] == "--- | ---"
    assert lines[14] == "---"


@pytest.mark.parametrize(
    "text,column,replacement,cursor",
    [
        ("- żółć", 6, "\n- ", (1, 2)),
        ("*  żółć", 7, "\n*  ", (1, 3)),
        ("+ żółć", 6, "\n+ ", (1, 2)),
        ("1. żółć", 7, "\n2. ", (1, 3)),
        ("1) żółć", 7, "\n2) ", (1, 3)),
        ("- [x] żółć", 10, "\n- [ ] ", (1, 6)),
        ("- [X] żółć", 10, "\n- [ ] ", (1, 6)),
        ("- [ ] żółć", 10, "\n- [ ] ", (1, 6)),
        ("> żółć", 6, "\n> ", (1, 2)),
        ("\t  - żółć", 9, "\n\t  - ", (1, 5)),
        ("- żółć dalej", 4, "\n- ", (1, 2)),
    ],
)
def test_continue_list(text, column, replacement, cursor):
    result = complete.continue_list(text, (0, column))
    assert result == ((0, column), (0, column), replacement, cursor)
    editor = edit.TextEditor()
    editor.set_text(text)
    info.replace_notes(editor, result)
    assert info.editor_text(editor) == text[:column] + replacement + text[column:]
    editor.undo()
    assert info.editor_text(editor) == text


@pytest.mark.parametrize("text", ["-", "  *  ", "\t1) [x]  ", "> ", "+ [ ] "])
def test_empty_list_ends(text):
    assert complete.continue_list("żółć\n" + text, (1, len(text))) == (
        (1, 0),
        (1, len(text)),
        "",
        (1, 0),
    )


@pytest.mark.parametrize("column", [0, 1, 2, 3, 4, 5, 6])
def test_continue_list_before_marker(column):
    assert complete.continue_list("  1. [x] żółć", (0, column)) is None


@pytest.mark.parametrize("prefix,expected", [(r"\fr", "ac{}{}"), ("x", ""), ("", "")])
def test_ghost_remainder(prefix, expected):
    text = "żółć " + prefix
    assert (
        complete.ghost_remainder(text, (0, len(text)), (r"\frac", 5, len(text), r"\frac{|}{}"))
        == expected
    )


@pytest.mark.parametrize("key", ["enter", "keypad_enter"])
@pytest.mark.parametrize("guard", ["none", "shift", "popup", "selection", "multiple"])
def test_list_enter_integration(block_frame, key, guard):
    from imgui_bundle import imgui

    _, state, preview, frame, io = block_frame
    editor = state["editor"]
    editor.set_text("- żółć")
    editor.set_cursor(edit.TextEditor.DocPos(0, 6))
    frame()
    frame()
    if guard == "shift":
        io.add_key_event(imgui.Key.mod_shift, True)
    elif guard == "popup":
        preview["view_state"]["popup"] = [("test", 0, 6, "test")]
    elif guard == "selection":
        editor.select_all()
    elif guard == "multiple":
        editor.set_text("- x x")
        editor.select_all_occurrences_of("x")
    io.add_key_event(getattr(imgui.Key, key), True)
    frame()
    consumed = preview["view_state"]["consumed"]
    if guard == "none":
        assert info.editor_text(editor) == "- żółć\n- "
        assert getattr(imgui.Key, key) in consumed
        frame()
        assert getattr(imgui.Key, key) in consumed
        assert info.editor_text(editor) == "- żółć\n- "
        io.add_key_event(getattr(imgui.Key, key), False)
        frame()
        assert getattr(imgui.Key, key) not in consumed
        editor.undo()
        assert info.editor_text(editor) == "- żółć"
    elif guard == "popup" and key == "enter":
        assert info.editor_text(editor) == "test"
    else:
        assert getattr(imgui.Key, key) not in consumed


def test_ghost_draws_above_editor_and_disappears(block_frame, monkeypatch):
    from imgui_bundle import imgui

    _, state, preview, frame, io = block_frame
    editor = state["editor"]
    editor.set_text("żółć $\\fr$")
    editor.set_cursor(edit.TextEditor.DocPos(0, 9))
    calls = []
    draw = SimpleNamespace(
        push_clip_rect=lambda *args: calls.append(("clip", args)),
        add_rect_filled=lambda *args: calls.append(("background", args)),
        add_text=lambda *args: calls.append(("text", args)),
        pop_clip_rect=lambda: None,
    )
    monkeypatch.setattr(imgui, "get_foreground_draw_list", lambda viewport: draw)
    monkeypatch.setattr(edit.TextEditor, "is_doc_pos_visible", lambda *args: True)
    frame()
    assert preview["view_state"]["popup"]
    assert [call[0] for call in calls] == ["clip", "background", "text"]
    assert calls[-1][1][-1] == "ac{}{}"
    assert calls[-1][1][1] == 28
    calls.clear()
    io.add_key_event(imgui.Key.escape, True)
    frame()
    assert not calls and not preview["view_state"]["popup"]


@pytest.mark.parametrize(
    "text,cursor,direction,expected",
    [
        ("abc żółć", (0, 8), -1, "abc "),
        ("abc ", (0, 4), -1, ""),
        ("a\nb", (1, 0), -1, "ab"),
        ("x = (y)", (0, 7), -1, "x = (y"),
        ("żółć abc", (0, 0), 1, " abc"),
        ("ab  \ncd", (0, 2), 1, "ab\ncd"),
    ],
)
def test_delete_word(text, cursor, direction, expected):
    start, end, replacement, _ = complete.delete_word(text, cursor, direction)
    first = complete.offset(text, start)
    last = complete.offset(text, end)
    assert text[:first] + replacement + text[last:] == expected


def test_delete_word_at_edge():
    assert complete.delete_word("abc", (0, 0), -1) is None
    assert complete.delete_word("abc", (0, 3), 1) is None


def test_ctrl_backspace_deletes_word(tmp_path):
    from imgui_bundle import imgui

    runtime = runtime_for(tmp_path / "Scene.notes.md")
    preview = {"runtime": runtime, "now": 0, "view_state": {}}
    active_notes(runtime, [0, 0], 0)
    context = imgui.create_context()

    def frame():
        imgui.new_frame()
        imgui.set_next_window_size((800, 700))
        imgui.begin("Info")
        info.render_editor({"index": [0, 0], "notes_size": 28}, preview)
        imgui.end()
        imgui.render()
        for texture in imgui.get_platform_io().textures:
            if texture.status == imgui.ImTextureStatus.want_create:
                texture.set_tex_id(99)
                texture.set_status(imgui.ImTextureStatus.ok)

    try:
        io = imgui.get_io()
        io.display_size = (960, 800)
        io.delta_time = 1 / 60
        io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
        io.set_ini_filename(None)
        frame()
        editor = runtime["notes_edit"]["editor"]
        editor.set_text("abc żółć")
        editor.set_cursor(edit.TextEditor.DocPos(0, 8))
        editor.set_focus()
        frame()
        frame()
        io.add_key_event(imgui.Key.mod_ctrl, True)
        io.add_key_event(imgui.Key.left_ctrl, True)
        io.add_key_event(imgui.Key.backspace, True)
        frame()
        assert info.editor_text(editor) == "abc "
        io.add_key_event(imgui.Key.backspace, False)
        frame()
        editor.select_region(edit.TextEditor.DocPos(0, 0), edit.TextEditor.DocPos(0, 2))
        io.add_key_event(imgui.Key.delete, True)
        frame()
        assert info.editor_text(editor) == "c "
    finally:
        imgui.destroy_context(context)


def test_up_lands_on_last_visual_row_of_wrapped_neighbor(tmp_path):
    from imgui_bundle import imgui, imgui_md

    runtime = runtime_for(tmp_path / "Scene.notes.md")
    runtime["app"].manifest["presentations"][0]["slides"][0]["notes"] = "słowo " * 80 + "\n\nx"
    preview = {"runtime": runtime, "now": 0, "view_state": {}}
    state = info.enter_notes(runtime, [0, 0], 0)
    context = imgui.create_context()
    md_context = imgui_md.create_context()
    io = imgui.get_io()
    io.display_size = (960, 800)
    io.delta_time = 1 / 60
    io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
    io.set_ini_filename(None)

    def frame():
        imgui.new_frame()
        imgui.set_next_window_size((600, 700))
        imgui.begin("Info")
        info.render_blocks({"index": [0, 0], "notes_size": 28}, preview, (state, False))
        imgui.end()
        imgui.render()
        for texture in imgui.get_platform_io().textures:
            if texture.status == imgui.ImTextureStatus.want_create:
                texture.set_tex_id(99)
                texture.set_status(imgui.ImTextureStatus.ok)

    try:
        frame()
        info.activate_block(preview, complete.blocks(state["text"])[1], 1)
        frame()
        frame()
        io.add_key_event(imgui.Key.up_arrow, True)
        frame()
        io.add_key_event(imgui.Key.up_arrow, False)
        frame()
        editor = state["editor"]
        cursor = editor.get_cursor_position(0)
        lines = info.editor_text(editor).split("\n")
        last = editor.doc_pos2_vis_pos(type(cursor)(len(lines) - 1, len(lines[-1]))).row
        assert state["span"][0] == 0 and last > 0
        assert editor.doc_pos2_vis_pos(cursor).row == last
    finally:
        imgui_md.destroy_context(md_context)
        imgui.destroy_context(context)
