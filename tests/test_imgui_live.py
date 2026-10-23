"""Protokół live ImGui: obraz, trwały zasób, ACK, dopiero wspólny start."""

from types import SimpleNamespace

import pytest
import test_live_scene as transport_fixtures

from manimcue.player.live import LiveController

transport_scene = transport_fixtures.transport_scene


class Session:
    def __init__(self):
        self.state = "ready"
        self.stopping = False
        self.running = True
        self.commands = []
        self.events = []
        self.frame = None

    def start(self, spec):
        self.spec = spec

    def poll(self):
        events, self.events = self.events, []
        if self.stopping:
            self.running = False
        return events

    def send(self, command):
        self.commands.append(command)

    def try_read_frame(self, acknowledge=True):
        assert not acknowledge
        frame, self.frame = self.frame, None
        return frame

    def request_stop(self):
        self.stopping = True


def entry(index=(0, 0), reason="initial", entry_id=1):
    return {
        "entry_id": entry_id,
        "index": list(index),
        "now": 0,
        "requested_playing": True,
        "resolution": [100, 100],
        "reason": reason,
        "slide": {
            "layers": [
                {
                    "kind": "live",
                    "scene_file": __file__,
                    "scene_name": "Panel",
                    "session_id": "panel",
                    "enter_cue": "move",
                }
            ]
        },
    }


def boundary(controller, session, frame_id=2):
    history = controller.histories[session]
    request, checkpoint = history.expected
    session.events += [
        f"BOUNDARY {request} {frame_id}",
        f"CHECKPOINT_READY {request} {checkpoint} {frame_id}",
    ]
    session.frame = SimpleNamespace(
        frame_id=frame_id, boundary=True, width=1, height=1, pixels=bytes(4)
    )
    return controller.poll(1)[0]


def test_ack_after_assign_and_start_after_ready():
    controller = LiveController(Session)
    controller.enter(entry())
    session = controller.sessions[0]
    controller.poll(0)
    assert session.commands == []
    controller.files_ready = True
    controller.poll(0)
    assert session.commands[0].startswith("checkpoint ")
    event = boundary(controller, session)
    assert not any(command.startswith("frame_seen") for command in session.commands)
    assert not controller.ready
    controller.accept_frame(event, SimpleNamespace(texture=7, closed=False))
    assert controller.leases[session].texture == 7
    assert session.commands[-1] == "frame_seen 2" and controller.ready
    controller.start_entries(1)
    assert session.commands[-1].startswith("release ")


def test_pause_prepares_without_enter_and_shutdown():
    controller = LiveController(Session)
    item = entry(reason="next")
    item["requested_playing"] = False
    controller.enter(item)
    session = controller.sessions[0]
    controller.files_ready = True
    event = boundary(controller, session)
    controller.accept_frame(event, SimpleNamespace(closed=False))
    controller.start_entries(1)
    assert not any(command.startswith("enter ") for command in session.commands)
    controller.entry["requested_playing"] = True
    controller.start_entries(2)
    assert session.commands[-1].startswith("enter ")
    controller.begin_shutdown()
    assert not controller.closed
    controller.poll(3)
    assert controller.closed


def test_timeout_degrades_and_does_not_block_files():
    controller = LiveController(Session)
    controller.enter(entry())
    controller.files_ready = True
    events = controller.poll(6)
    assert controller.failed and events[0]["type"] == "error" and controller.ready
    assert controller.sessions[0].stopping


def test_cancelled_boundary_ack_without_composition():
    controller = LiveController(Session)
    controller.enter(entry())
    session = controller.sessions[0]
    history = controller.histories[session]
    old_request = history.expected[0]
    controller.enter(entry((0, 1), "next", 2))
    assert controller.sessions[0] is session
    session.events = [f"BOUNDARY {old_request} 5"]
    session.frame = SimpleNamespace(frame_id=5, boundary=True)
    assert controller.poll(1) == []
    assert session.commands[-1] == "frame_seen 5"
    assert session not in controller.leases


def step_controller(monkeypatch):
    from manimcue.player import live

    monkeypatch.setattr(live.time, "monotonic", lambda: 0)
    controller = LiveController(Session)
    controller.enter(entry())
    session = controller.sessions[0]
    controller.histories.clear()
    controller.active = 0
    controller.started_group = True
    controller.step("next", 1)
    return controller, session


@pytest.mark.parametrize("result,direction", [("start", "previous"), ("end", "next")])
def test_sequence_boundary_ack_before_navigation(monkeypatch, result, direction):
    controller, session = step_controller(monkeypatch)
    session.events = [f"STEP_RESULT 1 {result} 7"]
    session.frame = SimpleNamespace(frame_id=7, boundary=True)
    event = controller.poll(1)[0]
    assert controller.active == 0
    assert "frame_seen 7" not in session.commands
    controller.accept_frame(event, SimpleNamespace(closed=False))
    assert session.commands[-1] == "frame_seen 7"
    events = controller.poll(1)
    assert [e for e in events if e["type"] == "navigate"] == [
        {"type": "navigate", "direction": direction, "entry_id": 1}
    ]
    assert not controller.poll(1)


def test_stale_step_result(monkeypatch):
    controller, session = step_controller(monkeypatch)
    controller.active = None
    session.events = ["STEP_RESULT 1 end 7"]
    assert controller.poll(1) == []
    assert not controller.steps


def test_step_result_waits_for_status_before_ack(monkeypatch):
    controller, session = step_controller(monkeypatch)
    session.frame = SimpleNamespace(frame_id=7, boundary=True)
    assert controller.poll(1) == []
    assert "frame_seen 7" not in session.commands
    session.events = ["STEP_RESULT 1 end 7"]
    event = controller.poll(1)[0]
    controller.accept_frame(event, SimpleNamespace(closed=False))
    assert session.commands[-1] == "frame_seen 7"


def test_busy_reserved_step(monkeypatch):
    controller, session = step_controller(monkeypatch)
    controller.started_group = False
    controller.step("back", 1)
    assert session.commands == ["step 1 next"]


def test_no_log_parsing(monkeypatch):
    controller, session = step_controller(monkeypatch)
    session.events = ["SEQUENCE_END", "Jestes na poczatku sekwencji", "CUE_DONE next"]
    assert controller.poll(1) == []
    assert controller.steps[session][0]["deadline"] == 5


@pytest.mark.parametrize("status", ["running", "looping"])
def test_cue_over_5s_then_stall(monkeypatch, status):
    controller, session = step_controller(monkeypatch)
    for now in range(1, 12):
        session.events = [f"STEP_STATUS 1 {status}"]
        assert not controller.poll(now)
    assert not controller.failed
    controller.poll(16)
    assert controller.failed and session.stopping


def test_interrupt_deadline_despite_heartbeat(monkeypatch):
    controller, session = step_controller(monkeypatch)
    controller.step("back", 1)
    controller.step("next", 1)
    assert session.commands == ["step 1 next", "step 2 back"]
    for now in range(1, 6):
        session.events = ["STEP_STATUS 1 looping", "STEP_STATUS 2 waiting"]
        controller.poll(now)
    assert controller.failed
    assert not any(e["type"] == "navigate" for e in controller.events)


@pytest.fixture
def wired_controller(transport_scene, monkeypatch):
    """Kontroler i EntryHistory połączone z prawdziwym parserem przez TCP."""
    import socket

    from manimcue.live_transport import LineBuffer
    from manimcue.player import live

    scene, peer = transport_scene
    peer.setblocking(False)
    peer.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    scene.client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    now = [10.0]

    def monotonic():
        now[0] += 0.000001
        return now[0]

    monkeypatch.setattr(live.time, "monotonic", monotonic)
    monkeypatch.setattr(live.time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))

    class WiredSession(Session):
        def __init__(self):
            super().__init__()
            self.buffer = LineBuffer()
            self.statuses = []

        def send(self, command):
            super().send(command)
            peer.sendall((command + "\n").encode())

        def poll(self):
            while True:
                try:
                    self.buffer.feed(peer.recv(4096))
                except BlockingIOError:
                    break
            result = []
            while self.buffer.has_line():
                result.append(self.buffer.pop_line())
            self.statuses.extend(result)
            return result

        def try_read_frame(self, acknowledge=True):
            assert not acknowledge
            return scene.live_buffer.try_read()

    controller = LiveController(WiredSession)
    item = entry()
    item["now"] = now[0]
    controller.enter(item)
    session = controller.sessions[0]

    def execute():
        scene.live_barrier()
        scene.live_poll(0.1)
        command = scene.live_commands.popleft()
        if command[0] == "step":
            scene.live_execute_step(*command[1:])
        else:
            scene.live_state_operation(*command)

    def accept():
        events = controller.poll(now[0])
        frames = [event for event in events if event["type"] == "frame"]
        assert not any(event["type"] == "navigate" for event in events)
        assert len(frames) == 1, events
        event = frames[0]
        assert f"frame_seen {event['frame'].frame_id}" not in session.commands
        controller.accept_frame(event, SimpleNamespace(closed=False, texture=7))
        scene.live_barrier()
        assert scene.live_seen == event["frame"].frame_id
        return event

    controller.files_ready = True
    controller.poll(now[0])
    execute()
    accept()
    controller.start_entries(now[0])
    execute()
    controller.poll(now[0])
    assert not controller.histories[session].reserved
    controller.active = 0
    yield controller, session, scene, now, execute, accept


@pytest.mark.parametrize("loop", [False, True])
def test_real_progress_over_5s_and_second_press_during_loop(wired_controller, loop):
    from manimcue.player.input import route

    controller, session, scene, now, execute, accept = wired_controller
    scene.SEQUENCE = ["long"]
    scene.LOOPS = {"long"} if loop else set()
    pressed = []

    def press(direction):
        actions = route({"type": "key", "key": direction, "repeat": False}, {"active_live": 0})
        assert len(actions) == 1 and actions[0]["type"] == "cue"
        controller.step(actions[0]["direction"], controller.entry["entry_id"])
        pressed.append(now[0])

    began = now[0]

    def cue(inner):
        for _, _dt in inner.live_times(0.25 if loop else 7):
            controller.poll(now[0])
            if loop and now[0] - began > 6 and len(pressed) == 1:
                press("left_arrow")
            assert not controller.failed

    scene.PRESETS = {"long": cue}
    press("right_arrow")
    execute()
    accept()
    assert now[0] - began > 5 and not controller.failed
    expected = "looping" if loop else "running"
    assert any(
        line.startswith("STEP_STATUS ") and line.endswith(expected) for line in session.statuses
    )
    if loop:
        assert len(pressed) == 2
        assert any(line.endswith(" waiting") for line in session.statuses)
        execute()
        accept()
        assert scene.cursor == 0
    assert not controller.histories[session].boundaries
    assert not controller.steps[session]


@pytest.mark.parametrize("reason", ["previous", "reverse"])
def test_persistent_and_reverse_boundary_restore_real_path(wired_controller, reason):
    from manimcue.player.controller import reduce
    from manimcue.player.state import initial_state

    controller, session, scene, now, execute, accept = wired_controller
    history = controller.histories[session]
    first = history.stack[-1].checkpoint
    scene.SEQUENCE = ["move"]
    scene.PRESETS = {"move": lambda inner: None}
    controller.step("next", controller.entry["entry_id"])
    execute()
    accept()
    controller.poll(now[0])
    assert scene.cursor == 1 and len(scene.undo_stack) == 1
    target = entry((0, 1), "next", 2)
    target["slide"]["layers"][0].pop("enter_cue")
    target["now"] = now[0]
    controller.enter(target)
    controller.files_ready = True
    controller.poll(now[0])
    execute()
    accept()
    controller.start_entries(now[0])
    execute()
    controller.poll(now[0])
    second = history.stack[-1].checkpoint
    assert len(history.stack) == 2 and first != second
    back = entry((0, 0), reason, 3)
    back["now"] = now[0]
    controller.enter(back)
    controller.files_ready = True
    controller.poll(now[0])
    execute()
    accept()
    assert len(history.stack) == 1 and history.stack[0].checkpoint == first
    assert not history.waiting and not history.degraded
    assert scene.cursor == 1 and len(scene.undo_stack) == 1
    controller.poll(now[0])
    execute()  # Usunięcie checkpointu opuszczonego wejścia poprzedza release.
    controller.start_entries(now[0])
    execute()
    controller.poll(now[0])
    controller.active = 0
    manifest = {
        "resolution": [100, 100],
        "presentations": [{"slides": [{"kind": "image"}, {"kind": "image"}]}],
    }
    state = initial_state(manifest, now[0])
    state.update(
        entry_id=3,
        preparing=False,
        paused=False,
        requested_playing=True,
        reverse=reason == "reverse",
    )
    controller.step("next", 3)
    execute()
    # Sam wynik nie zwalnia fokusu i nie emituje nawigacji przed zasobem/ACK.
    event = accept()
    assert event["request_id"] is not None
    events = controller.poll(now[0])
    navigation = [event for event in events if event["type"] == "navigate"]
    assert len(navigation) == 1 and session.commands[-1].startswith("frame_seen ")
    state, effects = reduce(state, {"type": navigation[0]["direction"]}, now[0])
    assert [effect["type"] for effect in effects] == ["cancel", "prepare"]
    assert state["index"] == ([0, 0] if reason == "reverse" else [0, 1])
    assert not state["reverse"]
    assert not controller.poll(now[0])
    assert not history.boundaries


def test_stale_boundary_metadata_removed(wired_controller):
    controller, session, scene, now, execute, _ = wired_controller
    history = controller.histories[session]
    controller.step("next", controller.entry["entry_id"])
    controller.cancel_steps()
    execute()
    assert controller.poll(now[0]) == []
    scene.live_barrier()
    assert scene.live_seen == scene.live_frame_id
    assert not history.boundaries and not controller.steps


@pytest.mark.parametrize("loop", [False, True])
def test_real_progress_then_stall_has_no_navigation(wired_controller, loop):
    controller, session, scene, now, execute, _ = wired_controller
    scene.SEQUENCE = ["stall"]
    scene.LOOPS = {"stall"} if loop else set()

    def cue(inner):
        for _, _dt in inner.live_times(6):
            controller.poll(now[0])
        assert not controller.failed
        now[0] += 5.1
        events = controller.poll(now[0])
        assert controller.failed and session.stopping
        assert not any(event["type"] == "navigate" for event in events)
        # Koniec pojedynczego powtorzenia, bez kolejnych obrotow testowej petli.
        inner.live_loop = False

    scene.PRESETS = {"stall": cue}
    controller.step("next", controller.entry["entry_id"])
    execute()
    assert any(line.endswith("looping" if loop else "running") for line in session.statuses)
    assert controller.failed
