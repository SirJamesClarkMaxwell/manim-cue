"""Historia checkpointów zachowuje tożsamość sesji i chroni stare wejścia."""

from types import SimpleNamespace

from test_imgui_live import Session, boundary, entry

from manimcue.player.live import LiveController


def test_history_replay_reverse_and_stale_generation():
    controller = LiveController(Session)
    controller.enter(entry())
    session = controller.sessions[0]
    controller.files_ready = True
    event = boundary(controller, session)
    lease = SimpleNamespace(closed=False)
    controller.accept_frame(event, lease)
    history = controller.histories[session]
    first_checkpoint = history.stack[-1].checkpoint
    controller.enter(entry((0, 1), "next", 2))
    controller.files_ready = True
    event = boundary(controller, session, 3)
    controller.accept_frame(event, lease)
    assert len(history.stack) == 2
    controller.enter(entry((0, 0), "previous", 3))
    assert history.expected[1] != first_checkpoint
    assert len(history.stack) == 1
    old = dict(event)
    controller.accept_frame(old, SimpleNamespace(closed=False))
    assert controller.leases[session] is lease
    controller.enter(entry((0, 0), "replay", 4))
    assert history.expected[1] == first_checkpoint


def test_closed_lease_never_acknowledged():
    controller = LiveController(Session)
    controller.enter(entry())
    session = controller.sessions[0]
    controller.files_ready = True
    event = boundary(controller, session)
    controller.accept_frame(event, SimpleNamespace(closed=True))
    assert not controller.ready
    assert not any(command.startswith("frame_seen") for command in session.commands)


import time
from pathlib import Path

import pytest


@pytest.mark.gpu
@pytest.mark.parametrize(
    "engine,filename", [("manimgl", "checkpoint_gl.py"), ("ce-cairo", "checkpoint_ce.py")]
)
def test_real_checkpoint_first_image_and_ack(engine, filename):
    controller = LiveController()
    item = entry()
    item["now"] = time.monotonic()
    layer = item["slide"]["layers"][0]
    layer.update(engine=engine, scene_file=str(Path(__file__).parent / "scenes" / filename))
    controller.enter(item)
    controller.files_ready = True
    deadline = time.monotonic() + 10
    try:
        while time.monotonic() < deadline and not controller.ready:
            for event in controller.poll(time.monotonic()):
                if event["type"] == "frame":
                    controller.accept_frame(event, SimpleNamespace(closed=False, texture=1))
            time.sleep(0.005)
        assert controller.ready and not controller.failed, controller.failed
        session = controller.sessions[0]
        assert session in controller.leases
        assert not controller.histories[session].waiting
    finally:
        controller.begin_shutdown()
        deadline = time.monotonic() + 5
        while not controller.closed and time.monotonic() < deadline:
            controller.poll(time.monotonic())
            time.sleep(0.005)
        assert controller.closed


@pytest.mark.gpu
@pytest.mark.parametrize(
    "engine,filename", [("manimgl", "checkpoint_gl.py"), ("ce-cairo", "checkpoint_ce.py")]
)
def test_real_previous_replay_and_manual_boundary_pixels(engine, filename):
    controller = LiveController()
    item = entry()
    layer = item["slide"]["layers"][0]
    layer.update(engine=engine, scene_file=str(Path(__file__).parent / "scenes" / filename))

    def enter_target(index, reason, identifier):
        target = {
            **item,
            "index": [0, index],
            "entry_id": identifier,
            "reason": reason,
            "now": time.monotonic(),
        }
        controller.enter(target)
        controller.files_ready = True

    def pump(predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in controller.poll(time.monotonic()):
                if event["type"] == "frame":
                    controller.accept_frame(event, SimpleNamespace(closed=False))
            assert not controller.failed, controller.failed
            if predicate():
                return
            time.sleep(0.005)
        raise AssertionError("Timeout procesu live")

    try:
        enter_target(0, "initial", 1)
        pump(lambda: controller.ready)
        session = controller.sessions[0]
        history = controller.histories[session]
        controller.start_entries(time.monotonic())
        pump(lambda: not history.reserved)
        before = controller.frames[session].frame_id
        session.send("paint")
        pump(
            lambda: (
                controller.frames[session].frame_id > before and controller.frames[session].boundary
            )
        )
        left = controller.frames[session].pixels
        enter_target(1, "next", 2)
        pump(lambda: controller.ready)
        controller.start_entries(time.monotonic())
        pump(lambda: history.stack[-1].cue_state == "completed")
        assert controller.frames[session].pixels != left
        enter_target(0, "previous", 3)
        pump(lambda: controller.ready)
        assert controller.frames[session].pixels == left
        controller.start_entries(time.monotonic())
        pump(lambda: not history.reserved)
        enter_target(0, "replay", 4)
        pump(lambda: controller.ready)
        controller.start_entries(time.monotonic())
        pump(lambda: history.stack[-1].cue_state == "completed")
        assert controller.frames[session].pixels != left
    finally:
        controller.begin_shutdown()
        deadline = time.monotonic() + 5
        while not controller.closed and time.monotonic() < deadline:
            controller.poll(time.monotonic())
            time.sleep(0.005)
        assert controller.closed


def test_restore_error_keeps_protected_resource_and_degradation():
    controller = LiveController(Session)
    controller.enter(entry())
    session = controller.sessions[0]
    controller.files_ready = True
    event = boundary(controller, session)
    original = SimpleNamespace(closed=False)
    controller.accept_frame(event, original)
    controller.enter(entry((0, 1), "next", 2))
    controller.files_ready = True
    session.frame = SimpleNamespace(frame_id=3, boundary=False, width=1, height=1, pixels=bytes(4))
    event = next(event for event in controller.poll(1) if event["type"] == "frame")
    controller.accept_frame(event, SimpleNamespace(closed=False))
    assert original in controller.pinned_leases
    history = controller.histories[session]
    request, checkpoint = history.expected
    session.events = [f"CHECKPOINT_ERROR {request} {checkpoint} restore_failed"]
    events = controller.poll(2)
    assert any(event["type"] == "restore_frame" for event in events)
    assert controller.leases[session] is original
    assert "restore_failed" in history.degraded and session.stopping
    assert controller.ready


def test_late_operation_status_finishes_after_uploaded_boundary():
    controller = LiveController(Session)
    controller.enter(entry())
    controller.files_ready = True
    session = controller.sessions[0]
    history = controller.histories[session]
    request, checkpoint = history.expected
    session.events = [f"BOUNDARY {request} 2"]
    session.frame = SimpleNamespace(frame_id=2, boundary=True, width=1, height=1, pixels=bytes(4))
    event = next(event for event in controller.poll(1) if event["type"] == "frame")
    controller.accept_frame(event, SimpleNamespace(closed=False))
    assert not controller.ready
    session.events = [f"CHECKPOINT_READY {request} {checkpoint} 2"]
    controller.poll(2)
    assert controller.ready


def test_navigation_acknowledges_copied_boundary_waiting_for_status():
    controller = LiveController(Session)
    controller.enter(entry())
    session = controller.sessions[0]
    session.frame = SimpleNamespace(frame_id=5, boundary=True)
    assert controller.poll(1) == []
    controller.enter(entry((0, 1), "next", 2))
    assert session.commands[-1] == "frame_seen 5"
