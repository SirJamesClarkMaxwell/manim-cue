"""Info: wspólny snapshot, niezależny podgląd i brak dekoderów po ukryciu."""

from types import SimpleNamespace

from manimcue.player.app import App
from manimcue.player.info import preview_target, state_text
from manimcue.player.live import LiveController


class FakeSource:
    def __init__(self):
        self.status = "ready"
        self.closed = False
        self.plays = []

    def prepare(self, entry_id, media):
        self.entry_id, self.media = entry_id, media

    def poll(self, now, target, budget_ms):
        return {
            "status": "ready",
            "frame_id": 1,
            "width": 1,
            "height": 1,
            "rgba": bytes(4),
            "pts": now % 1,
        }

    def play(self, now):
        self.plays.append(now)

    def pause(self):
        pass

    def request_close(self):
        self.closed = True

    def poll_closed(self, now):
        return self.closed


def manifest():
    return {
        "version": 1,
        "resolution": [100, 100],
        "presentations": [
            {"slides": [{"kind": "image", "file": "first", "notes": "**notes**"}]},
            {
                "resolution": [200, 100],
                "slides": [
                    {
                        "kind": "image",
                        "file": "next",
                        "layers": [
                            {
                                "kind": "image",
                                "file": "clip",
                                "keyframes": [
                                    {"t": 0, "rect": [0, 0, 0.5, 1]},
                                    {"t": 1, "rect": [0.5, 0, 0.5, 1]},
                                ],
                            }
                        ],
                    }
                ],
            },
        ],
    }


def make_app(**options):
    return App(
        manifest(),
        options,
        FakeSource,
        lambda update: SimpleNamespace(texture=1, close=lambda: None),
        LiveController(),
    )


def test_preview_target_resolution_normal_and_end():
    target = preview_target(manifest(), [0, 0])
    assert target["resolution"] == [200, 100] and target["index"] == [1, 0]
    assert preview_target(manifest(), [1, 0]) is None
    target["layers"].clear()
    assert manifest()["presentations"][1]["slides"][0]["layers"]


def test_hidden_preview_no_decoders_and_independent_motion():
    app = make_app(start_paused=True, show_info=False)
    assert not app.preview_sources
    app.set_info_visible(True)
    assert len(app.preview_sources) == 2
    now = app.started_at + 0.5
    state = app.tick(now)
    assert state["paused"] and state["notes"] == "**notes**"
    assert all(source.plays for source in app.preview_sources.values())
    assert not any(source.plays for source in app.sources.values())
    sources = list(app.preview_sources.values())
    app.set_info_visible(False)
    assert all(source.closed for source in sources) and not app.preview_sources


def test_info_and_s_snapshot_retains_degradation_and_elapsed():
    app = make_app()
    app.errors.append("restore nieznany wynik")
    state = app.tick(app.started_at + 0.5)
    assert state["elapsed"] == 0.5
    assert "restore nieznany wynik" in state_text(state)
    app.dispatch({"type": "pause"}, app.started_at + 1)
    assert app.presenter_snapshot(app.started_at + 4)["elapsed"] == 4


def test_live_input_media_order():
    app = make_app(show_info=False)
    observed = []
    poll = app.live.poll
    app.live.poll = lambda now: observed.append("live") or poll(now)
    source = app.sources["base"]
    original = source.poll
    source.poll = lambda *args: observed.append("media") or original(*args)
    app.tick(app.started_at + 0.1, lambda: observed.append("input"))
    assert observed == ["live", "input", "media"]


def test_timer_pause_restart_and_notes_scale_limits():
    app = make_app(show_info=False)
    start = app.started_at
    app.dispatch({"type": "timer_pause"}, start + 3)
    assert app.presenter_snapshot(start + 10)["elapsed"] == 3
    app.dispatch({"type": "timer_restart"}, start + 10)
    assert app.presenter_snapshot(start + 20)["elapsed"] == 0
    assert app.state["presenter_timer"]["paused"]
    app.dispatch({"type": "timer_pause"}, start + 20)
    assert app.presenter_snapshot(start + 25)["elapsed"] == 5
    media_state = app.state["clock"].copy()
    for _ in range(40):
        app.dispatch({"type": "notes_scale", "delta": 2}, start)
    assert app.state["notes_size"] == 48
    for _ in range(40):
        app.dispatch({"type": "notes_scale", "delta": -2}, start)
    assert app.state["notes_size"] == 16
    assert app.state["clock"] == media_state


def test_presenter_columns(monkeypatch):
    from imgui_bundle import imgui, imgui_md

    from manimcue.player.info import render_info

    context = imgui.create_context()
    try:
        io = imgui.get_io()
        io.display_size = (1000, 800)
        io.delta_time = 1 / 60
        io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
        io.set_ini_filename(None)
        sizes, fonts = [], []
        monkeypatch.setattr(imgui_md, "render", lambda text: fonts.append(imgui.get_font_size()))

        def render(commands):
            point = imgui.get_cursor_screen_pos()
            sizes.append((point.x, imgui.get_content_region_avail().x))
            imgui.dummy((100, 100))

        imgui.new_frame()
        imgui.set_next_window_size((900, 700))
        imgui.begin("test")
        state = make_app().presenter_snapshot(0)
        actions = render_info(state, {"render": render, "composition": [{}]})
        imgui.end()
        imgui.render()
        assert actions == [{"type": "thumbnail_range", "indices": [0]}]
        assert len(sizes) == 2 and sizes[0][0] < sizes[1][0]
        assert 1.4 < sizes[0][1] / sizes[1][1] < 1.7
        assert fonts == [round(imgui.get_style().font_size_base * 24 / 16)]
    finally:
        imgui.destroy_context(context)


def test_thumbnails_24_slides_hidden_no_extract(monkeypatch):
    app = make_app(show_info=False)
    slides = app.manifest["presentations"][0]["slides"]
    slides *= 24
    app.dispatch({"type": "thumbnail_range", "indices": [8, 9, 10, 11]}, app.started_at)
    observed = []
    monkeypatch.setattr(app.thumbnails, "poll_thumbnails", lambda now, **kw: observed.append(kw))
    app.tick(app.started_at + 1)
    assert not app.thumbnails.requests and not observed[-1]["allow_start"]
    app.set_info_visible(True)
    app.tick(app.started_at + 2)
    assert [key for key, _ in app.thumbnails.requests] == [(0, i) for i in (8, 9, 10, 11)]


def test_stale_thumbnail_retiring_slot_and_cache_limits():
    from manimcue.player.sources_av import Thumbnails

    retired = []
    thumbnails = Thumbnails(lambda value: SimpleNamespace(texture=99), retired.append)
    process = SimpleNamespace(
        exitcode=None, terminate=lambda: None, join=lambda _: None, close=lambda: None
    )
    connection = SimpleNamespace(poll=lambda: False, close=lambda: None)
    thumbnails.configure("old", [((0, 0), {})])
    thumbnails.worker = process, connection, (0, 0), "old", 0
    thumbnails.result = {"width": 256, "height": 144, "rgba": bytes(256 * 144 * 4)}
    thumbnails.configure("new", [((1, 0), {})])
    assert thumbnails.cancelled
    assert thumbnails.poll_thumbnails(1) == []
    assert thumbnails.worker and not thumbnails.cache
    process.exitcode = 0
    thumbnails.poll_thumbnails(1, allow_start=False)
    assert thumbnails.worker is None and not thumbnails.cache
    for index in range(80):
        thumbnails.worker = process, connection, (1, index), "new", 1
        thumbnails.result = {"width": 256, "height": 144, "rgba": bytes(256 * 144 * 4)}
        thumbnails.poll_thumbnails(1, allow_start=False)
        assert thumbnails.working_bytes == 8 * 256 * 144 * 4
        assert thumbnails.bytes + thumbnails.working_bytes <= thumbnails.max_bytes
        assert len(thumbnails.cache) <= 64
    assert retired and thumbnails.get((1, 0)) is None


def test_latex_after_init_inline_display_baseline():
    from pathlib import Path

    import imgui_bundle
    from imgui_bundle import imgui, imgui_md, imgui_microtex

    from manimcue.player.notes_math import clear_cache, render_formula

    fonts = Path(imgui_bundle.__file__).parent / "assets" / "fonts" / "latex"
    imgui_microtex.init(str(fonts / "latinmodern-math.clm1"), str(fonts / "latinmodern-math.otf"))
    context = imgui.create_context()
    markdown = imgui_md.MarkdownOptions()
    markdown.with_latex = True
    md_context = imgui_md.create_context(markdown)
    try:
        assert imgui_md.has_latex()
        for size, dpi in ((16, 1), (24, 2), (48, 1)):
            for style in ("inline", "display"):
                result = render_formula(r"\frac{1}{2}+x^2", size, dpi, style)
                assert result["error"] is None
                assert 0 < result["baseline"] <= result["height"] <= 2048
                assert len(result["rgba"]) == result["width"] * result["height"] * 4
                assert render_formula(r"\frac{1}{2}+x^2", size, dpi, style) is result
        assert render_formula(r"\input{secret}", 24, 1, "inline")["error"]
        assert render_formula("x" * 4097, 24, 1, "inline")["error"]
    finally:
        clear_cache()
        imgui_md.destroy_context(md_context)
        imgui.destroy_context(context)


def test_mathtext_fallback_formula_cache_limits(monkeypatch):
    from manimcue.player import notes_math

    notes_math.clear_cache()
    monkeypatch.setattr(notes_math, "MAX_FORMULAS", 3)
    monkeypatch.setattr(notes_math, "MAX_BYTES", 16000)
    try:
        for index in range(8):
            result = notes_math.render_formula(f"x_{index}", 24, 1, "inline", native=False)
            assert not result["error"] and result["baseline"] > 0
            assert len(notes_math._cache) <= 3 and notes_math._bytes <= 16000
        assert notes_math.render_formula(r"\unknowncommand", 24, 1, "display", native=False)[
            "error"
        ]
        tokens = notes_math.math_tokens(r"`$code$` and \$cash $x$ then $$x^2$$")
        assert [token.group(0) for token in tokens] == ["$x$", "$$x^2$$"]
    finally:
        notes_math.clear_cache()


def test_markdown_arrow_merge(monkeypatch):
    from imgui_bundle import immapp

    from manimcue.player.desktop import run_desktop

    captured = []
    monkeypatch.setattr(immapp, "run", lambda params, add_ons: captured.append(add_ons))
    assert run_desktop(manifest(), {}) == 0
    options = captured[0]
    assert options.with_latex and options.with_markdown_options.with_latex
    assert options.with_markdown_options.font_options.merge_fonts == [
        "fonts/Inconsolata-Medium.ttf"
    ]


def test_mathtext_inline_display_without_window(monkeypatch):
    from imgui_bundle import imgui, imgui_md

    from manimcue.player import notes_math

    notes_math.clear_cache()
    monkeypatch.setattr(imgui_md, "has_latex", lambda: False)
    monkeypatch.setattr(
        notes_math, "upload", lambda value: SimpleNamespace(texture=99, close=lambda: None)
    )
    context = imgui.create_context()
    renderer = notes_math.NotesRenderer()
    md_context = imgui_md.create_context()
    try:
        io = imgui.get_io()
        io.display_size = (800, 600)
        io.delta_time = 1 / 60
        io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
        io.set_ini_filename(None)
        images = []
        original = imgui.image

        def image(texture, size):
            images.append((imgui.get_cursor_pos_y(), size))
            original(texture, size)

        monkeypatch.setattr(imgui, "image", image)
        imgui.new_frame()
        imgui.begin("notes")
        renderer.render("before $x^2$ after\n$$x_1$$", 24, 1)
        imgui.end()
        imgui.render()
        assert len(images) == 2 and images[0][0] < images[1][0]
        assert all(value.get("lease") for value in notes_math._cache.values())
    finally:
        renderer.after_render(closing=True)
        imgui_md.destroy_context(md_context)
        imgui.destroy_context(context)


def test_mathtext_evicted_prepared_uploads_are_closed(monkeypatch):
    from imgui_bundle import imgui, imgui_md

    from manimcue.player import notes_math

    notes_math.clear_cache()
    monkeypatch.setattr(imgui_md, "has_latex", lambda: False)
    monkeypatch.setattr(notes_math, "MAX_BYTES", 16000)
    uploaded, closed = [], []

    def upload(value):
        lease = SimpleNamespace(texture=99, close=lambda: closed.append(id(lease)))
        uploaded.append(lease)
        return lease

    monkeypatch.setattr(notes_math, "upload", upload)
    context = imgui.create_context()
    md_context = imgui_md.create_context()
    renderer = notes_math.NotesRenderer()
    try:
        io = imgui.get_io()
        io.display_size = (800, 600)
        io.delta_time = 1 / 60
        io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
        io.set_ini_filename(None)
        for _ in range(3):
            imgui.new_frame()
            imgui.begin("eviction")
            renderer.render(" ".join(f"$x_{i}$" for i in range(8)), 24, 1)
            imgui.end()
            imgui.render()
            assert len(notes_math._cache) < 8
            # Zasoby muszą przeżyć draw data, również po eksmisji przed uploadem.
            assert len(closed) < len(uploaded)
            renderer.after_render()
        renderer.after_render(closing=True)
        assert len(uploaded) == 24
        assert sorted(closed) == sorted(id(lease) for lease in uploaded)
    finally:
        renderer.after_render(closing=True)
        imgui_md.destroy_context(md_context)
        imgui.destroy_context(context)


def test_mathtext_real_markdown_documents_fragment_limit(monkeypatch, tmp_path):
    from imgui_bundle import imgui, imgui_md

    from manimcue.player import notes_math

    notes_math.clear_cache()
    monkeypatch.setattr(imgui_md, "has_latex", lambda: False)
    monkeypatch.setattr(
        notes_math, "upload", lambda value: SimpleNamespace(texture=99, close=lambda: None)
    )
    context = imgui.create_context()
    md_context = imgui_md.create_context()
    renderer = notes_math.NotesRenderer()
    try:
        io = imgui.get_io()
        io.display_size = (800, 600)
        io.delta_time = 1 / 60
        io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
        io.set_ini_filename(None)
        imgui.new_frame()
        imgui.set_next_window_size((180, 500))
        imgui.begin("fallback limits")
        log = tmp_path / "fallback.txt"
        imgui.log_to_file(filename=str(log))
        imgui_md.render("**kontrola**")
        for text in (
            "**tekst $x$ dalej**",
            "- element $x$ dalszy tekst",
            "zawijany tekst " * 5 + "$x$ dalszy tekst " * 5,
        ):
            renderer.render(text, 24, 1)
        imgui.log_finish()
        imgui.end()
        imgui.render()
        logged = log.read_text(encoding="utf8")
        # Cały Markdown usuwa znaczniki; fallback przy wzorze zostawia je dosłownie.
        assert "kontrola" in logged and "**kontrola**" not in logged
        assert "**tekst" in logged and "dalej**" in logged, repr(logged)
        assert "element" in logged and logged.count("zawijany") == 5
        assert imgui.get_draw_data().total_vtx_count > 0
    finally:
        renderer.after_render(closing=True)
        imgui_md.destroy_context(md_context)
        imgui.destroy_context(context)
