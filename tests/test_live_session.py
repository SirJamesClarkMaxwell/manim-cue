"""Nadzór procesu, bootstrap launchera, transport i awarie sesji live."""

import os
import subprocess
import sys
import time
from itertools import pairwise
from pathlib import Path

import pytest
from test_live_corpus import SCENE_FILE, is_ready, names, pump, pump_for

from manimcue.live_session import LiveSession, LiveSpec


@pytest.fixture
def session():
    instance = LiveSession()
    yield instance
    instance.request_stop()
    deadline = time.monotonic() + 5
    while instance._process is not None and time.monotonic() < deadline:
        instance.poll()
        time.sleep(0.002)
    assert instance._process is None


def start(session, scene):
    session.start(LiveSpec(SCENE_FILE, scene))
    return pump(session, is_ready, 30)


@pytest.mark.gpu
def test_unknown_command_does_not_interrupt(session):
    start(session, "LiveGLMoveFiveSeconds")
    session.send("next")
    pump_for(session, 0.2)
    session.send("unknown-command")
    events, frames = pump_for(session, 0.5)
    assert "CUE_DONE move" not in names(events)
    assert any(not f.boundary for f in frames)
    assert session.state == "ready"


@pytest.mark.gpu
@pytest.mark.parametrize(
    "scene",
    [
        "LiveGLUpdaterWait",
        "LiveGLStaticWait",
        "LiveGLLoopBoundary",
        "LiveGLMoveFiveSeconds",
        "LiveGLFirstFrame",
    ],
)
def test_wait_and_loop_shutdown(session, scene):
    start(session, scene)
    if scene != "LiveGLFirstFrame":
        session.send("next")
        pump(session, lambda ev, fr: any(n.startswith("CUE_START") for n in names(ev)), 5)
    began = time.monotonic()
    session.request_stop()
    pump(session, lambda ev, fr: "STOPPED" in names(ev), 3)
    assert session.state == "stopped"
    assert time.monotonic() - began < 1


@pytest.mark.gpu
def test_stop_during_build(session):
    session.start(LiveSpec(SCENE_FILE, "LiveGLSlowBuild"))
    # Endpoint jest ogłaszany przed build_objects, a READY dopiero po nim.
    pump(session, lambda ev, fr: session._socket is not None, 30)
    began = time.monotonic()
    session.request_stop()
    pump(session, lambda ev, fr: "STOPPED" in names(ev), 3)
    assert 1.9 <= time.monotonic() - began < 2.8
    assert session._shm is None


@pytest.mark.gpu
def test_restart_uses_fresh_resources(session):
    _, frames = start(session, "LiveGLFirstFrame")
    original_shm = session._shm.name
    original_lock = session._frame_lock
    pixels = frames[-1].pixels
    session._process.kill()
    pump(session, lambda ev, fr: "STOPPED" in names(ev), 5)
    assert session.state == "error"
    assert frames[-1].pixels == pixels
    start(session, "LiveGLCorners")
    assert session._shm.name != original_shm
    assert session._frame_lock is not original_lock
    assert session.state == "ready"


@pytest.mark.gpu
def test_boundary_timeout(session):
    session.start(LiveSpec(SCENE_FILE, "LiveGLFirstFrame"))
    deadline = time.monotonic() + 30
    events = []
    # Celowo bez try_read_frame(): odbiornik nie potwierdza pierwszej klatki.
    while session._process is not None and time.monotonic() < deadline:
        events += session.poll()
        time.sleep(0.002)
    assert any(e.startswith("ERROR") and "2 s" in e for e in events)
    assert session.state == "error"
    assert session._shm is None


@pytest.mark.gpu
def test_boundary_is_preserved_before_queued_cue(session):
    start(session, "LiveGLInterruptTwoPlays")
    session.send("next")
    pump_for(session, 0.1)
    session.send("two_step")
    # Odbieramy status bez obrazu; kolejne cue musi czekać na kopię granicy.
    events = []
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        events += session.poll()
        if "CUE_DONE two_step" in events:
            break
        time.sleep(0.002)
    assert "CUE_DONE two_step" in events
    pump_events = []
    for _ in range(20):
        pump_events += session.poll()
        time.sleep(0.002)
    assert "CUE_START two_step" not in pump_events
    final = session.try_read_frame()
    assert final.boundary
    pump(session, lambda ev, fr: "CUE_START two_step" in names(ev), 5)


@pytest.mark.gpu
def test_backend_import_uses_clean_argv_and_no_movie_output(session, tmp_path, monkeypatch):
    source = tmp_path / "scene.py"
    source.write_text(
        """
import sys
from manimcue.live_scene import LiveScene
assert len(sys.argv) == 1, sys.argv
class Probe(LiveScene):
    default_file_writer_config = {
        "write_to_movie": True, "save_last_frame": True, "subdivide_output": True,
        "ffmpeg_bin": "F2_FFMPEG_MUST_NOT_START",
    }
    def build_objects(self):
        writer = self.file_writer
        assert not writer.write_to_movie
        assert not writer.save_last_frame
        assert not writer.subdivide_output
        assert writer.writing_process is None
    def cue_check(self):
        self.wait(0.05)
        assert self.file_writer.writing_process is None
    PRESETS = {"check": cue_check}
    SEQUENCE = ["check"]
    LOOPS = set()
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["player", "--player-only-option", "garbage"])
    session.start(LiveSpec(str(source), "Probe", 64, 36))
    pump(session, is_ready, 30)
    session.send("next")
    pump(session, lambda ev, fr: "CUE_DONE check" in names(ev), 5)
    session.request_stop()
    pump(session, lambda ev, fr: "STOPPED" in names(ev), 5)
    assert session.error is None
    assert not list(tmp_path.rglob("*.mp4"))
    assert not list(tmp_path.rglob("*.png"))


@pytest.mark.gpu
@pytest.mark.parametrize("module", [False, True], ids=["console_entrypoint", "python_m"])
def test_spawn_from_console_entrypoint(tmp_path, module):
    # F2: CLI nie ma jeszcze live; testowy plugin dodaje komendę bez zmiany forka.
    # Rzeczywisty launcher zachowuje własny __main__.__spec__ podczas spawn.
    (tmp_path / "sitecustomize.py").write_text(
        """
import click
original = click.Group.__init__
def install(self, *args, **kwargs):
    original(self, *args, **kwargs)
    @click.command("f2-probe")
    def probe():
        from f2_probe import run
        run()
    self.add_command(probe)
click.Group.__init__ = install
""",
        encoding="utf-8",
    )
    (tmp_path / "f2_probe.py").write_text(
        f"""
import time
from manimcue.live_session import LiveSpec, LiveSession
def run():
    session = LiveSession()
    session.start(LiveSpec({SCENE_FILE!r}, "LiveGLFirstFrame", 64, 36))
    ready = False
    deadline = time.monotonic() + 30
    try:
        while not ready and time.monotonic() < deadline:
            ready = "READY" in session.poll()
            frame = session.try_read_frame()
            if frame is not None:
                assert len(frame.pixels) == 64 * 36 * 4
            assert session.error is None, session.error
            time.sleep(0.002)
        assert ready
        print("F2_SPAWN_OK", flush=True)
    finally:
        session.request_stop()
        stopped = False
        while not stopped and time.monotonic() < deadline + 5:
            stopped = "STOPPED" in session.poll() or session.state == "stopped"
            time.sleep(0.002)
        assert stopped
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)
    command = (
        [sys.executable, "-m", "manimcue.slides"]
        if module
        else [str(Path(sys.executable).parent / "manim-cue.exe")]
    )
    result = subprocess.run(
        [*command, "f2-probe"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("F2_SPAWN_OK") == 1


def test_clock_skips_missed_deadlines(monkeypatch):
    from types import SimpleNamespace

    import manimcue.live_scene as backend
    from manimcue.live_scene import LiveScene

    clock = [0.0]
    monkeypatch.setattr(backend.time, "monotonic", lambda: clock[0])
    # Tempo trzyma `sleep`, nie timeout `select` — fałszywy zegar musi iść razem z nim.
    monkeypatch.setattr(
        backend.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds)
    )
    scene = SimpleNamespace(
        camera=SimpleNamespace(fps=60), abort_cue=False, live_commands=[], live_loop=False
    )
    scene.live_poll = lambda timeout: None
    samples = []
    for elapsed, dt in LiveScene.live_times(scene, 0.5):
        samples.append((elapsed, dt))
        clock[0] += 0.2  # przeciążony render: żadnej serii spóźnionych klatek
    assert len(samples) == 4
    assert samples[-1][0] == 0.5
    assert sum(dt for _, dt in samples) == 0.5
    assert all(b[0] > a[0] for a, b in pairwise(samples))


def test_wait_stop_condition_without_rendering():
    from types import SimpleNamespace

    from manimcue.live_scene import LiveScene

    elapsed = []
    calls = []
    scene = SimpleNamespace(
        live_buffer=True,
        abort_cue=False,
        default_wait_time=1,
        pre_play=lambda: calls.append("pre"),
        post_play=lambda: calls.append("post"),
        should_update_mobjects=lambda: True,
        live_publish=lambda dt: elapsed.append(dt),
        live_times=lambda duration: iter((i / 4, 0.25) for i in range(1, 9)),
    )
    LiveScene.wait(scene, 2, stop_condition=lambda: sum(elapsed) >= 0.5)
    assert sum(elapsed) == 0.5
    assert calls == ["pre", "post"]


def test_stop_during_import(session, tmp_path):
    source = tmp_path / "slow_import.py"
    source.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    session.start(LiveSpec(str(source), "NeverBuilt", 64, 36))
    began = time.monotonic()
    session.request_stop()
    pump(session, lambda ev, fr: "STOPPED" in names(ev), 3)
    assert 1.9 <= time.monotonic() - began < 2.8
    assert session._shm is None


def test_invalid_spec_does_not_allocate(session):
    with pytest.raises(ValueError):
        session.start(LiveSpec("relative.py", "Scene"))
    assert session._shm is None
    assert session._process is None


@pytest.mark.gpu
@pytest.mark.parametrize("scene, cue", [("LiveGLBuildRaises", False), ("LiveGLCueRaises", True)])
def test_build_and_cue_errors(session, scene, cue):
    if cue:
        start(session, scene)
        session.send("next")
    else:
        session.start(LiveSpec(SCENE_FILE, scene))
    pump(session, lambda ev, fr: any(n.startswith("ERROR") for n in names(ev)), 30)
    if session._process is not None:
        pump(session, lambda ev, fr: "STOPPED" in names(ev), 5)
    assert scene in session.error
    assert ("boom" if cue else "build_objects") in session.error
    assert session._shm is None
    assert session.state == "error"


@pytest.mark.gpu
def test_qt_receiver_uses_public_session_api(qtbot):
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "examples" / "live_receiver.py"
    module_spec = importlib.util.spec_from_file_location("f2_receiver", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    widget = module.Receiver(LiveSpec(SCENE_FILE, "LiveGLFirstFrame", 160, 90))
    qtbot.addWidget(widget)
    widget.show()
    try:
        qtbot.waitUntil(lambda: widget.session.state == "ready", timeout=30000)
        assert widget.pixmap() is not None and not widget.pixmap().isNull()
        assert widget.pixmap().size().width() == 160
    finally:
        widget.close()
        qtbot.waitUntil(lambda: widget.stopped, timeout=5000)
    assert not widget.isVisible()


@pytest.mark.gpu
def test_static_wait_does_not_publish_interior_frames(session):
    start(session, "LiveGLStaticWait")
    session.send("next")
    pump(session, lambda ev, fr: "CUE_START pause" in names(ev), 5)
    events, frames = pump_for(session, 0.3)
    assert not frames
    assert "CUE_DONE pause" not in names(events)
    events, frames = pump(session, lambda ev, fr: "CUE_DONE pause" in names(ev), 5)
    assert len(frames) == 1 and frames[0].boundary


def test_worker_error_takes_precedence_over_transport_error():
    session = LiveSession()
    session._event("ERROR transport: reset")
    session._event("ERROR Scene / cue: RuntimeError: boom")
    session._event("ERROR transport: closed")
    assert session.error == "Scene / cue: RuntimeError: boom"
    assert session.state == "error"


def test_final_worker_diagnosis_is_drained_after_exit():
    from types import SimpleNamespace

    class LatePipe:
        def __init__(self):
            self.polls = 0
            self.received = False

        def poll(self, timeout):
            self.polls += 1
            return self.polls > 1

        def recv(self):
            if self.received:
                raise EOFError
            self.received = True
            return "ERROR Scene / build_objects: RuntimeError: boom"

        def close(self):
            pass

    session = LiveSession()
    session._pipe = LatePipe()
    session._process = SimpleNamespace(exitcode=0, join=lambda timeout: None, close=lambda: None)
    events = session.poll()
    assert events == ["ERROR Scene / build_objects: RuntimeError: boom", "STOPPED"]
    assert session.error == "Scene / build_objects: RuntimeError: boom"
    assert session._process is None
