"""Prefetch przez prawdziwe procesy, sockety i SHM; bez okna OpenGL."""

import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from test_live_pool import until

from manimcue.live_pool import LivePool, ProcessBudget
from manimcue.player.prefetch import Prefetch
from manimcue.player.sources_av import close_pool, configure_budget, process_counts


@pytest.fixture
def prefetch():
    pool = LivePool(ProcessBudget(12))
    configure_budget(pool.budget)
    value = Prefetch(pool)
    yield value
    value.cancel("test")
    pool.begin_shutdown()
    close_pool()

    def tick():
        pool.poll(time.monotonic())
        value.poll(time.monotonic())
        process_counts()

    until(lambda: not value.retiring and pool.closed and not process_counts()["retiring"], tick)
    assert not pool.budget.processes
    # Inne moduły nie dziedziczą licznika zakończonego playera.
    import manimcue.player.sources_av as adapter

    adapter._budget = None


def image(tmp_path):
    path = tmp_path / "prefetch.png"
    Image.new("RGBA", (16, 9), "red").save(path)
    return {"kind": "image", "file": str(path), "resolution": [64, 36], "layers": []}


def ready(value):
    return value.items and all(item["ready"] for item in value.items.values())


def test_file_first_frame_held_rebase(prefetch, tmp_path):
    prefetch.prepare((1,), image(tmp_path))
    until(lambda: ready(prefetch), lambda: prefetch.poll(time.monotonic()))
    source = prefetch.items["base"]["source"]
    process = source.process
    frame = source.frame
    for _ in range(3):
        prefetch.poll(time.monotonic() + 8)
        assert source.frame == frame and not source.eof
    taken = prefetch.take((1,), 15)
    assert taken["base"]["source"] is source
    assert source.process is process and source.entry_id == 15 and source.generation == 2
    try:
        until(lambda: source.eof, lambda: source.poll(time.monotonic(), None, 1))
        assert source.frame == frame
    finally:
        source.request_close()
        until(lambda: source.poll_closed(time.monotonic()), lambda: None)


@pytest.mark.parametrize("engine", ["ce-cairo", pytest.param("manimgl", marks=pytest.mark.gpu)])
@pytest.mark.parametrize("persistent", [False, True])
def test_ready_hold_over_5s_then_checkpoint_composition_ack(
    prefetch, tmp_path, monkeypatch, engine, persistent
):
    from manimcue.player.live import LiveController

    slide = image(tmp_path)
    scene = str(
        Path(__file__).parent / "scenes" / ("live_ce.py" if engine == "ce-cairo" else "live_gl.py")
    )
    layer = {
        "kind": "live",
        "scene_file": scene,
        "scene_name": "LiveCEAddRemoveBack" if engine == "ce-cairo" else "LiveGLAddRemoveBack",
        "engine": engine,
        "rect": [0, 0, 1, 1],
    }
    if persistent:
        layer["session_id"] = "panel"
    slide["layers"] = [layer]
    prefetch.prepare((2,), slide)
    until(lambda: ready(prefetch), lambda: prefetch.poll(time.monotonic()))
    session = prefetch.items["0"]["source"]
    statuses = []
    poll = session.poll

    def poll_statuses():
        events = poll()
        statuses.extend(events)
        return events

    monkeypatch.setattr(session, "poll", poll_statuses)
    assert session.checkpoint_metrics == []
    # Techniczny ACK nie tworzy historii ani granicy właściwego wejścia.
    began = time.monotonic()
    until(lambda: time.monotonic() >= began + 5.1, lambda: prefetch.poll(time.monotonic()), 7)
    assert ready(prefetch) and session.state == "ready"
    taken = prefetch.take((2,), 8)
    base = taken.pop("base")["source"]
    controller = LiveController(pool=prefetch.pool)
    entry = {
        "entry_id": 8,
        "index": [0, 1],
        "now": time.monotonic(),
        "requested_playing": False,
        "resolution": [64, 36],
        "reason": "next",
        "slide": slide,
    }
    controller.enter(entry, prefetched=taken)
    controller.files_ready = True
    frames = []

    def tick():
        frames.extend(e for e in controller.poll(time.monotonic()) if e["type"] == "frame")

    try:
        until(lambda: bool(frames), tick)
        assert frames[0]["frame"].frame_id > 1 and frames[0]["frame"].boundary
        assert not controller.ready
        first_frame = frames.pop()
        controller.accept_frame(first_frame, SimpleNamespace(closed=False))
        assert controller.ready
        adoption = controller.adoptions.get(session)
        controller.release_prefetch()
        assert not controller.started_group
        controller.entry["requested_playing"] = True
        controller.start_entries(time.monotonic())
        history = controller.histories.get(session)
        request, checkpoint = history.pending_start if history else ("2", adoption["checkpoint"])
        until(lambda: f"ENTRY_RELEASED {request} {checkpoint}" in statuses, tick)
        assert not history or not history.reserved
        controller.active = 0
        controller.step("next", 8)
        step = controller.steps[session][0]
        until(lambda: "result" in step, tick)
        assert step["result"] == "done" and step["entry_id"] == 8
        until(lambda: any(e["frame"].frame_id == step["frame_id"] for e in frames), tick)
        result_frame = next(e for e in frames if e["frame"].frame_id == step["frame_id"])
        assert result_frame["request_id"] == step["request"]
        assert result_frame["frame"].frame_id > first_frame["frame"].frame_id
        assert result_frame["frame"].pixels != first_frame["frame"].pixels
        controller.accept_frame(result_frame, SimpleNamespace(closed=False))
        assert not controller.steps[session]
    finally:
        controller.begin_shutdown()
        until(lambda: controller.closed, lambda: controller.poll(time.monotonic()))
        base.request_close()
        until(lambda: base.poll_closed(time.monotonic()), lambda: None)


def test_stale_deck_error_timeout_no_retry(prefetch, tmp_path):
    slide = image(tmp_path)
    slide["file"] += ".missing"
    prefetch.prepare((3,), slide)
    until(lambda: prefetch.failed == (3,), lambda: prefetch.poll(time.monotonic()))
    prefetch.prepare((3,), slide)
    assert not prefetch.items
    assert prefetch.take((4,), 1) is None


def test_budget_cancel_waits_exit(prefetch, tmp_path):
    prefetch.pool.budget.configure(1)
    prefetch.prepare((4,), image(tmp_path))
    until(lambda: ready(prefetch), lambda: prefetch.poll(time.monotonic()))
    prefetch.cancel("navigation")
    assert prefetch.bytes and prefetch.retiring
    until(lambda: not prefetch.retiring, lambda: prefetch.poll(time.monotonic()))
    assert prefetch.bytes == 0


@pytest.mark.parametrize("action", ["next", "start_at", "previous"])
def test_app_prefetch_preview_independent_and_navigation(tmp_path, action):
    from manimcue.player.app import App

    slide = image(tmp_path)
    manifest = {
        "version": 1,
        "resolution": [64, 36],
        "presentations": [{"slides": [slide.copy(), slide.copy(), slide.copy()]}],
    }
    leases = []

    def upload(frame):
        lease = SimpleNamespace(texture=len(leases) + 1, closed=False)
        lease.close = lambda: setattr(lease, "closed", True)
        leases.append(lease)
        return lease

    app = App(manifest, {"show_info": True}, uploader=upload)

    def tick():
        app.tick(time.monotonic())
        app.after_render()

    try:
        until(lambda: not app.state["preparing"] and ready(app.prefetch), tick)
        source = app.prefetch.items["base"]["source"]
        preview = app.preview_sources["base"]
        assert source is not preview and source.process.pid != preview.process.pid
        token = app.prefetch.token
        app.dispatch({"type": "start_at", "index": [0, 0]}, time.monotonic())
        assert app.prefetch.token == token
        event = {"type": action}
        if action == "start_at":
            event["index"] = [0, 2]
        app.dispatch(event, time.monotonic())
        if action == "next":
            assert app.sources["base"] is source
            until(lambda: not app.state["preparing"], tick)
            assert app.prefetch.hits == 1
        else:
            assert source in [item["source"] for item in app.prefetch.retiring]
            assert app.prefetch.token is None
    finally:
        app.dispatch({"type": "quit"}, time.monotonic())
        until(lambda: app.closed, tick)
        app.drop_all()
        app.after_render()
        import manimcue.player.sources_av as adapter

        adapter._budget = None


def test_source_wait_poll_delayed_exit_new_entry(prefetch, tmp_path):
    from manimcue.player.sources_av import Source

    prefetch.pool.budget.configure(1)
    first, second = Source(), Source()
    media = image(tmp_path)
    first.prepare(1, media)
    second.prepare(2, media)
    assert second.waiting_slot and second.process is None
    second.prepare(3, media)
    first.request_close()
    second.poll(time.monotonic(), None, 1)
    assert second.process is None
    until(lambda: first.poll_closed(time.monotonic()), lambda: None)
    try:
        until(lambda: second.frame is not None, lambda: second.poll(time.monotonic(), None, 1))
        assert second.entry_id == 3 and second.generation == 2
        assert prefetch.pool.budget.snapshot()["total"] == 1
    finally:
        second.request_close()
        until(lambda: second.poll_closed(time.monotonic()), lambda: None)


@pytest.mark.parametrize("engine", ["ce-cairo", pytest.param("manimgl", marks=pytest.mark.gpu)])
def test_hold_no_zero_dt_updaters(prefetch, tmp_path, engine):
    from manimcue.player.live import LiveController

    marker = tmp_path / "updates.txt"
    scene = tmp_path / "scene.py"
    module, base = (
        ("manimcue.live_scene_ce", "LiveSceneCE")
        if engine == "ce-cairo"
        else ("manimcue.live_scene", "LiveScene")
    )
    scene.write_text(
        f"from {module} import {base}\nfrom pathlib import Path\n"
        f"class Panel({base}):\n"
        "    def build_objects(self):\n        pass\n"
        "    def update_mobjects(self, dt):\n"
        f"        with Path({str(marker)!r}).open('a') as stream:\n            stream.write('x')\n"
        "        super().update_mobjects(dt)\n",
        encoding="utf8",
    )
    slide = image(tmp_path)
    slide["layers"] = [
        {"kind": "live", "scene_file": str(scene), "scene_name": "Panel", "engine": engine}
    ]
    prefetch.prepare((7,), slide)
    until(lambda: ready(prefetch), lambda: prefetch.poll(time.monotonic()))
    before = marker.read_bytes() if marker.exists() else b""
    for _ in range(3):
        prefetch.poll(time.monotonic())
    taken = prefetch.take((7,), 4)
    base_source = taken.pop("base")["source"]
    controller = LiveController(pool=prefetch.pool)
    controller.enter(
        {
            "entry_id": 4,
            "index": [0, 1],
            "now": time.monotonic(),
            "requested_playing": False,
            "resolution": [64, 36],
            "reason": "next",
            "slide": slide,
        },
        prefetched=taken,
    )
    controller.files_ready = True
    frames = []
    try:
        until(
            lambda: frames,
            lambda: frames.extend(
                e for e in controller.poll(time.monotonic()) if e["type"] == "frame"
            ),
        )
        assert (marker.read_bytes() if marker.exists() else b"") == before
        controller.accept_frame(frames[-1], SimpleNamespace(closed=False))
        assert controller.ready
        # Pusta scena bez updaterów nie aktualizuje się w bezczynności (GL i CE); wyjście
        # z hold dowodzi krok w test_ready_hold_over_5s_then_checkpoint_composition_ack.
    finally:
        controller.begin_shutdown()
        until(lambda: controller.closed, lambda: controller.poll(time.monotonic()))
        base_source.request_close()
        until(lambda: base_source.poll_closed(time.monotonic()), lambda: None)


def test_waiting_live_new_entry_cancels_old_request(prefetch):
    from test_imgui_live import entry

    from manimcue.player.live import LiveController

    pool = prefetch.pool
    pool.budget.configure(1)
    worker = pool.take("ce-cairo")
    pool.workers.append(worker)
    controller = LiveController(pool=pool)
    first = entry()
    first["now"] = time.monotonic()
    controller.enter(first)
    old = controller.sessions[0]
    assert old.state == "waiting_slot"
    second = entry((0, 1), "next", 2)
    second["now"] = time.monotonic()
    controller.enter(second)
    assert old is not controller.sessions[0]
    assert not old.running and old.state == "stopped"
    controller.begin_shutdown()
    until(lambda: controller.closed, lambda: controller.poll(time.monotonic()))


def test_adjacent_wins_without_second_scene(tmp_path):
    from manimcue.player.app import App

    slide = image(tmp_path)
    slide["layers"] = [
        {
            "kind": "live",
            "scene_file": str(Path(__file__).parent / "scenes/live_ce.py"),
            "scene_name": "LiveCEFirstFrame",
            "engine": "ce-cairo",
            "session_id": "panel",
        }
    ]
    other = {**slide, "layers": [{**slide["layers"][0], "rect": [0.2, 0.1, 1, 1]}]}
    manifest = {"version": 1, "resolution": [64, 36], "presentations": [{"slides": [slide, other]}]}

    def upload(frame):
        return SimpleNamespace(texture=1, closed=False, close=lambda: None)

    app = App(manifest, {"show_info": False}, uploader=upload)

    def tick():
        app.tick(time.monotonic())
        app.after_render()

    try:
        until(lambda: not app.state["preparing"] and ready(app.prefetch), tick)
        session = app.live.sessions[0]
        history = app.live.histories[session]
        assert len(history.stack) == 1
        assert list(app.prefetch.items) == ["base"]
        app.dispatch({"type": "next"}, time.monotonic())
        until(lambda: not app.state["preparing"], tick)
        assert app.live.sessions[0] is session
        assert len(history.stack) == 2
        assert app.live_pool.hits + app.live_pool.misses == 1
        app.dispatch({"type": "previous"}, time.monotonic())
        until(lambda: not app.state["preparing"], tick)
        assert len(history.stack) == 1 and not history.degraded
    finally:
        app.dispatch({"type": "quit"}, time.monotonic())
        until(lambda: app.closed, tick)
        app.drop_all()
        app.after_render()
        import manimcue.player.sources_av as adapter

        adapter._budget = None


def test_memory_limit_skips_only_layer(prefetch, tmp_path):
    slide = image(tmp_path)
    path = tmp_path / "large.png"
    Image.new("RGBA", (100, 100), "blue").save(path)
    slide["layers"] = [{"kind": "image", "file": str(path)}]
    prefetch.prepare((8,), slide)
    until(
        lambda: set(prefetch.items) == {"base"} and ready(prefetch) and not prefetch.retiring,
        lambda: prefetch.poll(time.monotonic()),
    )
    assert prefetch.failed is None and prefetch.bytes <= prefetch.max_bytes
    source = prefetch.take((8,), 3)["base"]["source"]
    source.request_close()
    until(lambda: source.poll_closed(time.monotonic()), lambda: None)


def test_admission_cancels_one_process_and_does_not_retry_token(monkeypatch):
    from manimcue.player import prefetch as module

    budget = ProcessBudget(2)
    value = Prefetch(LivePool(budget))
    created = []

    class FakeSource:
        role = "prefetch"
        held = True
        waiting_slot = False

        def prepare(self, *args, **kwargs):
            assert budget.try_acquire(self.role)
            self.process = SimpleNamespace(pid=len(created), exitcode=None)
            created.append(self)
            budget.register(self.process, self.role, self.request_close)

        def request_close(self):
            budget.mark_retiring(self.process.pid)

        def poll_closed(self, now):
            budget.release_after_exit(self.process.pid)
            return self.process.exitcode is not None

        def poll(self, *args):
            return {"rgba": b"frame"}

    monkeypatch.setattr(module, "Source", FakeSource)
    slide = {"kind": "image", "resolution": [1, 1], "layers": [{"kind": "image"}]}
    token = (1,)
    value.prepare(token, slide)
    for pid in range(2):
        for _ in range(3):
            assert not budget.try_acquire("preview")
            value.prepare(token, slide)
            value.poll(time.monotonic())
            assert len(created) == 2
            assert budget.retiring == {pid}
        created[pid].process.exitcode = 0
        value.poll(time.monotonic())
        assert budget.try_acquire("preview")
        budget.register(SimpleNamespace(pid=10 + pid, exitcode=None), "preview")
    for _ in range(3):
        value.prepare(token, slide)
        value.poll(time.monotonic())
    assert value.failed == token and not value.items and not value.retiring
    assert len(created) == 2
    budget.processes[10].exitcode = 0
    budget.release_after_exit(10)
    value.prepare((2,), {**slide, "layers": []})
    assert len(created) == 3


def test_decoder_idle_reclaimer_stops_one_and_shutdown_stops_all(monkeypatch):
    from manimcue.player import sources_av as adapter

    budget = ProcessBudget(2)
    workers = []
    for pid in range(2):
        process = SimpleNamespace(pid=pid, exitcode=None)
        workers.append((process, SimpleNamespace(close=lambda: None), None))
        assert budget.try_acquire("idle")
        budget.register(process, "idle")
    monkeypatch.setattr(adapter, "_pool", workers)
    monkeypatch.setattr(adapter, "_retiring_pool", [])
    monkeypatch.setattr(adapter, "_budget", None)
    adapter.configure_budget(budget)
    assert not budget.try_acquire("thumbnail")
    assert len(workers) == 1 and len(budget.retiring) == 1
    assert not budget.try_acquire("scene")
    assert len(workers) == 1
    adapter.close_pool()
    assert not workers and budget.retiring == {0, 1}
