"""Integracja CE przez prawdziwy spawn, TCP i SHM; bez okna."""

import json
import time
from pathlib import Path

import numpy as np
import pytest
import test_live_session as session_fixtures
from test_live_corpus import is_ready, names, pump, pump_for

from manimcue.live_session import LiveSpec, capture_first_frame
from manimcue.slides.config import LiveLayer, PresentationConfig, SlideConfig

session = session_fixtures.session

SCENE = str(Path(__file__).parent / "scenes" / "live_ce.py")
EXTRA = str(Path(__file__).parent / "scenes" / "live_ce_extra.py")


def start(session, scene, file=SCENE, **kwargs):
    session.start(LiveSpec(file, scene, engine="ce-cairo", **kwargs))
    return pump(session, is_ready, 30)


def cue(session, command):
    session.send(command)
    return pump(session, lambda ev, fr: f"CUE_DONE {command}" in names(ev), 5)


def test_graph_back_named_cue_and_exact_pixels(session):
    _, first = start(session, "GraphPanel", EXTRA)
    session.send("next")
    pump(session, lambda ev, fr: "CUE_DONE change" in names(ev), 5)
    cue(session, "named")
    began = time.monotonic()
    session.send("back")
    _, frames = pump(session, lambda ev, fr: any(f.boundary for f in fr), 3)
    assert 0.5 <= time.monotonic() - began < 0.7
    assert any(not f.boundary for f in frames)
    assert frames[-1].pixels == first[0].pixels
    cue(session, "verify")
    session.send("next")
    pump(session, lambda ev, fr: "CUE_DONE change" in names(ev), 5)
    assert session._snapshot_metrics


@pytest.mark.parametrize("command", ["condition", "dynamic_condition", "frozen"])
def test_wait_matrix(session, command):
    start(session, "WaitMatrix", EXTRA)
    _events, frames = cue(session, command)
    if command == "frozen":
        interior = [f for f in frames if not f.boundary]
        assert len(interior) == 1
        assert interior[0].pixel(480, 270)[:3] == (255, 0, 0)
    assert session.error is None


@pytest.mark.parametrize("command,text", [("invalid", "static Wait"), ("skip", "skip_animations")])
def test_wait_and_skip_rejected(session, command, text):
    start(session, "WaitMatrix", EXTRA)
    session.send(command)
    _events, _ = pump(session, lambda ev, fr: session.state == "error", 5)
    assert text in session.error


def test_d10_time_and_independent_updater(session):
    start(session, "WaitMatrix", EXTRA)
    session.send("next")
    pump_for(session, 0.2)
    session.send("next")
    pump(session, lambda ev, fr: "CUE_DONE interrupt" in names(ev), 2)
    assert session.error is None


def test_shutdown_skips_callable_tail(session):
    start(session, "ShutdownTail", EXTRA)
    session.send("next")
    pump_for(session, 0.1)
    began = time.monotonic()
    session.request_stop()
    pump(session, lambda ev, fr: "STOPPED" in names(ev), 3)
    assert time.monotonic() - began < 1
    assert session.error is None


@pytest.mark.parametrize("scene", ["LiveCEStaticWait", "LiveCEUpdaterWait", "LiveCELoopBoundary"])
def test_unknown_entry_and_view_do_not_interrupt(session, scene):
    start(session, scene)
    session.send("next")
    pump_for(session, 0.1)
    session.send("not-an-entry")
    session.send("view zoom 1")
    events, _ = pump_for(session, 0.2)
    assert not any(e.startswith("CUE_DONE") for e in names(events))
    assert session.error is None


def test_boundary_timeout_ce(session):
    session.start(LiveSpec(SCENE, "LiveCEFirstFrame", engine="ce-cairo"))
    deadline = time.monotonic() + 15
    while session.running and time.monotonic() < deadline:
        session.poll()
        time.sleep(0.002)
    assert "2 s" in session.error
    assert session._shm is None


@pytest.mark.parametrize("width,height", [(960, 540), (480, 270), (538, 648)])
@pytest.mark.parametrize("opacity", [0, 0.5, 1])
def test_alpha_letterbox_qt_and_thumbnail(tmp_path, width, height, opacity):
    from qtpy.QtGui import QColor, QImage, QPainter

    source = tmp_path / "color.py"
    source.write_text(
        "from manimcue.live_scene_ce import LiveSceneCE\n"
        "class Color(LiveSceneCE):\n"
        "    def build_objects(self):\n"
        '        self.camera.background_color = "#2080c0"\n'
        "        self.camera.init_background()\n",
        encoding="utf-8",
    )
    frame = capture_first_frame(
        LiveSpec(str(source), "Color", width, height, 60, opacity, "ce-cairo")
    )
    image = QImage(frame.pixels, width, height, 4 * width, QImage.Format.Format_RGBA8888)
    base = QImage(width, height, QImage.Format.Format_RGBA8888)
    base.fill(QColor(100, 40, 20))
    painter = QPainter(base)
    painter.drawImage(0, 0, image)
    painter.end()
    expected = np.array([32, 128, 192]) * opacity + np.array([100, 40, 20]) * (1 - opacity)
    for x, y in [(0, 0), (width // 2, height // 2), (width - 1, height - 1)]:
        raw = image.pixelColor(x, y)
        assert abs(raw.alpha() - round(255 * opacity)) <= 1
        actual = base.pixelColor(x, y)
        assert np.max(np.abs(np.array(actual.getRgb()[:3]) - expected)) <= 2


def test_engine_format_and_run_identity(tmp_path):
    file = tmp_path / "base.png"
    file.touch()
    live = LiveLayer(
        scene_file=Path(SCENE), scene_name="LiveCEFirstFrame", engine="ce-cairo", session_id="x"
    )
    slide = SlideConfig(file=file, rev_file=file, layers=[live])
    deck = PresentationConfig(slides=[slide, slide.model_copy(deep=True)])
    path = tmp_path / "deck.json"
    deck.to_file(path)
    assert json.loads(path.read_text())["version"] == 4
    assert PresentationConfig.from_file(path).slides[0].layers[0].engine == "ce-cairo"
    for version in (2, 3):
        old = deck.model_dump(mode="json")
        old["version"] = version
        path.write_text(json.dumps(old))
        assert PresentationConfig.from_file(path).slides[0].layers[0].engine == "manimgl"
    deck.slides[1].layers[0].engine = "manimgl"
    with pytest.raises(ValueError, match="niespójna"):
        PresentationConfig.model_validate(deck.model_dump())
    with pytest.raises(ValueError):
        LiveLayer(scene_file=Path(SCENE), scene_name="x", engine="unknown")


def test_no_movie_hash_and_config_after_import(session, tmp_path):
    source = tmp_path / "probe.py"
    source.write_text(
        """import sys
from manim import config
from manimcue.live_scene_ce import LiveSceneCE
import manim.renderer.cairo_renderer as renderer
assert "manimlib" not in sys.modules and "qtpy" not in sys.modules
assert len(sys.argv) == 1
config.format = "mp4"
config.disable_caching = False
config.renderer = "opengl"
def forbidden(*args, **kwargs):
    raise AssertionError("encoder/hash/cache touched")
renderer.get_hash_from_play_call = forbidden
class Probe(LiveSceneCE):
    def build_objects(self):
        assert config.format == "none" and config.disable_caching
        writer = self.renderer.file_writer
        writer.begin_animation = forbidden
        writer.is_already_cached = forbidden
        writer.write_frame = forbidden
    def check(self):
        from manim import Square, RIGHT
        square = Square()
        self.add(square)
        self.play(square.animate.shift(RIGHT), run_time=.05)
        self.wait(.05)
    PRESETS = {"check": check}
""",
        encoding="utf-8",
    )
    for _ in range(2):
        start(session, "Probe", str(source))
        for _ in range(3):
            cue(session, "check")
        session.request_stop()
        pump(session, lambda ev, fr: "STOPPED" in names(ev), 3)
        assert session.error is None
    assert not list(tmp_path.rglob("*.mp4"))


@pytest.mark.parametrize("stage", ["setup", "build_objects", "cue"])
def test_lifecycle_cleanup_once_preserves_error(session, tmp_path, stage):
    source = tmp_path / "lifecycle.py"
    log = tmp_path / "cleanup.txt"
    source.write_text(
        f"""from pathlib import Path
from manimcue.live_scene_ce import LiveSceneCE
log = Path({str(log)!r})
class Broken(LiveSceneCE):
    def setup(self):
        writer = self.renderer.file_writer
        original = writer.finish
        def finish():
            with log.open('a') as stream:
                stream.write('finish\\n')
            original()
        writer.finish = finish
        if {stage!r} == 'setup':
            raise ValueError('primary failure')
    def build_objects(self):
        if {stage!r} == 'build_objects':
            raise ValueError('primary failure')
    def cue(self):
        raise ValueError('primary failure')
    PRESETS = {{'cue': cue}}
    def tear_down(self):
        with log.open('a') as stream:
            stream.write('teardown\\n')
        raise RuntimeError('secondary failure')
""",
        encoding="utf-8",
    )
    session.start(LiveSpec(str(source), "Broken", engine="ce-cairo"))
    if stage == "cue":
        pump(session, is_ready, 15)
        session.send("cue")
    pump(session, lambda ev, fr: "STOPPED" in names(ev), 15)
    assert "primary failure" in session.error
    assert "secondary failure" not in session.error
    assert log.read_text().splitlines() == ["teardown", "finish"]


@pytest.mark.parametrize(
    "body,diagnosis",
    [
        ("class Wrong: pass", "LiveSceneCE"),
        ("class Wrong(LiveSceneCE):\n    def construct(self): pass", "construct"),
    ],
)
def test_wrong_class_and_construct_diagnosis(session, tmp_path, body, diagnosis):
    source = tmp_path / "wrong.py"
    source.write_text("from manimcue.live_scene_ce import LiveSceneCE\n" + body, encoding="utf-8")
    session.start(LiveSpec(str(source), "Wrong", engine="ce-cairo"))
    events, _ = pump(session, lambda ev, fr: "STOPPED" in names(ev), 15)
    assert diagnosis in session.error
    assert "READY" not in names(events)


def test_shutdown_during_blocking_import(session, tmp_path):
    source = tmp_path / "blocked.py"
    source.write_text("import time\ntime.sleep(20)", encoding="utf-8")
    session.start(LiveSpec(str(source), "Blocked", engine="ce-cairo"))
    pump_for(session, 0.2)
    began = time.monotonic()
    session.request_stop()
    pump(session, lambda ev, fr: "STOPPED" in names(ev), 3)
    assert time.monotonic() - began < 2.8
    assert session._shm is None


def test_wait_interrupt_finishes_remaining_plays(session):
    start(session, "WaitMatrix", EXTRA)
    session.send("interrupted_wait")
    pump_for(session, 0.2)
    began = time.monotonic()
    session.send("next")
    pump(session, lambda ev, fr: "CUE_DONE interrupted_wait" in names(ev), 1)
    assert time.monotonic() - began < 1
    assert session.error is None


def test_twenty_restarts_and_stop_during_build(session):
    old_names = set()
    for _ in range(20):
        start(session, "LiveCEFirstFrame", width=64, height=36)
        assert session._shm.name not in old_names
        old_names.add(session._shm.name)
        session.request_stop()
        pump(session, lambda ev, fr: "STOPPED" in names(ev), 3)
        assert session._shm is None
    session.start(LiveSpec(EXTRA, "SlowImport", engine="ce-cairo"))
    pump(session, lambda ev, fr: session._socket is not None, 15)
    began = time.monotonic()
    session.request_stop()
    pump(session, lambda ev, fr: "STOPPED" in names(ev), 3)
    assert 1.9 <= time.monotonic() - began < 2.8


def test_tcp_utf8_split_multi_reconnect_and_boundary(session):
    import socket

    start(session, "GraphPanel", EXTRA)
    pump_for(session, 0.05)
    payload = "zażółć\n".encode()
    session._socket.sendall(payload[:4])
    pump_for(session, 0.03)
    session._socket.sendall(payload[4:])
    pump(session, lambda ev, fr: "CUE_DONE zażółć" in names(ev), 3)
    address = session._socket.getpeername()
    session._socket.close()
    session._socket = socket.create_connection(address)
    session._socket.setblocking(False)
    session._socket.sendall(b"next\nback\n")
    events = []
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        events += session.poll()
        if "CUE_DONE change" in events:
            break
        time.sleep(0.002)
    assert "CUE_DONE change" in events
    # Bez potwierdzenia granicy back nie może nadpisać obrazu.
    frame = session.try_read_frame()
    assert frame.boundary
    _, frames = pump(session, lambda ev, fr: any(f.boundary for f in fr), 3)
    assert frames[-1].frame_id > frame.frame_id


@pytest.mark.parametrize("width,height", [(960, 540), (480, 270), (538, 648)])
def test_circle_and_asymmetric_letterbox_coordinates(width, height):
    frame = capture_first_frame(LiveSpec(EXTRA, "CirclePanel", width, height, engine="ce-cairo"))
    pixels = np.frombuffer(frame.pixels, np.uint8).reshape(height, width, 4)
    y, x = np.where((pixels[:, :, :3] > 240).all(axis=2))
    assert abs((x.max() - x.min()) - (y.max() - y.min())) <= 2
    if (width, height) == (538, 648):
        assert not pixels[:172, :, :3].any()
        assert not pixels[475:, :, :3].any()
        edge = capture_first_frame(
            LiveSpec(EXTRA, "LetterboxEdges", width, height, engine="ce-cairo")
        )
        assert edge.pixel(269, 171) == (0, 0, 0, 255)
        assert edge.pixel(269, 172) == (255, 0, 0, 255)
        assert edge.pixel(269, 474) == (255, 0, 0, 255)
        assert edge.pixel(269, 475) == (0, 0, 0, 255)
    corners = capture_first_frame(
        LiveSpec(SCENE, "LiveCECorners", width, height, engine="ce-cairo")
    )
    scale = min(width / (128 / 9), height / 8)
    rw, rh = round(128 / 9 * scale), round(8 * scale)
    x0, y0 = (width - rw) // 2, (height - rh) // 2
    for sx, sy, rgb in [
        (-1, 1, (255, 0, 0)),
        (1, 1, (0, 255, 0)),
        (-1, -1, (0, 0, 255)),
        (1, -1, (255, 255, 255)),
    ]:
        px = round(x0 + rw / 2 + sx * (128 / 18 - 1) * scale)
        py = round(y0 + rh / 2 - sy * 3 * scale)
        assert max(abs(a - b) for a, b in zip(corners.pixel(px, py)[:3], rgb)) <= 2


def test_live_clock_skips_deadlines_without_dt_drift(monkeypatch):
    from types import SimpleNamespace

    import manimcue.live_transport as transport

    now = [10.0]
    monkeypatch.setattr(transport.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        transport.time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay + 0.027)
    )
    scene = SimpleNamespace(
        camera=SimpleNamespace(frame_rate=60),
        abort_cue=False,
        live_commands=[],
        live_loop=False,
        live_poll=lambda timeout: None,
    )
    ticks = list(transport.LiveTransport.live_times(scene, 1))
    assert ticks[-1][0] == 1
    assert sum(dt for _, dt in ticks) == pytest.approx(1)
    assert len(ticks) < 40


def test_thumbnail_cache_engine_fps_opacity_and_pixels(tmp_path):
    from types import SimpleNamespace

    from PIL import Image

    from manimcue.slides.slide.base import BaseSlide

    owner = SimpleNamespace(_resolution=(160, 180))
    layer = LiveLayer(
        scene_file=Path(SCENE),
        scene_name="LiveCEFirstFrame",
        engine="ce-cairo",
        background_opacity=0,
    )
    first = BaseSlide._live_thumbnail(owner, layer, tmp_path, True)
    assert Image.open(first).getpixel((0, 0))[3] == 0
    assert BaseSlide._live_thumbnail(owner, layer, tmp_path, True) == first
    layer.fps = 30
    assert BaseSlide._live_thumbnail(owner, layer, tmp_path, True) != first
    layer.background_opacity = 1
    opaque = BaseSlide._live_thumbnail(owner, layer, tmp_path, True)
    assert Image.open(opaque).getpixel((0, 0))[3] == 255
    layer.background_opacity = 0.5
    partial = BaseSlide._live_thumbnail(owner, layer, tmp_path, True)
    from qtpy.QtGui import QColor, QImage, QPainter

    thumbnail = QImage(str(partial))
    assert abs(thumbnail.pixelColor(0, 0).alpha() - 128) <= 1
    base = QImage(thumbnail.size(), QImage.Format.Format_RGBA8888)
    base.fill(QColor(100, 40, 20))
    painter = QPainter(base)
    painter.drawImage(0, 0, thumbnail)
    painter.end()
    assert max(abs(a - b) for a, b in zip(base.pixelColor(0, 0).getRgb()[:3], (50, 20, 10))) <= 2


@pytest.mark.parametrize(
    "engine,file",
    [
        ("ce-cairo", "live_three_ce.py"),
        ("manimgl", "live_three.py"),
    ],
)
def test_both_engines_named_cue_does_not_shadow_sequence_history(session, engine, file):
    source = Path(__file__).parents[1] / "examples" / file
    session.start(LiveSpec(str(source), "ThreePanel", 320, 180, engine=engine))
    _, first = pump(session, is_ready, 15)
    session.send("next")
    pump(session, lambda ev, fr: "CUE_DONE flip" in names(ev), 4)
    cue(session, "flip")
    session.send("back")
    _, frames = pump(session, lambda ev, fr: any(f.boundary for f in fr), 3)
    assert frames[-1].pixels == first[0].pixels
    session.send("view zoom 1")
    session.send("next")
    pump(session, lambda ev, fr: "CUE_DONE flip" in names(ev), 4)
    session.send("next")
    pump(session, lambda ev, fr: "SEQUENCE_END" in names(ev), 2)
    if engine == "ce-cairo":
        session.send("view pan 1 1")
        _, frames = pump_for(session, 0.1)
        assert not frames


def test_snapshot_history_limit_and_transform_child_alignment():
    from manim import Square, Transform, VGroup, tempconfig

    from manimcue.live_scene_ce import LiveSceneCE, SceneSnapshot

    with tempconfig({"renderer": "cairo", "format": "none", "disable_caching": True}):
        scene = LiveSceneCE()
        child = Square()
        root = VGroup(child)
        other = VGroup(child)
        scene.add(root, other)
        before = SceneSnapshot(scene)
        transform = Transform(root, VGroup(Square(), Square(), Square()))
        transform.begin()
        transform.finish()
        assert len(root) == 3
        before.restore(scene)
        assert len(root) == 1 and root[0] is other[0] is child
        for _ in range(55):
            scene.save_state()
        assert len(scene.undo_stack) == len(scene.snapshot_metrics) == 50
