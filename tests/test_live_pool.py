"""Rzeczywisty spawn puli, późny spec, socket i SHM bez okna GPU."""

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from manimcue.live_pool import LivePool, ProcessBudget, WarmWorker
from manimcue.live_session import LiveSession, LiveSpec


def until(predicate, tick, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        tick()
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("Timeout puli")


@pytest.fixture
def pool():
    value = LivePool(ProcessBudget(8))
    yield value
    value.begin_shutdown()
    until(lambda: value.closed, lambda: value.poll(time.monotonic()))
    assert not value.budget.processes


@pytest.mark.parametrize("engine", ["manimgl", "ce-cairo"])
def test_pool_import_ready_gl_ce(pool, engine):
    pool.configure({engine})
    until(
        lambda: len(pool.workers) == 2 and all(w.ready for w in pool.workers),
        lambda: pool.poll(time.monotonic()),
    )
    assert all(w.engine == engine for w in pool.workers)
    worker = pool.workers[0]
    pool.configure(set())
    until(lambda: not pool.workers, lambda: pool.poll(time.monotonic()))
    assert worker.control.closed


def test_spawn_lock_late_spec_shm(pool):
    pool.configure({"ce-cairo"})
    until(lambda: any(w.ready for w in pool.workers), lambda: pool.poll(time.monotonic()))
    pid = pool.workers[0].process.pid
    session = LiveSession()
    session.start(
        LiveSpec(
            str(Path(__file__).parent / "scenes/live_ce.py"),
            "LiveCEFirstFrame",
            width=64,
            height=36,
            engine="ce-cairo",
        ),
        pool=pool,
    )
    try:
        until(lambda session=session: session.state == "ready", session.poll)
        assert session._process.pid == pid and pool.hits == 1
        until(lambda: session.try_read_frame() is not None, session.poll)
        name = session._shm.name
    finally:
        session.request_stop()
        until(lambda session=session: not session.running, session.poll)
    from multiprocessing.shared_memory import SharedMemory

    with pytest.raises(FileNotFoundError):
        SharedMemory(name=name)
    assert pid not in pool.budget.processes


def test_budget_wait_poll_delayed_exit_new_entry(pool):
    pool.budget.configure(1)
    worker = pool.take("ce-cairo")
    assert worker is not None
    pool.workers.append(worker)
    session = LiveSession()
    spec = LiveSpec(
        str(Path(__file__).parent / "scenes/live_ce.py"),
        "LiveCEFirstFrame",
        width=32,
        height=18,
        engine="ce-cairo",
    )
    session.start(spec, pool=pool)
    assert session.state == "waiting_slot" and session._shm is None
    session.request_stop()
    pool._stop(worker)
    assert not pool.budget.try_acquire("scene")
    until(lambda: not pool.workers, lambda: pool.poll(time.monotonic()))
    assert session.state == "stopped" and not session.running
    session.start(spec, pool=pool)
    try:
        until(lambda session=session: session.state == "ready", session.poll)
    finally:
        session.request_stop()
        until(lambda session=session: not session.running, session.poll)


def orphan_parent(connection):
    """Kończy rodzica bez finalizerów multiprocessing i bez wysłania stop."""
    import os

    pool = LivePool()
    worker = pool.take("ce-cairo")
    connection.send(worker.process.pid)
    until(lambda: worker.bootstrap.poll(0), lambda: None)
    assert worker.bootstrap.recv() == "POOL_READY"
    connection.send("ready")
    connection.close()
    os._exit(0)


def test_pool_parent_death():
    import multiprocessing as mp

    psutil = pytest.importorskip("psutil")
    ctx = mp.get_context("spawn")
    reader, sender = ctx.Pipe(duplex=False)
    parent = ctx.Process(target=orphan_parent, args=(sender,))
    parent.start()
    sender.close()
    try:
        assert reader.poll(15)
        child = psutil.Process(reader.recv())
        assert reader.poll(15) and reader.recv() == "ready"
        child.wait(timeout=1)
        parent.join(1)
        assert parent.exitcode == 0
    finally:
        reader.close()
        if parent.is_alive():
            parent.kill()
            parent.join(1)
        parent.close()


def test_one_scene_per_process(pool):
    pool.configure({"ce-cairo"})
    pids = []
    for _ in range(2):
        until(lambda: any(w.ready for w in pool.workers), lambda: pool.poll(time.monotonic()))
        session = LiveSession()
        session.start(
            LiveSpec(
                str(Path(__file__).parent / "scenes/live_ce.py"),
                "LiveCEFirstFrame",
                width=32,
                height=18,
                engine="ce-cairo",
            ),
            pool=pool,
        )
        try:
            until(lambda session=session: session.state == "ready", session.poll)
            pids.append(session._process.pid)
            assert session.try_read_frame() is not None
        finally:
            session.request_stop()
            until(lambda session=session: not session.running, session.poll)
        assert all(w.process.pid != pids[-1] for w in pool.workers)
    assert len(set(pids)) == 2


def test_cancelled_refill_does_not_disable_engine(pool):
    pool.configure({"ce-cairo"})
    pool.poll(time.monotonic())
    for _ in range(2):
        worker = pool.workers[-1]
        pool._stop(worker)
        until(lambda worker=worker: worker not in pool.workers, lambda: pool.poll(time.monotonic()))
        assert not pool.failures.get("ce-cairo")


def test_refill_yields_to_waiting_scene_after_delayed_exit(monkeypatch):
    budget = ProcessBudget(1)
    pool = LivePool(budget)
    pool.configure({"ce-cairo"})
    connection = SimpleNamespace(close=lambda: None, poll=lambda timeout: False)
    process = SimpleNamespace(pid=1, exitcode=None, join=lambda timeout: None, close=lambda: None)
    worker = WarmWorker(process, connection, connection, None, "ce-cairo", 0)
    pool.workers.append(worker)
    assert budget.try_acquire("idle")
    budget.register(process, "idle", lambda: pool._stop(worker))
    spawned = []

    def spawn(engine, role):
        if budget.try_acquire(role):
            spawned.append(role)
            return object()
        return None

    monkeypatch.setattr(pool, "_spawn", spawn)
    assert not budget.try_acquire("scene")
    for _ in range(3):
        pool.poll(0)
        assert not budget.try_acquire("scene")
    assert budget.retiring == {1} and not spawned
    process.exitcode = 0
    pool.poll(0)
    assert not pool.workers and not spawned
    assert budget.try_acquire("scene")
    budget.abort()
    assert budget.try_acquire("idle")
    budget.abort()


def test_abandoned_wait_stops_blocking_refill(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("manimcue.live_pool.time.monotonic", lambda: clock[0])
    budget = ProcessBudget(0)
    assert not budget.try_acquire("thumbnail")
    budget.limit = 1
    assert not budget.try_acquire("idle")
    clock[0] = 1.0
    assert budget.try_acquire("idle")
    budget.abort()


@pytest.mark.parametrize("role", ["scene", "preview", "prefetch"])
def test_thumbnail_yields_to_fresh_waiter_after_reap(monkeypatch, role):
    clock = [0.0]
    monkeypatch.setattr("manimcue.live_pool.time.monotonic", lambda: clock[0])
    budget = ProcessBudget(1)
    assert budget.try_acquire("thumbnail")
    process = SimpleNamespace(pid=123, exitcode=None)
    budget.register(process, "thumbnail", lambda: budget.mark_retiring(123))
    assert not budget.try_acquire(role)
    process.exitcode = -1
    budget.release_after_exit(123)
    assert not budget.try_acquire("thumbnail")
    assert budget.try_acquire(role)
    budget.abort()
    assert budget.try_acquire("thumbnail")
    budget.abort()
    budget.waiting[role] = 0
    clock[0] = 0.5
    assert budget.try_acquire("thumbnail")
    budget.abort()


@pytest.mark.parametrize("role", ["thumbnail", "prefetch", "preview", "scene"])
def test_budget_reclaims_one_lowest_process_until_exit(role):
    budget = ProcessBudget(5)
    stopped = []
    for pid, category in enumerate(["preview", "prefetch", "thumbnail", "idle", "idle"]):
        assert budget.try_acquire(category)

        def stop(pid=pid):
            stopped.append(pid)
            budget.mark_retiring(pid)

        budget.register(SimpleNamespace(pid=pid, exitcode=None), category, stop)
    for _ in range(3):
        assert not budget.try_acquire(role)
    assert stopped == [3]
    assert budget.snapshot()["total"] == 5
    budget.processes[3].exitcode = 0
    budget.release_after_exit(3)
    assert budget.try_acquire(role)
    assert stopped == [3]


def test_live_idle_reclaimer_stops_one_but_shutdown_stops_all():
    pool = LivePool(ProcessBudget(2))
    for pid in range(2):
        process = SimpleNamespace(pid=pid, exitcode=None)
        connection = SimpleNamespace(close=lambda: None)
        worker = WarmWorker(process, connection, connection, None, "ce-cairo", 0)
        pool.workers.append(worker)
        assert pool.budget.try_acquire("idle")
        pool.budget.register(process, "idle")
    pool.retire_idle()
    assert pool.budget.retiring == {0}
    pool.begin_shutdown()
    assert pool.budget.retiring == {0, 1}


def test_budget_reclaim_order():
    budget = ProcessBudget(4)
    stopped = []
    for pid, role in enumerate(["preview", "prefetch", "thumbnail", "idle"]):
        assert budget.try_acquire(role)

        def stop(pid=pid):
            stopped.append(pid)
            budget.mark_retiring(pid)

        budget.register(SimpleNamespace(pid=pid, exitcode=None), role, stop)
    for pid in [3, 2, 1, 0]:
        assert not budget.try_acquire("scene")
        assert stopped[-1] == pid
        budget.processes[pid].exitcode = 0
        budget.release_after_exit(pid)
        assert budget.try_acquire("scene")
        budget.register(SimpleNamespace(pid=pid + 10, exitcode=None), "scene")
    assert stopped == [3, 2, 1, 0]
