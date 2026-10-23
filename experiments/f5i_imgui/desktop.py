"""PoC ImGui na PC: baza + N klipów 1080p60, panel live manim-cue i okno Info z podglądem następnego slajdu.

uv run --frozen --with imgui-bundle==1.93.0 --with pyopengl python experiments/f5i_imgui/desktop.py --clips 3
Wynik (JSON) na stdout albo do --output. Mierzy wgrania klatek do tekstur i klatki renderu ImGui,
nie fizyczne odświeżenie monitora.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MEDIA = ROOT / ".tmp" / "f5i-media"


def media(resolution):
    """Te same syntetyczne filmy CE co `examples/measure_clips.py`, renderowane raz do `.tmp`."""
    sys.path.insert(0, str(ROOT / "examples"))
    from measure_clips import make_video

    folder = MEDIA / f"{resolution[0]}x{resolution[1]}"
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(4):
        target = folder / f"{index}.mp4"
        if not target.exists():
            target.write_bytes(
                make_video(folder / "render", str(index), resolution, base=index == 0).read_bytes()
            )
        paths.append(target)
    return paths


def build(args, paths):
    from sources_desktop import LiveSource, VideoSource
    from stage import LIVE_RECT, NOTES, Layer, Slide, clip_rect

    def slide(with_live):
        layers = [
            Layer(f"clip_{i + 1}", clip_rect(i), VideoSource(paths[i + 1], size=args.clip_size))
            for i in range(args.clips)
        ]
        if with_live:
            from manimcue.live_session import LiveSpec

            width, height = round(LIVE_RECT[2] * 1920), round(LIVE_RECT[3] * 1080)
            spec = LiveSpec(
                str(ROOT / "tests/scenes/live_gl.py"), "LiveGLLoopBoundary", width, height, 60
            )
            layers.append(
                Layer(
                    "live",
                    LIVE_RECT,
                    LiveSource(spec, cue="spin"),
                    aspect=width / height,
                    border=True,
                )
            )
        return Slide(NOTES, VideoSource(paths[0]), layers)

    current = slide(not args.no_live)
    preview = None if args.no_info else slide(False)
    return current, preview


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clips", type=int, default=3)
    parser.add_argument("--resolution", default="1920x1080")
    parser.add_argument(
        "--clip-size", default=None, help="WxH konwersji klipów, domyślnie rozmiar filmu"
    )
    parser.add_argument("--window", default="1600x900")
    parser.add_argument("--warmup", type=float, default=3.0)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--no-live", action="store_true")
    parser.add_argument("--no-info", action="store_true")
    parser.add_argument(
        "--no-vsync", action="store_true", help="render bez limitu (zapas wydajności)"
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--screenshot", type=Path, help="PNG ostatniej klatki okna")
    args = parser.parse_args()
    resolution = tuple(int(v) for v in args.resolution.split("x"))
    args.clip_size = tuple(int(v) for v in args.clip_size.split("x")) if args.clip_size else None
    paths = media(resolution)

    from imgui_bundle import hello_imgui
    from stage import Stage, runner_params

    state = {}

    def done(result):
        result.update(clips=args.clips, live=not args.no_live, resolution=list(resolution))
        state["result"] = result
        hello_imgui.get_runner_params().app_shall_exit = True

    def post_init():
        current, preview = build(args, paths)
        state["stage"] = Stage(
            [current], preview, not args.no_info, args.warmup, args.seconds, done
        )

    def gui():
        state["stage"].gui()

    def before_exit():
        stage = state.get("stage")
        if stage is not None:
            for source in stage.sources():
                source.close()

    size = tuple(int(v) for v in args.window.split("x"))
    params = runner_params(
        post_init, gui, before_exit, "manim-cue: PoC ImGui", size, True, not args.no_vsync
    )
    hello_imgui.run(params)
    if args.screenshot:
        from PIL import Image

        Image.fromarray(hello_imgui.final_app_window_screenshot()).save(args.screenshot)

    text = json.dumps(state.get("result", {"error": "brak wyniku"}), indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
