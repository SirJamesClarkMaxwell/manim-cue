# manim-cue

A fork of [manim-slides 5.7.0](https://github.com/jeertmans/manim-slides) with live Manim
scenes and composited video/image layers. Render slides with Manim CE 0.22 or manimgl,
then present them with notes, an animated next-slide preview and interactive live panels.

## Install and try

From the cloned repository, run `powershell -ExecutionPolicy Bypass -File scripts/setup.ps1`
on Windows, or `bash scripts/setup.sh` on Linux/macOS. The scripts install uv if missing,
run `uv sync` and render Orbit followed by Demo. Initial installation needs internet access.
They warn if ffmpeg is missing from PATH (needed for manimgl `render --GL`).

Requirements: Python ≥ 3.13 (uv downloads it if needed) and an OpenGL 3.3 driver for live
panels. On Linux, Manim CE also needs the Cairo/Pango development packages
(e.g. `sudo apt install build-essential pkg-config libcairo2-dev libpango1.0-dev`).

Manual setup, with [uv](https://docs.astral.sh/uv/) already installed:

```bash
uv sync
uv run --frozen manim-cue render examples/orbit.py Orbit
uv run --frozen manim-cue render examples/demo.py Demo
uv run manim-cue present Demo
```

Rendered decks go into `slides/`. To render with manimgl, add `--GL` immediately after
`render`; render Orbit before Demo with the same engine.

| Key or action | Player behavior |
| --- | --- |
| Right / Left | Next / previous slide |
| Space | Pause/resume base, clips and layer motion; live continues |
| R / V | Replay / reverse previous slide |
| F / H | Fullscreen / hide mouse |
| S | Show presenter state on the presentation screen |
| Q | Quit |
| Click live / Esc | Give keyboard focus to live / return focus to slides |
| Drag / Shift-drag / wheel / double-click | Orbit / pan / zoom / reset live camera |

The Info window shows notes, current composition and the next slide. Move it to your second
monitor; fullscreen mode assigns separate screens when two are available. On one monitor,
run `uv run manim-cue present Demo --show-info-window` to show Info explicitly. Before slides 5
and 8, watch the clip in the next-slide preview. On slide 9, the blue square moves behind the
transparent live panel and its letterbox bars. Click the panel to see its custom border.

## Author a deck

Use `from manimcue.slides import Slide` for either CE or GL (selected by the render command).
`ThreeDSlide` is also exported. Options passed to `next_slide` describe the slide it opens.

```python
from pathlib import Path
from manimcue.slides import BorderStyle, ClipLayer, Keyframe, LiveLayer, Slide, slide_file

class MyDeck(Slide):
    def construct(self):
        self.next_slide(
            notes="Click live; Esc returns to slides.",
            layers=[
                ClipLayer(file=slide_file("slides/Orbit.json", 0), loop=True,
                          keyframes=[Keyframe(t=0, rect=(0.05, 0.1, 0.4, 0.4))]),
                LiveLayer(scene_file=Path("examples/live_panel.py"), scene_name="Panel",
                          rect=(0.55, 0.1, 0.4, 0.4), session_id="panel", enter_cue="rotate",
                          background_opacity=0, fps=60, thumbnail=None,
                          active_border=BorderStyle(color="cyan", width=10, opacity=0.7),
                          error_border=None),
            ],
        )
        self.wait(2)
```

[`examples/demo.py`](examples/demo.py) is the complete working deck. `LiveLayer` also supports
`keyframes` and the discriminator `kind="live"`; `ClipLayer` has `rect`, `loop`, `playback_rate`, `thumbnail`, `end_thumbnail`, `keyframes` and `kind="clip"`.
`Keyframe(t=..., rect=...)` interpolates a layer rectangle in active slide time. `slide_file(json, index)`
resolves another rendered deck's base clip (zero-based index).
`SceneView(self, file, height=4, loop=True)` embeds a clip as an animatable Manim mobject;
import it from `manimcue.scene_view`. See the [complete author API](docs/api.md) for all fields,
defaults, validation and examples.

## Author a live scene

Subclass `manimcue.live_scene.LiveScene`, implement `build_objects`, and register methods
in `PRESETS` (name → callable taking self). `SEQUENCE` lists names for Right; `LOOPS` is the set
of cues repeated until the next command. See `examples/live_panel.py` and `examples/live_three.py`.
In a standalone live window, Right advances the sequence and Left restores its last snapshot.
A new command interrupts an animation by completing its current animation state.

```bash
uv run manimgl examples/live_panel.py Panel
uv run python -m manimcue.cue rotate
uv run python -m manimcue.cue next back
```

TCP accepts newline-delimited cue names on localhost; `next`/`back` move the sequence cursor,
named cues do not. `MANIMCUE_PORT` sets the standalone port (default 47821); the endpoint is
printed on startup. The client also accepts `--port`. Embedded live workers use private ports.

## How it works

The player composites the base and ordered layers in one Qt scene shared by the main and
current Info views. Each live panel runs manimgl in a separate process, with one application
thread per process. RGBA frames cross shared memory, while TCP carries cue commands and
status. Adjacent slides with the same compatible `session_id` reuse a live process and its
last frame. Base video and clips prepare their first frames behind a readiness barrier;
live entry cues wait for READY before the group starts. D17 guarantees shared start and pause
for recorded layers, with accepted drift rather than frame locking; live continues during
player pause. The next-slide preview uses independent muted video loops and static live thumbnails.

## Examples and tests

| File in `examples/` | Purpose |
| --- | --- |
| `orbit.py` | Reusable prerecorded Orbit clip; render first |
| `demo.py` | Nine-slide tour: loops, live 2D/3D, clip motion, SceneView, persistent cues, transparency |
| `live_panel.py` | Interactive 2D presets and 3D camera panel |
| `live_three.py` | Deterministic entry cue for the three-source demonstration |
| `live_receiver.py` | Shared-memory live receiver demonstration |
| `measure_live.py` | Live pipeline timing measurements |
| `measure_player.py` | Player transition measurements |

Run `uv run pytest` (or `uv run --frozen pytest -q -p no:cacheprovider`). GL tests require a
working OpenGL driver; window interaction and two-monitor behavior need a human trial.

## Limits and provenance

Live entry cues are not undone by previous/reverse/replay slide navigation. Transparent live
backgrounds and letterbox bars are supported; arbitrary translucent GL objects retain manimgl's
shader blending behavior. Alpha in prerecorded CE/GL clips and reverse encoding is outside
the supported contract. manimgl is the only live backend; CE is for prerecorded slides.
The next-slide preview freezes layer geometry at `rect_at(0)` and allows independent loop drift.
Layered decks cannot be exported through the upstream file converters.

The fork retains the MIT license, © Jérome Eertmans, in
[src/manimcue/slides/LICENSE.md](src/manimcue/slides/LICENSE.md). Compared with upstream,
imports use `manimcue.slides`, the CLI is `manim-cue`, IPython magic and the Sphinx directive
are removed, and PyPI version checks are disabled. `.manim-slides.toml` and the upstream logger
name remain compatible. Architectural decisions are in [SPEC.md](SPEC.md), implementation
contracts in [PLAN.md](PLAN.md), and reviews in [REVIEW-LOG.md](REVIEW-LOG.md) (all in Polish).
