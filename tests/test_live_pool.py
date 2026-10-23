"""Rzeczywisty spawn puli, późny spec, socket i SHM bez okna GPU."""

import time
from pathlib import Path

import pytest

from manimcue.live_pool import LivePool, ProcessBudget
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
        pool.retire_idle()
        until(lambda worker=worker: worker not in pool.workers, lambda: pool.poll(time.monotonic()))
        assert not pool.failures.get("ce-cairo")
