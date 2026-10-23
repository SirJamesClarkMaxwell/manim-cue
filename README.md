# manim-cue

A fork of [manim-slides 5.7.0](https://github.com/jeertmans/manim-slides) with live Manim
scenes and composited video/image layers. Render slides with Manim CE 0.22 or manimgl,
then present them with notes, an animated next-slide preview and interactive live panels.

## Install and try

From the cloned repository, run `powershell -ExecutionPolicy Bypass -File scripts/setup.ps1`
on Windows, or `bash scripts/setup.sh` on Linux/macOS. The scripts install uv if missing,
run `uv sync` and render Orbit followed by Demo. Initial installation needs internet access.
They warn if ffmpeg is missing from PATH (needed for manimgl `render --GL`).

Requirements: Python ≥ 3.13 (uv downloads it if needed) and an OpenGL 3.3 driver for manimgl live
panels; CE Cairo live panels do not need OpenGL. On Linux, Manim CE also needs the Cairo/Pango development packages
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
| MMB / Shift+MMB drag | Orbit / pan the manimgl live camera |
| Alt+LMB / Alt+Shift+LMB / Alt+RMB drag | Touchpad orbit / pan / zoom |
| Wheel / LMB double-click | Zoom / reset to the last cue boundary |

The Info window shows notes, current composition and the next slide. Move it to your second
monitor; fullscreen mode assigns separate screens when two are available. On one monitor,
run `uv run manim-cue present Demo --show-info-window` to show Info explicitly. Before slides 5
and 8, watch the clip in the next-slide preview. On slide 9, the blue square moves behind the
transparent live panel and its letterbox bars. Click the panel to see its custom border.

Camera gestures require an already focused live panel and a press inside its container.
The first click grants focus; dragging plain LMB leaves the camera still. A captured drag
continues outside the panel until release. Losing focus, changing slides or reserving an
entry cancels it. Wheel zoom requires the pointer over the active panel. Cairo ignores views.

ImGui Info uses two columns: the current composition and presenter timer on the left,
the independently playing next slide and scrollable Markdown notes on the right.
Timer pause/restart affects only presenter time; restart preserves its paused state.
A−/A+ changes notes and math from 16 to 48 logical pixels (default 24), for the session.
Notes support `$inline$` and `$$display$$` math with local MicroTeX and an Agg fallback.
Invalid formulas remain visible with an error. The bottom strip lazily loads static
thumbnails for the current deck; clicking one jumps directly through the normal entry
barrier. Clicking the current slide does nothing. A jump starts local live history without
an entry cue; a compatible adjacent session may stay alive. Earlier history is discarded.

With ImGui live focus, a physical Right at the end of the **whole sequence**, or Left at
its beginning, returns focus and invokes the usual slide action after the boundary image
is acknowledged. Held-key repeat never advances through this boundary. Pause, loops,
reverse and end-of-deck rules still apply. Qt keeps live focus at sequence boundaries.

## Live Cairo panels

Select the live engine independently of the deck render engine:

```python
LiveLayer(scene_file=Path("examples/live_panel_ce.py"), scene_name="Panel",
          engine="ce-cairo", rect=(0.1, 0.1, 0.4, 0.6),
          session_id="cairo-panel", enter_cue="rotate", background_opacity=0)
```

Import `LiveSceneCE` from `manimcue.live_scene_ce` and implement `build_objects()`;
define `PRESETS`, `SEQUENCE` and `LOOPS` as in `examples/live_panel_ce.py`.
Cues use ordinary CE `self.play()` and `self.wait()`. Keep `construct()` inherited.
Demo slides 10–11 contain two Cairo panels and an Orbit clip, with persistent sessions.
The default live engine is `manimgl`; choosing Cairo does not translate GL objects.
Deck JSON now uses format v4; v2/v3 live layers load as manimgl.

Cairo live supports CE 0.22 2D with a fixed camera and an isotropic 16:9 image inside
the panel. Camera gestures are ignored. Right advances the sequence; Left interpolates
back over 0.6 s. Named entry cues do not add history: Back restores the state before
the last sequence cue, including changes made by intervening named cues. History retains
50 sequence positions. Snapshot support covers standard 2D panel objects, shared children,
add/remove, geometry, styles and updater references; arbitrary Python state and updater
closure state are not restored. Interrupting a cue finishes its animations and logical time,
without simulating the skipped time of independent updaters. Live keeps running while
the base and clips are paused. Empty background and letterbox bars preserve alpha;
arbitrary translucent content follows upstream Cairo blending.

For a standalone window test:

```bash
uv run --frozen python examples/live_receiver.py examples/live_panel_ce.py Panel --engine ce-cairo
```

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
current Info views. Each live panel runs ManimGL or CE Cairo in a separate process, with one application
thread per process. RGBA frames cross shared memory, while TCP carries cue commands and
status. Adjacent slides with the same compatible `session_id` reuse a live process and its
last frame. Each committed entry saves a checkpoint, including manual sequence history.
Base video, clips and live checkpoint/restore operations prepare behind a readiness barrier;
the group starts after the matching live boundary frame arrives. D17 guarantees shared start and pause
for recorded layers, with accepted drift rather than frame locking; live continues during
player pause. The next-slide preview uses independent muted video loops and static live thumbnails.

For adjacent compatible sessions, **←** restores the live state left on the previous slide,
including manual cues performed there. **V** restores that same boundary state while the base
plays the previous slide in reverse and clips show their last frames. Live does not run backwards.
**R** restores the checkpoint before the current entry and runs its `enter_cue` once, forwards,
even when the base is in reverse. Without `enter_cue`, R only restores the checkpoint.
Forward navigation after going back creates a new branch from the current live state.
Loop repetitions and reverse-to-normal playback do not repeat live entry cues.

Initial opening (including starting in the middle) builds a fresh scene without an entry cue;
a cold forward transition runs the target cue after saving the fresh build. Earlier slides
are never reconstructed. Gaps, different presentations and failed/stopping workers start a
new generation. Layers without `session_id` keep their per-slide lifecycle without checkpoints.

Info and the optional S overlay show checkpoint preparation, the restored beginning or state
left on a slide, and entry cue start/completion. During preparation, including a paused start,
manual live cues and camera gestures are rejected until the worker accepts entry start/release.
Restore finishes while paused; the entry cue waits for playback. A five-second preparation
timeout stops the uncertain worker and lets the base/clips continue. A persistent
`stan live nieprzywrócony` message means the panel is stale; READY alone does not clear it.

## Examples and tests

| File in `examples/` | Purpose |
| --- | --- |
| `orbit.py` | Reusable prerecorded Orbit clip; render first |
| `demo.py` | Eleven-slide tour: loops, live 2D/3D, clip motion, SceneView, GL/CE checkpoints, transparency |
| `live_panel.py` | Interactive 2D presets and 3D camera panel |
| `live_three.py` | Deterministic entry cue for the three-source demonstration |
| `live_receiver.py` | Shared-memory live receiver demonstration |
| `measure_live.py` | Live pipeline timing measurements |
| `measure_player.py` | Player transition measurements |

Run `uv run pytest` (or `uv run --frozen pytest -q -p no:cacheprovider`). GL tests require a
working OpenGL driver; window interaction and two-monitor behavior need a human trial.

## Limits and provenance

Checkpoints cover standard panel mobjects, shared children, geometry, styles, updater callable
references and logical time, together with the sequence cursor/history. Compatible nodes
interpolate for 0.6 s before exact graph restoration; this is not a reversed recording.
Scene attributes, mutable closures, RNG and external resources are not restored or automatically
detected. Repeatable replay requires deterministic cues and the same interruption pattern.
The limit is 50 entry checkpoints and 256 MiB of accounted snapshot/history data, including
working-copy reserve; it is not a process RSS limit. Unsupported data or a missing/evicted
checkpoint leaves the last valid image with a persistent stale-state message and skips the cue.
Partial restore failure stops the worker. There is no history across processes or presentations.
Transparent live
backgrounds and letterbox bars are supported; arbitrary translucent GL objects retain manimgl's
shader blending behavior. Alpha in prerecorded CE/GL clips and reverse encoding is outside
the supported contract. CE live supports fixed-camera Cairo 2D panels; camera gestures and 3D
remain outside that backend's contract.
The next-slide preview freezes layer geometry at `rect_at(0)` and allows independent loop drift.
Layered decks cannot be exported through the upstream file converters.

The fork retains the MIT license, © Jérome Eertmans, in
[src/manimcue/slides/LICENSE.md](src/manimcue/slides/LICENSE.md). Compared with upstream,
imports use `manimcue.slides`, the CLI is `manim-cue`, IPython magic and the Sphinx directive
are removed, and PyPI version checks are disabled. `.manim-slides.toml` and the upstream logger
name remain compatible. Architectural decisions are in [SPEC.md](SPEC.md), implementation
contracts in [PLAN.md](PLAN.md), and reviews in [REVIEW-LOG.md](REVIEW-LOG.md) (all in Polish).


## ImGui player status (phase 10a)

Qt remains the default: `uv run --frozen manim-cue present Demo`.
The experimental desktop backend is selectable with
`uv run --frozen manim-cue present Demo --player imgui --show-info-window`.
The Windows and shared PC/Pyodide gates passed (commit ed012bb); desktop
integration is under acceptance, not a performance or full parity claim.

The backend uses GLFW/OpenGL3 and separate main/Info viewports. Media decoding
runs in supervised processes, while application code stays on one thread per
process. Live panels reuse the existing transport and checkpoint history.
Desktop audio is excluded: one warning is emitted per material with an audio
track. Use Qt when audio is needed. The web backend is a later phase.

See `reports/REPORT-10a.md` for test evidence, remaining acceptance checks
and network-dependent tests. Native window appearance,
DPI, focus, two-monitor use, vsync and performance still require acceptance
with an unlocked screen. The existing ImGui experiment remains a separate PoC.


Both desktop players warm two single-use live workers per engine used by the current
deck (ManimGL and/or CE Cairo). Idle workers import the backend without loading author
code, allocating frame SHM or creating a scene/GPU context. Active and retiring workers
share a deck-sized process budget with ImGui file decoders; a busy budget delays entry
through the existing five-second preparation deadline. Pools close on player shutdown.

ImGui PC also prepares one normal next slide after the current slide is ready, even
when Info is hidden. Files hold their first frame at t=0; live panels build objects and
hold their first frame without entry cues or checkpoint history. Author `build_objects`
code can therefore run before navigation, including its I/O effects. Only a committed
normal next adopts this work; backward/reverse/replay navigation, jumps, deck/spec
changes and failures discard it. Compatible adjacent live sessions take precedence.
Info preview remains independent. Speculative frame buffers and copies are limited to
128 MiB CPU+GPU; backend/scene RSS and VRAM are measured separately. Qt and web do not
prefetch. The 0.5-second p95 target remains subject to windowed acceptance.
