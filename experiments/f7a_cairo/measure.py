"""Pomiar Cairo bez adaptera, okna i zapisu filmu; uruchamiać z korzenia repo."""

import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path

import manim as m
import numpy as np

ROOT = Path(__file__).resolve().parent
WARMUP = 30
SAMPLES = 240


def build_case(name):
    """Odpowiedniki geometrii D22; przypadki sterowania dzielą geometrię."""
    scene = m.Scene()
    square = m.Square(2, fill_color="#FF0000", fill_opacity=1, stroke_width=0)
    scene.add(square)
    if name == "corners":
        scene.clear()
        for x, y, color in [
            (-6, 3, "#FF0000"),
            (6, 3, "#00FF00"),
            (-6, -3, "#0000FF"),
            (6, -3, "#FFFFFF"),
        ]:
            scene.add(
                m.Square(1, fill_color=color, fill_opacity=1, stroke_width=0).move_to([x, y, 0])
            )
    elif name == "add_remove":
        scene.add(
            m.Circle(1, fill_color="#0000FF", fill_opacity=1, stroke_width=0).shift(3 * m.RIGHT)
        )
    elif name == "updater_wait":
        scene.clear()
        square = m.Dot(radius=0.2, color=m.WHITE)
        scene.add(square)
    elif name == "tex":
        scene.clear()
        square = m.MathTex(r"\int_0^1 x\,dx").scale(2)
        scene.add(square)
    elif name.startswith("panel_"):
        square.set_fill(m.BLUE, opacity=0.5).set_stroke(m.WHITE, width=4).shift(3 * m.LEFT)
        circle = m.Circle(1, fill_color=m.RED, fill_opacity=0.5).shift(3 * m.RIGHT)
        scene.add(circle)
    elif name == "three_panel":
        square.set_fill("#00FF00")

    base = square.copy()

    def update(index):
        phase = (index % 120) / 120
        square.become(base)
        if name in {"move", "interrupt_two_plays", "updater_wait"}:
            square.move_to([-4 + 8 * phase, 0, 0])
        elif name in {"loop", "three_panel", "panel_rotate"}:
            square.rotate(phase * m.PI / 2)
        elif name == "panel_pulse":
            circle.set(width=2 * (1 + 0.6 * np.sin(np.pi * phase)))
        elif name == "panel_sweep":
            square.shift(6 * phase * m.RIGHT)
        elif name == "add_remove":
            square.set_opacity(phase)

    return scene, update


def stats(values):
    return {"median_ms": float(np.median(values)), "p95_ms": float(np.percentile(values, 95))}


def main():
    began = time.perf_counter()
    result = {
        "created_utc": datetime.now(UTC).isoformat(),
        "manim": m.__version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "warmup_frames": WARMUP,
        "sample_frames": SAMPLES,
        "method": "Full redraw update_frame; separate np.copyto RGBA bottom-up + letterbox; no pacing, IPC, updates or construction in timings",
        "cases": [],
        "excluded": {
            "three_d": "Poza 7a",
            "slow_build/cue_raises/build_raises": "Semantyka sterowania/błędu, nie koszt klatki; geometria first_frame",
            "idle_updater/static_wait": "Geometria first_frame; bezczynność docelowo bez renderu",
        },
    }
    names = [
        "first_frame",
        "corners",
        "move",
        "interrupt_two_plays",
        "add_remove",
        "updater_wait",
        "loop",
        "tex",
        "panel_rotate",
        "panel_pulse",
        "panel_sweep",
        "three_panel",
    ]
    for width, height in [(960, 540), (480, 270), (538, 648)]:
        scale = min(width / (128 / 9), height / 8)
        rw, rh = round((128 / 9) * scale), round(8 * scale)
        with m.tempconfig(
            {
                "renderer": "cairo",
                "format": "none",
                "disable_caching": True,
                "pixel_width": rw,
                "pixel_height": rh,
                "frame_width": 128 / 9,
                "frame_height": 8,
                "frame_rate": 60,
                "preview": False,
                "media_dir": str(ROOT.parents[1] / ".tmp" / "f7a-cairo"),
                "verbosity": "ERROR",
            }
        ):
            for name in names:
                try:
                    scene, update = build_case(name)
                except Exception as exc:
                    if name != "tex":
                        raise
                    result["cases"].append(
                        {"case": name, "buffer": [width, height], "skip": str(exc)}
                    )
                    continue
                assert not scene.session_spec.output.enabled
                target = np.zeros((height, width, 4), dtype=np.uint8)
                target[:, :, 3] = 255
                x, y = (width - rw) // 2, (height - rh) // 2
                render, copies, totals = [], [], []
                for i in range(WARMUP + SAMPLES):
                    update(i)
                    start = time.perf_counter_ns()
                    scene.renderer.update_frame(scene)
                    middle = time.perf_counter_ns()
                    np.copyto(target[y : y + rh, x : x + rw], scene.camera.pixel_array[::-1])
                    end = time.perf_counter_ns()
                    if i >= WARMUP:
                        render.append((middle - start) / 1e6)
                        copies.append((end - middle) / 1e6)
                        totals.append((end - start) / 1e6)
                assert scene.camera.pixel_array.shape == (rh, rw, 4)
                assert target.dtype == np.uint8
                assert np.array_equal(
                    target[y : y + rh, x : x + rw], scene.camera.pixel_array[::-1]
                )
                if name == "first_frame":
                    assert tuple(scene.camera.pixel_array[rh // 2, rw // 2]) == (255, 0, 0, 255)
                result["cases"].append(
                    {
                        "case": name,
                        "buffer": [width, height],
                        "render_size": [rw, rh],
                        "render": stats(render),
                        "copy": stats(copies),
                        "total": stats(totals),
                        "fps_total_mean": 1000 / float(np.mean(totals)),
                        "fps_total_median": 1000 / float(np.median(totals)),
                        "raw_render_ms": render,
                        "raw_copy_ms": copies,
                    }
                )
                print(width, height, name, round(1000 / np.mean(totals), 1), "fps", flush=True)
    result["elapsed_seconds"] = time.perf_counter() - began
    (ROOT / "results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
