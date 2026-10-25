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


@pytest.mark.parametrize("text", ["", "a", "a\n", "a\n\n"])
def test_enter_does_not_dirty(tmp_path, text):
    runtime = runtime_for(tmp_path / "Scene.notes.md")
    runtime["app"].manifest["presentations"][0]["slides"][0]["notes"] = text
    state = info.enter_notes(runtime, [0, 0], 0)
    info.capture_notes(runtime, 1)
    assert info.editor_text(state["editor"]) == text
    assert not runtime["dirty_notes"].buffers


@pytest.mark.parametrize("reason", ["slide", "preview", "hide", "exit"])
def test_flush_reads_lines_before_delay(tmp_path, reason):
    runtime = runtime_for(tmp_path / "Scene.notes.md")
    state = info.enter_notes(runtime, [0, 0], 0)
    state["editor"].set_text("zażółć\n\n")
    if reason == "slide":
        info.enter_notes(runtime, [0, 1], 0.1)
    else:
        info.flush_notes(runtime, 0.1, exiting=reason == "exit")
    assert overlay.read_overlay(tmp_path / "Scene.notes.md").sections[0].text == "zażółć\n\n"
    assert not runtime["dirty_notes"].buffers
    for deck in runtime["app"].manifest["presentations"]:
        assert deck["slides"][0]["notes"] == "zażółć\n\n"


def test_failure_two_slides_hide_exit_rescue(tmp_path, monkeypatch):
    path = tmp_path / "Scene.notes.md"
    runtime = runtime_for(path)
    state = info.enter_notes(runtime, [0, 0], 0)
    state["editor"].set_text("edycja A")
    monkeypatch.setattr(
        overlay,
        "save_overlay",
        lambda *a, **k: (_ for _ in ()).throw(PermissionError("zablokowany")),
    )
    state = info.enter_notes(runtime, [0, 1], 0.1)
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
    state = info.enter_notes(runtime, [0, 0], 0)
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
    state = info.enter_notes(runtime, [0, 0], 0)
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
    state = info.enter_notes(runtime, [0, 0], 0)
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
    state = info.enter_notes(runtime, [0, 0], 0)
    info.replace_notes(state["editor"], ((0, 0), (0, 8), "a", (0, 1)))
    info.flush_notes(runtime, 0.1)
    assert not overlay.read_overlay(path).sections


def test_editor_widget_without_windows(tmp_path):
    from imgui_bundle import imgui

    runtime = runtime_for(tmp_path / "Scene.notes.md")
    preview = {"runtime": runtime, "now": 0, "view_state": {"editing": True}}
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
            state = info.enter_notes(runtime, [0, 0], preview["now"])
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
            assert preview["view_state"]["editing"]
            assert info.editor_text(state["editor"]) == "a"
            state["editor"].undo()
            assert info.editor_text(state["editor"]) == "nakładka"
    finally:
        monkeypatch.setattr(imgui, "button", actual_button)
        imgui.destroy_context(context)
