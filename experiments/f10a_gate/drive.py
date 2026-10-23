"""Przeklikanie decku w playerze ImGui bez klawiatury: next co --dwell s i zrzuty viewportów.

Działa także przy zablokowanym ekranie: domyślny framebuffer okna jest wtedy niezdefiniowany,
więc draw data każdego viewportu (scena i Info) renderuje się drugi raz do FBO przed swapem.
Liczniki klatek bez vsync nie są pomiarem odbioru (zadanie 11), tylko diagnozą.

    uv run --frozen python experiments/f10a_gate/drive.py Demo --dwell 4 --output .tmp/drive
"""

import argparse
import json
import time
from pathlib import Path

from manimcue.player import app as app_module
from manimcue.player import desktop
from manimcue.player.manifest import model_to_manifest
from manimcue.slides.config import Config
from manimcue.slides.present import get_scenes_presentation_config

RUN = {"next_at": None, "capture": None, "shots": [], "stats": {}, "fbos": {}}
original_tick = app_module.App.tick


def tick(self, now, process_input=None):
    """Oryginalny tick, potem statystyka slajdu i zaplanowane next/quit."""
    state = original_tick(self, now, process_input)
    if RUN["next_at"] is None:
        RUN["next_at"] = now + RUN["dwell"]
    key = str(tuple(self.state["index"]))
    stats = RUN["stats"].setdefault(key, {"ticks": 0, "t0": now, "frames": {}})
    stats["ticks"] += 1
    stats["t1"] = now
    for name, frame in self.frames.items():
        marker = frame.get("frame_id", frame.get("texture"))
        stats["frames"].setdefault(name, set()).add(marker)
    if now >= RUN["next_at"] - 0.3 and RUN["capture"] is None and len(RUN["shots"]) < RUN["due"]:
        RUN["capture"] = len(RUN["shots"])
        RUN["shots"].append(
            {"index": key, "message": state.get("message"), "errors": self.errors[:]}
        )
    if now >= RUN["next_at"]:
        RUN["next_at"] = now + RUN["dwell"]
        RUN["due"] += 1
        total = sum(len(deck["slides"]) for deck in self.state["manifest"]["presentations"])
        self.dispatch({"type": "quit" if RUN["due"] > total + 1 else "next"}, now)
    return state


def _fbo(size):
    from OpenGL import GL

    if size not in RUN["fbos"]:
        texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, *size, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None
        )
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        RUN["fbos"][size] = GL.glGenFramebuffers(1)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, RUN["fbos"][size])
        GL.glFramebufferTexture2D(
            GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, texture, 0
        )
    return RUN["fbos"][size]


def capture():
    """Przed swapem: każdy viewport z draw data do FBO i do PNG."""
    if RUN["capture"] is None:
        return
    from imgui_bundle import imgui
    from OpenGL import GL
    from PIL import Image

    number, RUN["capture"] = RUN["capture"], None
    viewport_box = GL.glGetIntegerv(GL.GL_VIEWPORT)
    main = imgui.get_main_viewport().id_
    for viewport in imgui.get_platform_io().viewports:
        if not viewport.draw_data:
            continue
        size = int(viewport.size.x), int(viewport.size.y)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, _fbo(size))
        GL.glViewport(0, 0, *size)
        GL.glClearColor(0.5, 0, 0.5, 1)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        imgui.backends.opengl3_render_draw_data(viewport.draw_data)
        data = GL.glReadPixels(0, 0, *size, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        name = "stage" if viewport.id_ == main else "info"
        image = Image.frombytes("RGBA", size, data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        image.save(RUN["output"] / f"{name}_{number:02d}.png")
    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
    GL.glViewport(*viewport_box)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenes", nargs="+")
    parser.add_argument("--folder", type=Path, default=Path("slides"))
    parser.add_argument("--dwell", type=float, default=4.0)
    parser.add_argument("--output", type=Path, default=Path(".tmp/drive"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    RUN.update(dwell=args.dwell, output=args.output, due=1)

    from imgui_bundle import immapp

    real_run = immapp.run

    def run(params, add_ons=None):
        params.callbacks.before_swap = capture
        return real_run(params, add_ons)

    app_module.App.tick, desktop.App, immapp.run = tick, app_module.App, run
    manifest = model_to_manifest(get_scenes_presentation_config(args.scenes, args.folder))
    started = time.monotonic()
    code = desktop.run_desktop(
        manifest, {"config": Config().model_dump(), "hide_info_window": "never"}
    )
    stats = {
        key: {
            "loop_fps": round(item["ticks"] / max(item["t1"] - item["t0"], 1e-9), 1),
            "new_frames_per_s": {
                name: round(len(values) / max(item["t1"] - item["t0"], 1e-9), 1)
                for name, values in item["frames"].items()
            },
        }
        for key, item in RUN["stats"].items()
    }
    result = {
        "code": code,
        "seconds": round(time.monotonic() - started, 1),
        "shots": RUN["shots"],
        "stats": stats,
    }
    (args.output / "drive.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({"code": code, "shots": len(RUN["shots"])}))


if __name__ == "__main__":
    main()
