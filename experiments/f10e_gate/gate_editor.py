"""Bramki TextEditor D49; uruchamiać ręcznie przy odblokowanym pulpicie."""

import argparse
import ctypes
import json
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=90)
    args = parser.parse_args()
    from imgui_bundle import hello_imgui, imgui, immapp
    from imgui_bundle import imgui_color_text_edit as edit

    editor = edit.TextEditor()
    editor.set_language(edit.TextEditor.Language.markdown())
    editor.set_word_wrap_enabled(True)
    editor.set_show_line_numbers_enabled(False)
    editor.set_text("początek\n\tdrugi wiersz " * 8)
    params = hello_imgui.RunnerParams()
    params.platform_backend_type = hello_imgui.PlatformBackendType.glfw
    params.renderer_backend_type = hello_imgui.RendererBackendType.open_gl3
    params.ini_disable = True
    params.fps_idling.enable_idling = False
    params.app_window_params.window_title = "manim-cue D49 gates"
    params.app_window_params.window_geometry.size = (1000, 700)
    started = time.monotonic()
    results = []
    state = {
        "popup": False,
        "choice": 0,
        "accepted": 0,
        "focus": False,
        "popup_focus": False,
        "focus_popup": False,
        "main": 0,
        "shortcuts": 0,
    }
    rectangles = {}
    consumed = set()
    editor_font = None
    keys = (
        imgui.Key.up_arrow,
        imgui.Key.down_arrow,
        imgui.Key.enter,
        imgui.Key.tab,
        imgui.Key.escape,
    )
    pos = edit.TextEditor.DocPos

    def content():
        # get_text() jest stratny ('a' i 'a\n' dają 'a\n'); dokładny tekst z wierszy.
        return "\n".join(editor.get_line_text(line) for line in range(editor.get_line_count()))

    def snapshot():
        cursor = editor.get_cursor_position(0)
        return content(), (cursor.line, cursor.index)

    def record(name, passed, details):
        result = {"gate": name, "status": "PASS" if passed else "FAIL", "details": details}
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    def delay(frames=3):
        for _ in range(frames):
            yield

    def key(key_code, down):
        imgui.get_io().add_key_event(key_code, down)

    def press(key_code, frames=3, seconds=0.0):
        key(key_code, True)
        yield from delay(frames)
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            yield
        key(key_code, False)
        yield from delay()

    def text(value):
        for character in value:
            imgui.get_io().add_input_character(ord(character))
        yield from delay()

    def click(name):
        x, y = rectangles[name]
        io = imgui.get_io()
        io.add_mouse_pos_event(x, y)
        yield from delay()
        io.add_mouse_button_event(0, True)
        yield from delay()
        io.add_mouse_button_event(0, False)
        yield from delay()

    def focus():
        editor.set_focus()
        yield from delay()

    def chord(key_code):
        key(imgui.Key.left_ctrl, True)
        key(imgui.Key.mod_ctrl, True)
        yield from press(key_code)
        key(imgui.Key.left_ctrl, False)
        key(imgui.Key.mod_ctrl, False)
        yield from delay()

    def scenarios():
        yield from delay(10)
        yield from focus()
        baseline = snapshot()
        details = []
        for key_code in keys:
            state["popup"] = True
            yield from delay()
            before = (state["choice"], state["accepted"])
            yield from press(key_code, seconds=0.8 if key_code == imgui.Key.down_arrow else 0.0)
            unchanged = snapshot() == baseline
            repeated = key_code != imgui.Key.down_arrow or state["choice"] - before[0] > 1
            reacted = (
                (state["choice"], state["accepted"]) != before
                if key_code != imgui.Key.escape
                else not state["popup"]
            )
            details.append(
                {
                    "key": str(key_code),
                    "editor_unchanged": unchanged,
                    "popup_reacted": reacted,
                    "repeat": repeated,
                }
            )
        state["popup"] = True
        yield from delay()
        yield from click("suggestion")
        yield from text("ż")
        mouse_ok = content() != baseline[0] and not state["popup"]
        mouse_details = {"text_changed": content() != baseline[0], "popup_open": state["popup"]}
        record(
            "B1",
            all(
                item["editor_unchanged"] and item["popup_reacted"] and item["repeat"]
                for item in details
            )
            and mouse_ok,
            {"keys": details, "mouse_then_typing": mouse_details},
        )

        editor.set_text("")
        yield from focus()
        key(imgui.Key.mod_ctrl, True)
        key(imgui.Key.mod_alt, True)
        key(imgui.Key.left_ctrl, True)
        key(imgui.Key.right_alt, True)
        yield from delay()
        for letter, character in zip("acelnosxz", "ąćęłńóśźż"):
            key(getattr(imgui.Key, letter), True)
            yield from text(character)
            key(getattr(imgui.Key, letter), False)
            yield from delay()
        for shortcut in (imgui.Key.b, imgui.Key.i):
            yield from press(shortcut)
        for key_code in (
            imgui.Key.mod_ctrl,
            imgui.Key.mod_alt,
            imgui.Key.left_ctrl,
            imgui.Key.right_alt,
        ):
            key(key_code, False)
        yield from delay()
        synthetic = content()
        record(
            "B2.synthetic",
            synthetic == "ąćęłńóśźż" and state["shortcuts"] == 0,
            {"text": synthetic, "own_shortcuts": state["shortcuts"]},
        )
        yield from windows_altgr()
        # Syntetyczne znaki omijają fokus OS, więc test po utracie fokusu nie ma sensu tutaj;
        # unieważnienie flagi edycji przy io.app_focus_lost testuje implementacja.
        results.append(
            {
                "gate": "B2.focus_lost",
                "status": "SKIP",
                "details": "znaki wstrzykiwane omijają fokus OS; test flagi w implementacji",
            }
        )
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)

        imgui.push_font(editor_font, 28)
        try:
            font = imgui.get_font_baked()
            missing = [
                character
                for character in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
                if font.find_glyph_no_fallback(ord(character)) is None
            ]
        finally:
            imgui.pop_font()
        record("B3", not missing, {"missing": missing, "size": 28})

        yield from focus()
        child_focus = state["focus"]
        state["popup"] = True
        yield from delay()
        state["focus_popup"] = True
        yield from delay()
        popup_focus = state["popup_focus"]
        state["focus_popup"] = False
        yield from press(imgui.Key.escape)
        first_escape = not state["popup"] and state["focus"]
        yield from press(imgui.Key.escape)
        second_escape = not state["focus"]
        yield from click("main")
        before = snapshot()
        main_before = state["main"]
        yield from press(imgui.Key.space)
        main_ok = snapshot() == before and state["main"] > main_before
        yield from focus()
        yield from text("Q")
        editor_ok = snapshot() != before
        record(
            "B4",
            child_focus
            and popup_focus
            and first_escape
            and second_escape
            and main_ok
            and editor_ok,
            {
                "child": child_focus,
                "popup": popup_focus,
                "first_escape": first_escape,
                "second_escape": second_escape,
                "main_first_key": main_ok,
                "editor_first_key": editor_ok,
            },
        )

        editor.set_text("zażółć")
        editor.select_all()
        yield from focus()
        yield from chord(imgui.Key.c)
        copied = imgui.get_clipboard_text() == "zażółć"
        imgui.set_clipboard_text("gęślą\n\tjaźń")
        yield from chord(imgui.Key.v)
        pasted = content()
        yield from chord(imgui.Key.z)
        undone = content()
        yield from chord(imgui.Key.y)
        redone = content()
        record(
            "B5",
            copied and pasted == "gęślą\n\tjaźń" and undone == "zażółć" and redone == pasted,
            {"copy": copied, "paste": pasted, "undo": undone, "redo": redone},
        )

        transactions = []
        original = "żółć\t" + "zawijanie " * 30 + "\nłąka\nkoniec"
        for name, start, end, replacement in (
            ("suggestion", pos(0, 0), pos(0, 0), "\\frac{}{}"),
            ("bold", pos(1, 0), pos(1, 4), "**łąka**"),
            ("rendered", pos(0, 0), pos(2, 6), "\tZ renderu\nżółć\n"),
        ):
            editor.set_text(original)
            editor.set_cursor(start)
            yield from focus()
            if name == "bold":
                key(imgui.Key.mod_shift, True)
                key(imgui.Key.left_shift, True)
                for _ in range(4):
                    yield from press(imgui.Key.right_arrow)
                key(imgui.Key.mod_shift, False)
                key(imgui.Key.left_shift, False)
                yield from delay()
            baseline = snapshot()
            selection = editor.get_cursor_text(0)
            editor.replace_section_text(start, end, replacement)
            editor.set_cursor(
                pos(
                    start.line,
                    start.index + (2 if name == "bold" else 6 if name == "suggestion" else 0),
                )
            )
            yield from delay()
            changed = snapshot()
            yield from chord(imgui.Key.z)
            undo = snapshot()
            undo_selection = editor.get_cursor_text(0)
            yield from chord(imgui.Key.y)
            redo = snapshot()
            lines = original.split("\n")
            sensible = 0 <= undo[1][0] < len(lines) and 0 <= undo[1][1] <= len(lines[undo[1][0]])
            restored_selection = editor.get_cursor_text(0)
            transactions.append(
                {
                    "name": name,
                    "undo": undo,
                    "selection_before": selection,
                    "selection_after_redo": restored_selection,
                    "selection_after_undo": undo_selection,
                    "redo": redo,
                    "pass": (
                        undo[0] == baseline[0]
                        and redo[0] == changed[0]
                        and sensible
                        and (name != "bold" or selection == "łąka")
                    ),
                }
            )
        record("B6", all(item["pass"] for item in transactions), transactions)

    def windows_altgr():
        if not hasattr(ctypes, "windll"):
            results.append(
                {"gate": "B2.windows", "status": "SKIP", "details": "próba człowieka: brak Windows"}
            )
            print(json.dumps(results[-1], ensure_ascii=False), flush=True)
            return
        from ctypes import wintypes

        user = ctypes.windll.user32
        user.GetForegroundWindow.restype = wintypes.HWND
        user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user.GetKeyboardLayout.restype = wintypes.HKL
        user.ActivateKeyboardLayout.argtypes = [wintypes.HKL, wintypes.UINT]
        user.ActivateKeyboardLayout.restype = wintypes.HKL
        layouts = (wintypes.HKL * 256)()
        count = user.GetKeyboardLayoutList(256, layouts)
        polish = next(
            (layout for layout in layouts[:count] if int(layout) & 0xFFFF == 0x0415), None
        )
        if polish is None:
            results.append(
                {
                    "gate": "B2.windows",
                    "status": "SKIP",
                    "details": "próba człowieka: brak polskiego układu",
                }
            )
            print(json.dumps(results[-1], ensure_ascii=False), flush=True)
            return

        class Keyboard(ctypes.Structure):
            _fields_ = [
                ("vk", wintypes.WORD),
                ("scan", wintypes.WORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("extra", ctypes.c_size_t),
            ]

        class Mouse(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("data", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("extra", ctypes.c_size_t),
            ]

        class Payload(ctypes.Union):
            _fields_ = [("keyboard", Keyboard), ("mouse", Mouse)]

        class Input(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("payload", Payload)]

        def send(vk, flags=0):
            event = Input(1, Payload(keyboard=Keyboard(vk, 0, flags, 0, 0)))
            if user.SendInput(1, ctypes.byref(event), ctypes.sizeof(event)) != 1:
                raise OSError("SendInput nie wstrzyknął klawisza")

        user.FindWindowW.restype = wintypes.HWND
        own = user.FindWindowW(None, "manim-cue D49 gates")
        if own:
            # Tap Alt odblokowuje SetForegroundWindow dla procesu bez ostatniego wejścia.
            user.keybd_event(0x12, 0, 0, 0)
            user.keybd_event(0x12, 0, 2, 0)
            user.SetForegroundWindow(own)
            yield from delay(10)
        window = user.GetForegroundWindow()
        process = wintypes.DWORD()
        user.GetWindowThreadProcessId(window, ctypes.byref(process))
        import os

        if process.value != os.getpid():
            record("B2.windows", False, "Okno bramki nie jest na pierwszym planie")
            return
        previous = user.GetKeyboardLayout(0)
        editor.set_text("")
        yield from focus()
        try:
            user.ActivateKeyboardLayout(polish, 0)
            for letter in "ACELNOSXZ":
                send(0xA5, 1)
                yield from delay()
                send(ord(letter))
                yield from delay()
                send(ord(letter), 2)
                send(0xA5, 3)
                yield from delay()
            record("B2.windows", content() == "ąćęłńóśźż", {"text": content()})
        finally:
            send(0xA5, 3)
            user.ActivateKeyboardLayout(previous, 0)

    runner = scenarios()

    def gui():
        try:
            io = imgui.get_io()
            owner = imgui.get_id("completion-owner")
            popup_was_open = state["popup"]
            if popup_was_open:
                for key_code in keys:
                    pressed = imgui.internal.is_key_pressed(
                        key_code, imgui.InputFlags_.repeat, owner
                    )
                    if pressed:
                        if key_code in (imgui.Key.up_arrow, imgui.Key.down_arrow):
                            state["choice"] += 1 if key_code == imgui.Key.down_arrow else -1
                        else:
                            consumed.add(key_code)
                            state["popup"] = False
                            editor.set_focus()
                            state["accepted"] += key_code != imgui.Key.escape
                    imgui.internal.set_key_owner(
                        key_code, owner, imgui.internal.InputFlagsPrivate_.lock_this_frame
                    )
            for key_code in list(consumed):
                if imgui.is_key_down(key_code):
                    imgui.internal.set_key_owner(
                        key_code, owner, imgui.internal.InputFlagsPrivate_.lock_this_frame
                    )
                else:
                    consumed.remove(key_code)
            if not popup_was_open and state["focus"] and imgui.is_key_pressed(imgui.Key.escape):
                imgui.set_window_focus(None)
            if (
                state["focus"]
                and io.key_ctrl
                and not io.key_alt
                and (imgui.is_key_pressed(imgui.Key.b) or imgui.is_key_pressed(imgui.Key.i))
            ):
                state["shortcuts"] += 1
            imgui.begin_child("notes-host", (650, 550))
            imgui.push_font(editor_font, 28)
            editor.render("editor", (630, 520), True)
            imgui.pop_font()
            state["focus"] = imgui.is_window_focused(imgui.FocusedFlags_.child_windows)
            imgui.end_child()
            imgui.same_line()
            imgui.begin_group()
            imgui.button("Główny", (220, 100))
            minimum, maximum = imgui.get_item_rect_min(), imgui.get_item_rect_max()
            rectangles["main"] = ((minimum.x + maximum.x) / 2, (minimum.y + maximum.y) / 2)
            if imgui.is_item_clicked():
                imgui.set_window_focus(None)
            if not state["focus"] and not state["popup"] and imgui.is_key_pressed(imgui.Key.space):
                state["main"] += 1
            imgui.text(f"Wybór: {state['choice']}")
            imgui.end_group()
            state["popup_focus"] = False
            if state["popup"]:
                imgui.set_next_window_pos((680, 220))
                if state["focus_popup"]:
                    imgui.set_next_window_focus()
                imgui.begin("Podpowiedzi", flags=imgui.WindowFlags_.no_focus_on_appearing)
                # set_focus edytora wynosi okno główne nad popup; popup zawsze na wierzchu.
                imgui.internal.bring_window_to_display_front(imgui.internal.get_current_window())
                state["popup_focus"] = imgui.is_window_focused()
                imgui.button("Wstaw podpowiedź", (220, 60))
                minimum, maximum = imgui.get_item_rect_min(), imgui.get_item_rect_max()
                rectangles["suggestion"] = (
                    (minimum.x + maximum.x) / 2,
                    (minimum.y + maximum.y) / 2,
                )
                if imgui.is_item_clicked():
                    state["accepted"] += 1
                    state["popup"] = False
                    editor.set_focus()
                imgui.end()
            if time.monotonic() - started > args.timeout:
                raise TimeoutError(f"Limit {args.timeout}s")
            next(runner)
        except StopIteration:
            finish()
        except Exception as error:  # noqa: BLE001 — błąd bramki musi trafić do raportu JSON
            record("runtime", False, repr(error))
            finish()

    def finish():
        # Brak wyników też jest błędem; timeout nie może udawać ukończenia.
        expected = {"B1", "B2.synthetic", "B2.windows", "B2.focus_lost", "B3", "B4", "B5", "B6"}
        for name in sorted(expected - {result["gate"] for result in results}):
            record(name, False, "Scenariusz nie został ukończony")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        params.app_shall_exit = True

    def load_font():
        nonlocal editor_font
        editor_font = hello_imgui.load_font_ttf("fonts/Inconsolata-Medium.ttf", 28)

    params.callbacks.load_additional_fonts = load_font
    params.callbacks.show_gui = gui
    immapp.run(params)
    return int(any(result["status"] == "FAIL" for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
