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
| scene_file | FilePath | required | Existing Python file with LiveScene subclass | `scene_file=Path("examples/live_panel.py")` |
| scene_name | str | required | Class looked up by worker; must inherit LiveScene | `scene_name="Panel"` |
| rect | Rect | (0,0,1,1) | Inside frame; sets worker resolution | `rect=(0.55,0.1,0.4,0.4)` |
| keyframes | list[Keyframe] | [] | Strictly increasing t; scales rendered panel | `keyframes=[Keyframe(t=0, rect=(0,0,1,1))]` |
| fps | positive int | 60 | Greater than zero | `fps=30` |
| session_id | str or None | None | Unique per slide; compatible adjacent occurrences reuse process | `session_id="panel"` |
| enter_cue | str or None | None | Nonempty single line; named cue on committed forward entry | `enter_cue="rotate"` |
| background_opacity | float | 1.0 | Finite [0,1]; camera and letterbox background | `background_opacity=0` |
| active_border | BorderStyle or None | yellow 6px, opacity 1 | None disables drawing, not focus | `active_border=BorderStyle(color="cyan")` |
| error_border | BorderStyle or None | #dc2828 6px, opacity 1 | None disables drawing, not error status | `error_border=None` |
| thumbnail | FilePath or None | None | Generated first-frame PNG during render | `thumbnail=None` |

Example: `LiveLayer(scene_file=Path("examples/live_panel.py"), scene_name="Panel", background_opacity=0)`.
`size((width,height))` returns pixel dimensions, rounded and clamped to at least one pixel.
Adjacent occurrences of a session must match resolved file, class, fps, pixel size and
background_opacity. Position, entry cue and border styles may differ. A gap starts a new
generation and allows different settings. Forward next/auto-next/skip-all sends entry cues;
previous/reverse/replay does not undo or repeat them. The retained frame keeps alpha and
composites over the new base. The full rectangle captures clicks, including transparent pixels.
The worker renders the whole default 16:9 GL camera isotropically, with letterbox bars.

Opacity guarantees apply to empty background and bars. Arbitrary translucent GL shapes,
strokes and overlaps retain upstream shader blending behavior; no universal straight/premultiplied
conversion is promised. Transport and thumbnails use straight RGBA. Thumbnail cache keys
include source bytes, class, size, opacity and pixel interpretation version; changes in imported
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

| Argument | Type | Default | Validation / behavior | Example |
| --- | --- | --- | --- | --- |
| commands | one or more str | required | Newline-delimited commands | `rotate pulse` |
| --port | int | MANIMCUE_PORT or 47821 | TCP destination | `--port 47822` |
| --mode | line/together/split | line | Separate sends / one send / split first command | `--mode together` |
| --delay | float | 0 | Sleep before send, seconds | `--delay 1` |
| --hold | float | 0 | Keep connection after send, seconds | `--hold 5` |

## Rendered models and compatibility

`SlideConfig` contains all next_slide fields plus required `file: FilePath` and
`rev_file: FilePath`. `PresentationConfig` contains `version: int=3` (newer versions rejected),
`slides: list[SlideConfig]` (required, nonempty), `resolution: tuple[positive int,positive int]`
(default 1920×1080), and `background_color: Color` (black). `from_file(Path)` resolves stored
paths and validates session runs; `to_file(Path)` serializes the current paths without rebasing. v2 live layers
without kind remain readable. Exporting layered decks to upstream file converters is rejected.

`Config.keys` retains the upstream key mapping plus S for presenter state; duplicate effective
key codes are rejected. `.manim-slides.toml` remains the configuration filename. See README
for the complete default key table and SPEC.md for D17/D20/D27–D35 contracts.
