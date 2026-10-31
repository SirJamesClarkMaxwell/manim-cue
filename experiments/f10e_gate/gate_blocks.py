"""B7: ręczna próba produkcyjnego panelu bloków; tylko przy odblokowanym pulpicie."""

import argparse
import json
import time
from pathlib import Path
from types import SimpleNamespace

from manimcue.player import info
from manimcue.player.notes_complete import blocks
from manimcue.player.notes_overlay import DirtyBuffers

CASES = (
    ("wrap", "Długi zawinięty blok: po jednej klatce cały tekst bez wewnętrznego scrolla."),
    (
        "outside",
        "Przewiń panel, kliknij ostatni blok; pierwszy znak trafia do niego, kursor widoczny.",
    ),
    (
        "paste",
        "Ctrl+V: długi tekst ze schowka; po jednej klatce poprawna wysokość i widoczny kursor.",
    ),
    (
        "merge",
        "Backspace na początku / Delete na końcu: scalenie, kursor w złączeniu, bez kasowania liter.",
    ),
    ("width", "Zmień szerokość okna: po jednej klatce poprawna wysokość i widoczny kursor."),
    ("scale", "A−/A+, ponowna aktywacja: poprawna wysokość i widoczny kursor."),
    ("keys", "↑/↓ na krawędzi i repeat: jeden blok na klatkę; tekst bez zmian."),
    ("modifiers", "Shift/Ctrl/Alt/Super + ↑/↓/Backspace/Delete: brak przejścia do innego bloku."),
    (
        "focus",
        "Klik i pierwszy znak; Esc, utrata fokusu, popup i klik podpowiedzi: brak utraty tekstu.",
    ),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from imgui_bundle import hello_imgui, imgui, immapp

    text = "Pierwszy blok\n\n" + "Zażółć gęślą jaźń. " * 160 + "\n\nOstatni blok"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    path = args.output.parent / "B7.notes.md"
    if path.exists():
        raise FileExistsError(f"Wybierz nowy katalog wyników: {path}")
    slide = {"notes": text, "rendered_notes": text}
    runtime = {
        "dirty_notes": DirtyBuffers(),
        "app": SimpleNamespace(
            manifest={"presentations": [{"notes_file": str(path), "slides": [slide]}]}
        ),
    }
    preview = {"runtime": runtime, "now": time.monotonic(), "view_state": {}}
    params = hello_imgui.RunnerParams()
    params.platform_backend_type = hello_imgui.PlatformBackendType.glfw
    params.renderer_backend_type = hello_imgui.RendererBackendType.open_gl3
    params.ini_disable = True
    params.fps_idling.enable_idling = False
    params.app_window_params.window_title = "manim-cue D49 B7 — bloki"
    params.app_window_params.window_geometry.size = (1000, 700)
    results = {}
    size = 28
    selected = 0

    def save():
        missing = [name for name, _ in CASES if name not in results]
        args.output.write_text(
            json.dumps(
                {"gate": "B7", "results": results, "missing": missing}, ensure_ascii=False, indent=2
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def gui():
        nonlocal size, selected
        preview["now"] = time.monotonic()
        imgui.set_next_window_size((950, 650), imgui.Cond_.first_use_ever)
        imgui.begin("B7")
        name, instruction = CASES[selected]
        imgui.text_wrapped(f"{selected + 1}/{len(CASES)} {name}: {instruction}")
        for label in ("PASS", "FAIL"):
            if imgui.button(label):
                state = runtime.get("notes_edit", {})
                results[name] = {
                    "status": label,
                    "size": size,
                    "span": state.get("span"),
                    "visual_rows": preview["view_state"].get("visual_rows"),
                    "text_length": len(state.get("text", "")),
                }
                save()
                selected = min(selected + 1, len(CASES) - 1)
            imgui.same_line()
        if imgui.button("Poprzednia próba"):
            selected = max(0, selected - 1)
        for label, delta in (("A−", -2), ("A+", 2)):
            imgui.same_line()
            if imgui.button(label):
                info.deactivate_notes(preview)
                size = max(16, min(48, size + delta))
        imgui.same_line()
        if imgui.button("Aktywuj długi blok"):
            state = info.enter_notes(runtime, [0, 0], preview["now"])
            info.activate_block(preview, blocks(state["text"])[1])
        imgui.same_line()
        if imgui.button("Tekst do wklejenia"):
            imgui.set_clipboard_text(
                "Wklejony tekst z polskimi literami żółć. " * 100 + "\n\nkoniec"
            )
        imgui.same_line()
        if imgui.button("Zakończ"):
            info.flush_notes(runtime, preview["now"], exiting=True)
            save()
            params.app_shall_exit = True
        imgui.begin_child(
            "panel", (0, 0), window_flags=imgui.WindowFlags_.always_vertical_scrollbar
        )
        imgui.push_font(None, size)
        snapshot = {"index": [0, 0], "notes_size": size}
        info.render_blocks(snapshot, preview, info.render_notes_status(snapshot, preview))
        imgui.pop_font()
        imgui.end_child()
        imgui.end()

    def load_font():
        runtime["editor_font"] = hello_imgui.load_font_ttf("fonts/Inconsolata-Medium.ttf", 28)

    params.callbacks.load_additional_fonts = load_font
    params.callbacks.show_gui = gui
    try:
        immapp.run(params, with_markdown=True)
    finally:
        save()
    return int(
        len(results) != len(CASES) or any(value["status"] != "PASS" for value in results.values())
    )


if __name__ == "__main__":
    raise SystemExit(main())
