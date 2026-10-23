# Author API

All model constructors take keyword arguments. Models use Pydantic validation and JSON
serialization. FilePath accepts a string or Path pointing to an existing file. Field defaults
are copied per instance. Import deck types from `manimcue.slides`; models are also available
from `manimcue.slides.config` without importing Qt or Manim.

## Slide and next_slide

`Slide(*args, output_folder=Path("slides"), **kwargs)` extends the selected engine Scene;
`ThreeDSlide` extends its 3D variant. CE 0.22 is selected normally; `render --GL` selects manimgl.
`args` and remaining `kwargs` go to the engine constructor. `output_folder: Path` is the deck
output directory. Implement `construct()` with ordinary Manim calls. CE requires a video output
plan. GL requires a real animation between boundaries; a bare `wait()` does not count there.

`next_slide(*, **options)` opens the next slide and closes the preceding animation segment.
It accepts every BaseSlideConfig field below; extra kwargs go to the engine boundary method.

| Field | Type | Default | Validation / behavior | Example |
| --- | --- | --- | --- | --- |
| loop | bool | False | Repeat base and main clips until navigation | `loop=True` |
| auto_next | bool | False | Advance automatically on completion | `auto_next=True` |
| playback_rate | float | 1.0 | Pydantic float; base speed | `playback_rate=2` |
| reversed_playback_rate | float | 1.0 | Pydantic float; reverse speed | `reversed_playback_rate=0.5` |
| notes | str | "" | Text shown as Markdown in Info | `notes="**Click** live"` |
| dedent_notes | bool | True | Remove common indentation | `dedent_notes=False` |
| skip_animations | bool | False | Omit segment from output | `skip_animations=True` |
| src | FilePath or None | None | External base; cannot combine with animations | `src=Path("picture.png")` |
| type | SlideType | Video | `video` or `image`; inferred when src is provided | `type=SlideType.Image` |
| direction | literal str | "horizontal" | horizontal or vertical (upstream export metadata) | `direction="vertical"` |
| layers | list[LiveLayer or ClipLayer] | [] | Ordered back to front; discriminated by kind | `layers=[panel]` |

Example: `self.next_slide(layers=[panel], notes="Click live; Esc returns"); self.play(...)`.
Use `self.add_to_canvas(title=title)` / `self.remove_from_canvas("title")` and `self.canvas`
for named objects retained across slides. Render controls (class attributes) are
`disable_caching: bool=False`, `flush_cache: bool=False` (deck cache only),
`skip_reversing: bool=False`, `max_duration_before_split_reverse: float|None=4.0`,
and `num_processes: int|None=None`. Engine-specific Scene methods retain engine semantics.

## Rectangles and Keyframe

A Rect is `(x, y, width, height)` in fractions of the slide frame, origin at top left.
All four numbers must be finite, dimensions positive. Live's initial rect must lie inside
[0,1]; clip rects and keyframe rects may extend outside it.

| Keyframe field | Type | Default | Validation | Example |
| --- | --- | --- | --- | --- |
| t | float | required | Finite, nonnegative seconds | `t=1.5` |
| rect | Rect | required | Finite, positive dimensions | `rect=(0.1,0.1,0.4,0.4)` |

`Keyframe(t=0, rect=(1,0.3,0.2,0.2))` starts outside the right edge. In a layer,
`keyframes` must have strictly increasing times. `layer.rect_at(t)` linearly interpolates,
clamps before/after the first/last keyframe, and uses rect when the list is empty. If the first
keyframe is after zero, its rectangle already applies at zero. Main motion uses active slide
time excluding pauses; Info next-slide geometry stays at rect_at(0).

## LiveLayer

| Field | Type | Default | Validation / behavior | Example |
| --- | --- | --- | --- | --- |
| kind | literal str | "live" | Must be live | `kind="live"` |
| scene_file | FilePath | required | Existing Python file with the selected engine's live subclass | `scene_file=Path("examples/live_panel.py")` |
| scene_name | str | required | Class must inherit LiveScene (GL) or LiveSceneCE (Cairo) | `scene_name="Panel"` |
| rect | Rect | (0,0,1,1) | Inside frame; sets worker resolution | `rect=(0.55,0.1,0.4,0.4)` |
| keyframes | list[Keyframe] | [] | Strictly increasing t; scales rendered panel | `keyframes=[Keyframe(t=0, rect=(0,0,1,1))]` |
| engine | "manimgl" or "ce-cairo" | "manimgl" | Explicit live backend, independent of deck engine | `engine="ce-cairo"` |
| fps | positive int | 60 | Greater than zero | `fps=30` |
| session_id | str or None | None | Unique per slide; compatible adjacent occurrences reuse process | `session_id="panel"` |
| enter_cue | str or None | None | Nonempty single line; named cue on forward entry and checkpoint replay | `enter_cue="rotate"` |
| background_opacity | float | 1.0 | Finite [0,1]; camera and letterbox background | `background_opacity=0` |
| active_border | BorderStyle or None | yellow 6px, opacity 1 | None disables drawing, not focus | `active_border=BorderStyle(color="cyan")` |
| error_border | BorderStyle or None | #dc2828 6px, opacity 1 | None disables drawing, not error status | `error_border=None` |
| thumbnail | FilePath or None | None | Generated first-frame PNG during render | `thumbnail=None` |

Example: `LiveLayer(scene_file=Path("examples/live_panel.py"), scene_name="Panel", background_opacity=0)`.
For Cairo use `LiveLayer(scene_file=Path("examples/live_panel_ce.py"), scene_name="Panel", engine="ce-cairo")`.
`size((width,height))` returns pixel dimensions, rounded and clamped to at least one pixel.
Adjacent occurrences of a session must match resolved file, class, engine, fps, pixel size and
background_opacity. Position, entry cue and border styles may differ. A gap starts a new
generation and allows different settings. Forward next/auto-next/skip-all saves a checkpoint
before sending the target entry cue. Previous (←) and reverse (V) restore the checkpoint of
the entry being left: the live state left on the target slide, including its manual cues.
They do not run the target entry cue. Replay (R) restores the current entry's beginning and
runs its entry cue once after the preparation barrier; without a cue it only restores.
In reverse, the base stays in reverse and clips retain their end frames while the live cue
runs forwards. Returning from reverse to normal playback and repeating a loop leave live alone.
Forward entry after going back discards the old future and saves a new checkpoint.
The retained frame keeps alpha and
composites over the new base. The full rectangle captures clicks, including transparent pixels.
The worker renders the whole default 16:9 camera isotropically, with letterbox bars.

Checkpoint scope is one presentation instance, compatible adjacent `session_id` run and
worker generation. Opening a presentation at any index saves the fresh build without running
an entry cue. A cold forward transition (including after an error or a presentation boundary)
saves the fresh build and runs the target cue; cold previous/reverse saves it without a cue.
Replay of that local beginning runs the target cue. Earlier entries are not reconstructed.
Without `session_id`, the per-slide worker lifecycle remains unchanged and R does not restore live.

Preparation reserves the worker against manual next/back, named cues and GL camera gestures,
including while waiting in `start_paused`. Restore completes while paused; entry cue execution
waits for the first actual group start. The base/clips wait for the checkpoint/restore status
**and its matching received frame**, then start together. Cancelled operations are drained and
acknowledged without compositing their frames. Preparation has a single five-second deadline;
the existing boundary acknowledgement timeout remains two seconds. Timeout stops the uncertain
worker and lets recorded media proceed; late results cannot rejoin the composition.

The shared Info/S status distinguishes `zapis stanu wejścia`, `checkpoint gotowy`,
`przywrócono stan pozostawiony na N`, `przywrócono początek N`, cue sent/start/completion,
interruption, unsent cue and unknown result. `stan live nieprzywrócony: <reason>` persists
over ordinary READY/cue messages until a valid preparation succeeds. Missing/evicted states
keep the last valid image and skip the entry cue. Partial restoration errors stop the worker.

There are at most 50 entry checkpoints and 256 MiB of accounted snapshot/history data per
worker, with shared snapshots counted once and a conservative working-copy reserve. This is
not an RSS bound. Old unprotected entries may be evicted; the current entry and active restore
are protected. Accounting includes the current data of original objects retained by checkpoints,
even after removal from the scene; restore reserves for the largest source/target/original graph.
No disk snapshot, cue retransmission or cross-generation restore is performed.
The supported graph consists of standard panel mobjects and numeric/style data, scene lists,
shared child references, updater callable references and logical time, plus sequence history.
Scene attributes, mutable closures, RNG and external effects are outside the guarantee and
cannot all be detected. Identical replay requires deterministic cues and identical interruption.

For example, use the same layer on two adjacent slides:

```python
panel = LiveLayer(scene_file=Path("examples/live_panel_ce.py"), scene_name="Panel",
                  engine="ce-cairo", session_id="panel", enter_cue="rotate")
self.next_slide(layers=[panel.model_copy()])
self.play(square.animate.shift(RIGHT))
self.next_slide(layers=[panel.model_copy()])
self.play(square.animate.shift(LEFT))
```

The author scene defines `rotate` in `PRESETS`. After the second entry, ← restores the state
left on the first; R restores that entry's beginning and runs `rotate` forwards.

Opacity guarantees apply to empty background and bars. Arbitrary translucent GL shapes,
strokes and overlaps retain upstream shader blending behavior; no universal straight/premultiplied
conversion is promised. Transport and thumbnails use straight RGBA. Thumbnail cache keys
include source bytes, class, engine, fps, size, opacity, CE adapter version and pixel interpretation version; changes in imported
modules require clearing the deck cache.

## BorderStyle

| Field | Type | Default | Validation / behavior | Example |
| --- | --- | --- | --- | --- |
| color | pydantic_extra_types.color.Color | #ffc800 | Pydantic CSS names, hex, rgb/rgba, hsl/hsla; no Qt import | `color="rgba(0,255,255,0.5)"` |
| width | float | 6.0 | Finite > 0; composition pixels, clamped to container dimensions | `width=10` |
| opacity | float | 1.0 | Finite [0,1], multiplied by color alpha | `opacity=0.7` |

`BorderStyle(color="cyan", width=10, opacity=0.7)` is JSON serializable; Color uses its
Pydantic string representation. One border follows the active layer, including an invisible
style. On release it follows the first failed layer, including an invisible error style.
Missing fields in older v2/v3 decks use defaults; explicit null disables a style.

## ClipLayer

| Field | Type | Default | Validation / behavior | Example |
| --- | --- | --- | --- | --- |
| kind | literal str | "clip" | Must be clip | `kind="clip"` |
| file | FilePath | required | Existing video or image | `file=slide_file("slides/Orbit.json",0)` |
| rect | Rect | (0,0,1,1) | May extend outside frame | `rect=(0.1,0.1,0.4,0.4)` |
| keyframes | list[Keyframe] | [] | Strictly increasing times | `keyframes=[Keyframe(t=0,rect=(0,0,1,1))]` |
| loop | bool | False | Independent looping; slide loop also loops main clips | `loop=True` |
| playback_rate | float | 1.0 | Finite > 0; multiplied by main base rate | `playback_rate=0.5` |
| thumbnail | FilePath or None | None | First frame generated by render | `thumbnail=None` |
| end_thumbnail | FilePath or None | None | Last frame generated by render; main reverse uses it | `end_thumbnail=None` |

`ClipLayer(file=slide_file("slides/Orbit.json",0), loop=True)` embeds recorded video.
`is_video` uses MIME type; images and GIF show a static first frame. All representations
preserve aspect ratio and center inside the full hit-test container. A nonlooping video over
a nonstatic base must cover base duration at the selected rates; the render validates this.
Info loops all videos independently at their layer rate and uses the normal first thumbnail;
it never starts a second live session. Main reverse freezes clips at their end thumbnails.

## slide_file and SceneView

`slide_file(json_path: Path|str, index: int) -> Path` returns a resolved base clip path from
an already rendered presentation. Index is zero-based (ordinary Python indexing); invalid
indices raise IndexError. It does not bake the source slide's layers into the returned clip.
Example: `file = slide_file("slides/Orbit.json", 0)`.

Import `SceneView` from `manimcue.scene_view`. Both engine implementations accept:

| Argument | Type | Default | Validation / behavior | Example |
| --- | --- | --- | --- | --- |
| scene | engine Scene | required | Host clock supplies absolute scene.time | `self` |
| file | Path or str | required | Decodable CFR video, opened by FrameSource | `slide_file("slides/Orbit.json",0)` |
| height | float or None | None | Engine scale_to_fit_height, when provided | `height=4` |
| loop | bool | False | Wrap source frames | `loop=True` |
| rate | float | 1.0 | Playback rate; no additional constructor validation | `rate=2` |
| kwargs | engine image kwargs | {} | Passed to engine ImageMobject | engine-specific |

`view = SceneView(self, file, height=4, loop=True); self.add(view)`.
Animate ordinary geometry, e.g. `self.play(view.animate.scale(0.5), run_time=2)`.
`pause()`, `resume()`, `seek(t)` are immediate commands returning self; seek uses source seconds
(no additional seek validation; use finite nonnegative values). Copies share playback/decoder state. Transform/become
between distinct sources guarantees geometry and opacity, not source transfer.

## LiveSceneCE (CE 0.22 Cairo)

Import `LiveSceneCE` from `manimcue.live_scene_ce`. Use `engine="ce-cairo"` in the
LiveLayer pointing to its subclass. CE and manimgl panels may coexist in the same deck.
The worker imports and configures its own engine in a separate spawned process, with
no application threads, window, encoder or movie cache. Keep `construct()` inherited;
override `build_objects()` and optionally CE `setup()` / `tear_down()`.

```python
from manim import RIGHT, Square
from manimcue.live_scene_ce import LiveSceneCE

class Panel(LiveSceneCE):
    def build_objects(self):
        self.square = Square()
        self.add(self.square)

    def move(self):
        self.play(self.square.animate.shift(RIGHT), run_time=1)
        self.wait(0.5)

    PRESETS = {"move": move}
    SEQUENCE = ["move"]
    LOOPS = set()
```

All three class fields default to empty containers in CE. Cues use ordinary CE
animations and waits. Static waits publish a changed starting image once, then produce
no repeated interior frames; updater waits and
`stop_condition` waits update on the live clock. `frozen_frame=True` suppresses updaters;
combining it with a stop condition is rejected by CE. A condition that ends early advances
logical time only by the elapsed duration. Between cues updaters and logical time freeze.
`next_section(skip_animations=True)` is rejected. Mutating renderer/output configuration
during build/cues and overriding the renderer or `construct()` are outside the author API.

On interruption, all remaining plays in the callable finish without waiting, and logical
time reaches their end; skipped updater dt is not simulated. Shutdown instead exits the
callable immediately. Blocking Python code requires the supervisor's two-second kill fallback.
Errors include the scene and cue; teardown runs once, preserving the original error.

Back retains original standard Mobject/VMobject identities, shared submobject edges,
scene/foreground lists, logical scene time, geometry, styles and callable updater references. It interpolates
each compatible node once for 0.6 s, then restores the exact saved graph, including changed
child counts and added/removed objects. New or structurally incompatible geometry appears
at the final boundary. Python attributes outside the mobject graph, closure state and
external resources are not checkpoints. History stores up to 50 sequence positions;
named cues add no entries. Back after next → named cue returns before next in both engines.
Mobject copies and animation targets retain references to the running LiveSceneCE in bound
updaters; cloning the live scene or its IPC resources is unsupported.

The CE camera is fixed 2D; view commands are ignored. Animated cameras, pan/zoom/reset,
3D, arbitrary custom object graphs and arbitrary translucent-content correction are deferred.
The whole camera is letterboxed into `LiveLayer.size(deck_resolution)`, preserving alpha
of empty background/bars. A 538×648 panel contains 538×303 content at (0,172).
First-frame thumbnails use the same worker and straight RGBA as live. Source dependencies
still require a cache flush when changed. JSON v4 records engine; v2/v3 migrate to manimgl.

`LiveSpec(scene_file, scene_name, width=960, height=540, fps=60,
background_opacity=1.0, engine="manimgl")` keeps existing positional arguments intact.
Use `LiveSession.start(spec)`, `poll()`, `send(command)`, `try_read_frame()` and
`request_stop()` from `manimcue.live_session`; GUI calls do not wait for build or rendering.
`capture_first_frame(spec, timeout=120)` is a blocking utility for offline thumbnail creation.

## LiveScene and cue protocol

Import `LiveScene` from `manimcue.live_scene` (manimgl only). Do not override construct;
implement `build_objects(self) -> None`, add mobjects and assign any attributes used by cues.
`self.play`, `self.wait`, `self.add`, and the camera frame use manimgl semantics.

| Class field | Type | Default | Validation / behavior | Example |
| --- | --- | --- | --- | --- |
| PRESETS | dict[str, callable(self)] | rotate, pulse, sweep methods | Unknown name logs warning; callable runs in scene process | `{"spin": cue_spin}` |
| SEQUENCE | list[str] | ["rotate","pulse","sweep"] | Names in PRESETS; Right/next advances | `["spin"]` |
| LOOPS | set[str] | {"pulse"} | Cue names repeated until next command | `set()` |

See `examples/live_three.py` for a complete subclass. `SEQUENCE` and `PRESETS` must be
consistent; no independent schema validator is applied to class fields. Offline movie output
is rejected for LiveScene; run it with a window or through a managed live worker.

Standalone: `uv run manimgl examples/live_panel.py Panel`.
TCP binds 127.0.0.1, default port 47821; environment `MANIMCUE_PORT` overrides it. The printed
endpoint is authoritative. Each UTF-8 line is a command; only local trusted clients are intended.
`next` advances, `back` restores the last sequence snapshot; named presets do not move the cursor.
Commands arriving during play complete the current animation before the new command runs.
Right/Left in the live window map to next/back; keyboard has priority over queued socket input.
The player maps its configured keys after clicking a live panel, and Esc releases focus.
Mouse controls in the player send `view orbit dx dy`, `view pan dx dy`, `view zoom steps`,
and `view reset` to the worker.

Client: `uv run python -m manimcue.cue [options] command [command ...]`.
Control lines are limited to 512 UTF-8 bytes and the worker queue to 128 operations.
Embedded entry cue names use percent-encoded UTF-8 within that line limit; ordinary
manual cue names retain their existing newline-delimited representation.
`checkpoint`, `restore`, `enter`, `drop_checkpoint` and `release` are reserved embedded
control prefixes; use other names for manual presets.

| Argument | Type | Default | Validation / behavior | Example |
| --- | --- | --- | --- | --- |
| commands | one or more str | required | Newline-delimited commands | `rotate pulse` |
| --port | int | MANIMCUE_PORT or 47821 | TCP destination | `--port 47822` |
| --mode | line/together/split | line | Separate sends / one send / split first command | `--mode together` |
| --delay | float | 0 | Sleep before send, seconds | `--delay 1` |
| --hold | float | 0 | Keep connection after send, seconds | `--hold 5` |

## Rendered models and compatibility

`SlideConfig` contains all next_slide fields plus required `file: FilePath` and
`rev_file: FilePath`. `PresentationConfig` contains `version: int=4` (newer versions rejected),
`slides: list[SlideConfig]` (required, nonempty), `resolution: tuple[positive int,positive int]`
(default 1920×1080), and `background_color: Color` (black). `from_file(Path)` resolves stored
paths and validates session runs; `to_file(Path)` serializes the current paths without rebasing. v2 live layers
without kind remain readable. Exporting layered decks to upstream file converters is rejected.

`Config.keys` retains the upstream key mapping plus S for presenter state; duplicate effective
key codes are rejected. `.manim-slides.toml` remains the configuration filename. See README
for the complete default key table and SPEC.md for D17/D20/D27–D41 contracts.


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
