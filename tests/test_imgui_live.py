"""Protokół live ImGui: obraz, trwały zasób, ACK, dopiero wspólny start."""

from types import SimpleNamespace

from manimcue.player.live import LiveController


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
