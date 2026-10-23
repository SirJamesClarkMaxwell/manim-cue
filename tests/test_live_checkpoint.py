"""Bramka F5g: graf, updatery i rezerwa bez renderera oraz bez okna."""

import json
import statistics
import time
import tracemalloc
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_persistent_live as persistent
from test_live_layers import pump

from manimcue.live_checkpoint import (
    CheckpointStore,
    PanelSnapshot,
    RestoreFailed,
    UnsupportedSnapshot,
)
from manimcue.live_entry import EntryHistory
from manimcue.live_transport import LineBuffer, LiveTransport

make_player = persistent.make_player
qapp = persistent.qapp


@pytest.fixture(params=["manimgl", "ce-cairo"])
def checkpoint_decks(request, monkeypatch):
    original = persistent.presentation

    def presentation(*args, **kwargs):
        deck = original(*args, **kwargs)
        for slide in deck.slides:
            for layer in slide.layers:
                if layer.kind == "live":
                    layer.engine = request.param
                    layer.scene_file = (
                        Path(__file__).parent
                        / "scenes"
                        / (
                            "checkpoint_ce.py"
                            if request.param == "ce-cairo"
                            else "checkpoint_gl.py"
                        )
                    )
                    layer.scene_name = "Panel"
                    layer.enter_cue = "move"
        return deck

    monkeypatch.setattr(persistent, "presentation", presentation)
    return request.param


def settled(player):
    return not player.clips.preparing and all(
        not history.waiting and not history.reserved for history in player.live.histories.values()
    )


def manual(qapp, player, command):
    session = player.live.sessions[0]
    old = player.live.last_frames[session].frame_id
    session.send(command)
    pump(
        qapp,
        lambda: (
            player.live.last_frames[session].frame_id > old
            and player.live.last_frames[session].boundary
        ),
    )


def entered(qapp, player):
    pump(
        qapp,
        lambda: (
            settled(player)
            and next(iter(player.live.histories.values())).status == "koniec cue move"
        ),
    )


def test_player_previous_reverse_replay_pixels_and_branch(qapp, make_player, checkpoint_decks):
    player = make_player()
    try:
        pump(qapp, lambda: settled(player) and persistent.initialized(player), timeout=8)
    except BaseException:
        print(player.presenter_snapshot())
        print([vars(h) for h in player.live.histories.values()])
        raise
    session = player.live.sessions[0]
    history = player.live.histories[session]
    manual(qapp, player, "next")
    manual(qapp, player, "paint")
    left = player.live.last_frames[session].pixels
    player.load_next_slide()
    entered(qapp, player)
    manual(qapp, player, "next")
    player.previous()
    pump(qapp, lambda: settled(player))
    assert player.live.last_frames[session].pixels == left
    assert len(history.stack) == 1
    for _ in range(2):
        player.replay()
        entered(qapp, player)
        replay = player.live.last_frames[session].pixels
        if _ == 0:
            first_replay = replay
        assert replay == first_replay
    player.load_next_slide()
    entered(qapp, player)
    player.reverse()
    pump(qapp, lambda: settled(player))
    assert player.live.last_frames[session].pixels == first_replay
    assert player.playing_reversed_slide
    before = history.request
    player.load_next_slide(reason="auto_next")
    pump(qapp, lambda: settled(player))
    assert history.request == before
    assert not player.playing_reversed_slide


def test_replay_pause_reserves_keyboard_and_view(qapp, make_player, checkpoint_decks):
    from qtpy.QtCore import Qt
    from test_live_layers import key, recorded_sends

    player = make_player()
    pump(qapp, lambda: settled(player) and persistent.initialized(player))
    player.current_slide_index = 1
    player.current_file = player.current_slide_config.file
    player.load_current_media(start_paused=True, reason="next")
    pump(qapp, lambda: not player.clips.preparing)
    session = player.live.sessions[0]
    history = player.live.histories[session]
    assert history.reserved
    player.live.click(0)
    sent = recorded_sends(session)
    key(player, Qt.Key.Key_Right)
    key(player, Qt.Key.Key_Left)
    player.live.wheel(1)
    assert not sent
    assert "zarezerwowane" in player.state_overlay.text()
    player.play_pause()
    entered(qapp, player)
    assert len([s for s in sent if s.startswith("enter ")]) == 1
    sent.clear()
    key(player, Qt.Key.Key_R)
    key(player, Qt.Key.Key_Right)
    key(player, Qt.Key.Key_Left)
    player.play_pause()
    pump(qapp, lambda: not player.clips.preparing)
    assert history.reserved and not player.clips.running
    assert "next" not in sent and "back" not in sent
    assert not any(s.startswith("enter ") for s in sent)
    player.play_pause()
    entered(qapp, player)
    assert len([s for s in sent if s.startswith("enter ")]) == 1


def test_rapid_twenty_roundtrips_keep_current_boundary(qapp, make_player, checkpoint_decks):
    player = make_player(swapped=True)
    pump(qapp, lambda: settled(player) and persistent.initialized(player))
    session = player.live.sessions[0]
    initial = player.live.last_frames[session].pixels
    for _ in range(20):
        player.load_next_slide()
        player.previous()
        assert "wejście anulowane, cue niewysłane" in player.presenter_snapshot()
        pump(qapp, lambda: settled(player), timeout=10)
        assert player.live.sessions[0] is session
        assert player.live.last_frames[session].pixels == initial
        assert not player.live.histories[session].degraded
    assert session.error is None


def test_ready_without_entry_cue_does_not_claim_waiting_cue(
    qapp, make_player, checkpoint_decks, monkeypatch
):
    original = persistent.presentation

    def presentation(*args, **kwargs):
        deck = original(*args, **kwargs)
        for slide in deck.slides:
            slide.layers[0].enter_cue = None
        return deck

    monkeypatch.setattr(persistent, "presentation", presentation)
    player = make_player(start_paused=True)
    pump(qapp, lambda: not player.clips.preparing and bool(player.live.last_frames))
    assert "stan gotowy, czeka na start" in player.presenter_snapshot()
    assert "cue czeka" not in player.presenter_snapshot()
    player.play_pause()
    pump(qapp, lambda: persistent.initialized(player))


def test_multiple_previous_new_branch_replay_reverse_and_no_cue(
    qapp, make_player, checkpoint_decks
):
    player = make_player()
    pump(qapp, lambda: persistent.initialized(player))
    session = player.live.sessions[0]
    manual(qapp, player, "paint")
    left = player.live.last_frames[session].pixels
    player.load_next_slide()
    entered(qapp, player)
    middle = player.live.last_frames[session].pixels
    player.load_next_slide()
    entered(qapp, player)
    player.previous()
    pump(qapp, lambda: settled(player))
    assert player.live.last_frames[session].pixels == middle
    player.previous()
    pump(qapp, lambda: settled(player))
    assert player.live.last_frames[session].pixels == left
    player.load_next_slide()
    entered(qapp, player)
    assert player.live.last_frames[session].pixels == middle
    player.replay()
    entered(qapp, player)
    player.reverse()
    pump(qapp, lambda: settled(player))
    player.replay()
    entered(qapp, player)
    assert player.playing_reversed_slide
    assert "live powtarza cue do przodu" in player.presenter_snapshot()
    player.load_next_slide()
    pump(qapp, lambda: settled(player))
    player.current_presentation_config.slides[1].layers[0].enter_cue = None
    old = player.live.last_frames[session].pixels
    player.load_next_slide()
    pump(qapp, lambda: settled(player))
    before = player.live.last_frames[session].pixels
    assert before == old
    manual(qapp, player, "paint")
    player.replay()
    pump(qapp, lambda: settled(player))
    assert player.live.last_frames[session].pixels == before


@pytest.mark.parametrize("failure", ["missing", "unsupported", "limit", "restore_failed"])
def test_player_fallback_preserves_image_status_and_generation(
    qapp, make_player, checkpoint_decks, failure
):
    from test_live_layers import recorded_sends

    player = make_player()
    pump(qapp, lambda: persistent.initialized(player))
    session = player.live.sessions[0]
    history = player.live.histories[session]
    if failure == "missing":
        history.command("drop_checkpoint", history.stack[-1].checkpoint)
        player.live.flush_history(session, history)
        pump(qapp, lambda: not session._outgoing)
    else:
        manual(qapp, player, "fail_restore" if failure == "restore_failed" else failure)
    last = player.live.last_frames[session].pixels
    sent = recorded_sends(session)
    player.replay()
    pump(qapp, lambda: not player.clips.preparing and bool(history.degraded))
    assert failure in player.presenter_snapshot()
    assert player.live.last_frames[session].pixels == last
    assert not any(command.startswith("enter ") for command in sent)
    player.update_presenter_state()
    assert history.degraded in player.state_overlay.text()
    if failure == "restore_failed":
        pump(qapp, lambda: not session.running)
        assert session._shm is None
        player.load_next_slide()
        entered(qapp, player)
        assert player.live.sessions[0] is not session
    else:
        assert session.running and not session.stopping


def test_shutdown_during_restore_reaps_worker_and_shm(qapp, make_player, checkpoint_decks):
    player = make_player()
    pump(qapp, lambda: persistent.initialized(player))
    session = player.live.sessions[0]
    player.load_next_slide()
    entered(qapp, player)
    player.replay()
    history = player.live.histories[session]
    pump(qapp, lambda: history.started_restore is not None)
    player.close()
    pump(qapp, lambda: not session.running)
    assert session._shm is None and session._socket is None


def test_video_and_clip_replay_prime_beginning_behind_restore(
    qapp, tmp_path, make_player, checkpoint_decks, monkeypatch
):
    from qtpy.QtMultimedia import QMediaPlayer
    from test_clip_layers import make_clip

    from manimcue.slides.config import ClipLayer

    clip = make_clip(tmp_path / "replay-clip.mp4", 1)
    original = persistent.presentation

    def presentation(*args, **kwargs):
        deck = original(*args, **kwargs)
        for slide in deck.slides:
            slide.layers[1] = ClipLayer(file=clip, rect=(0, 0, 0.2, 0.2))
        return deck

    monkeypatch.setattr(persistent, "presentation", presentation)
    player = make_player(video=True)
    pump(qapp, lambda: persistent.initialized(player))
    base_first = player.clips.base_frame.toImage().copy()
    clip_first = player.clips.frames[1].toImage().copy()
    pump(qapp, lambda: player.media_player.position() > 150)
    player.replay()
    pump(qapp, lambda: player.clips.base_frame is not None and 1 in player.clips.frames)
    assert player.clips.preparing
    assert player.media_player.playbackState() == QMediaPlayer.PlaybackState.PausedState
    assert player.clips.players[1].playbackState() == QMediaPlayer.PlaybackState.PausedState
    assert player.media_player.position() <= 50 and player.clips.players[1].position() <= 50
    assert player.clips.base_frame.toImage() == base_first
    assert player.clips.frames[1].toImage() == clip_first
    entered(qapp, player)


@pytest.mark.parametrize("automatic", ["auto_next", "skip_all"])
def test_automatic_callback_from_reverse_preserves_live(
    qapp, make_player, checkpoint_decks, automatic
):
    from qtpy.QtMultimedia import QMediaPlayer

    player = make_player(video=True, slide_index=1, skip_all=automatic == "skip_all")
    pump(qapp, lambda: persistent.initialized(player))
    player.reverse()
    pump(qapp, lambda: settled(player))
    session = player.live.sessions[0]
    history = player.live.histories[session]
    request = history.request
    if automatic == "auto_next":
        player.current_slide_config.auto_next = True
    player.media_player.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)
    assert player.current_slide_index == 0 and not player.playing_reversed_slide
    assert history.request == request
    assert not player.live.entry_cues


@pytest.mark.parametrize("engine", ["gl", "ce"])
def test_checkpoint_graph_updater_identity_and_repeat(engine):
    if engine == "gl":
        from manimlib import Group, Square
    else:
        from manim import Group, Square
    child = Square()
    left, right = Group(child), Group(child)
    updater = lambda mob, dt: None
    child.add_updater(updater)
    scene = SimpleNamespace(
        mobjects=[left, right], foreground_mobjects=[], time=1, renderer=SimpleNamespace(time=1)
    )
    estimate = PanelSnapshot.estimate(scene)
    snapshot = PanelSnapshot(scene)
    child.clear_updaters()
    left.remove(child)
    child.shift([1, 0, 0])
    for _ in range(2):
        snapshot.restore(scene)
        assert left.submobjects[0] is child is right.submobjects[0]
        assert child.updaters == [updater]
        assert abs(child.get_center()[0]) < 1e-10
    assert estimate > child.points.nbytes if engine == "ce" else estimate > child.data.nbytes


@pytest.mark.parametrize("engine", ["gl", "ce"])
def test_checkpoint_memory_100_entries_history_sharing_and_preallocation(engine, monkeypatch):
    if engine == "gl":
        from manimlib import Square
    else:
        from manim import Square
    scene = SimpleNamespace(
        mobjects=[Square()],
        foreground_mobjects=[],
        time=0,
        undo_stack=[],
        cursor=0,
        live_status=lambda event: events.append(event),
    )
    events = []
    store = CheckpointStore(scene)
    shared = store.capture()
    scene.undo_stack.append(shared)
    for i in range(100):
        scene.mobjects[0].shift([0.01, 0, 0])
        store.checkpoint(f"g1_e{i + 1}")
        assert len(store.entries) <= 50
        assert store.accounted_bytes() + 4 * PanelSnapshot.estimate(scene) <= store.max_bytes
    assert len(events) == 50
    assert all(row[2] == (shared,) for row in store.entries.values())
    size = shared.byte_size
    assert store.accounted_bytes() == (
        size
        + sum(row[0].byte_size for row in store.entries.values())
        + PanelSnapshot.estimate(scene)
    )
    protected = store.protected
    store.max_bytes = store.accounted_bytes()
    store.reserve()
    assert protected in store.entries and len(store.entries) < 50
    store.entries.clear()
    scene.undo_stack.clear()
    assert store.accounted_bytes() == 0
    store.max_bytes = 1
    with monkeypatch.context() as patch:
        patch.setattr(PanelSnapshot, "__init__", lambda *args: pytest.fail("kopia przed odmową"))
        with pytest.raises(MemoryError):
            store.checkpoint("g1_e101")
    scene.mobjects[0].resource = object()
    with pytest.raises(UnsupportedSnapshot):
        store.capture()


@pytest.mark.parametrize("engine", ["gl", "ce"])
def test_snapshot_working_copy_peak_fits_reserved_graph(engine):
    if engine == "gl":
        from manimlib import Group, Square
    else:
        from manim import Group, Square

        __import__("manimcue.live_scene_ce")
    child = Square()
    scene = SimpleNamespace(
        mobjects=[Group(child), Group(child)],
        foreground_mobjects=[],
        time=0,
        renderer=SimpleNamespace(time=0),
        num_plays=0,
    )
    if engine == "gl":
        scene.frame = object()
        scene.assemble_render_groups = lambda: None
        scene.get_mobject_family_members = lambda: [
            node for root in scene.mobjects for node in root.get_family()
        ]

    def play(*animations, **kwargs):
        for animation in animations:
            animation.begin()
            animation.interpolate(0.5)
            animation.finish()

    scene.play = play
    estimate = PanelSnapshot.estimate(scene)
    tracemalloc.start()
    try:
        snapshot = PanelSnapshot(scene)
        _, capture_peak = tracemalloc.get_traced_memory()
        child.shift([1, 0, 0])
        baseline, _ = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        snapshot.animate(scene)
        _, peak = tracemalloc.get_traced_memory()
        working_peak = peak - baseline
    finally:
        tracemalloc.stop()
    (Path(__file__).parents[1] / ".tmp" / f"f5g-memory-{engine}.json").write_text(
        json.dumps(
            {
                "estimate_bytes": estimate,
                "capture_peak_bytes": capture_peak,
                "working_peak_bytes": working_peak,
                "reserve_bytes": 4 * estimate,
            }
        ),
        encoding="utf-8",
    )
    assert capture_peak <= 4 * estimate
    assert working_peak <= 4 * estimate


@pytest.mark.parametrize("engine", ["gl", "ce"])
def test_snapshot_retained_removed_originals_reserve_before_copy(engine, monkeypatch):
    import numpy as np

    if engine == "gl":
        from manimlib import Square
    else:
        from manim import Square
    node = Square()
    scene = SimpleNamespace(
        mobjects=[node],
        foreground_mobjects=[],
        time=0,
        undo_stack=[],
        cursor=0,
        live_status=lambda _: None,
    )
    store = CheckpointStore(scene)
    store.checkpoint("g1_e1")
    before = store.accounted_bytes()
    node.payload = np.zeros(1024 * 1024, dtype=np.uint8)
    scene.mobjects.clear()
    assert store.accounted_bytes() > before + 1024 * 1024
    store.max_bytes = 100 * 1024
    monkeypatch.setattr(PanelSnapshot, "__init__", lambda *args: pytest.fail("kopia przed odmową"))
    with pytest.raises(MemoryError):
        store.capture()
    snapshot = store.entries["g1_e1"][0]
    store.max_bytes = store.accounted_bytes() + 4 * snapshot.byte_size
    monkeypatch.setattr(
        snapshot, "animate", lambda *args: pytest.fail("restore bez rezerwy kopii oryginału")
    )
    with pytest.raises(MemoryError):
        store.restore("g1_e1")
    store.entries.clear()
    assert store.accounted_bytes() == 0


def test_history_status_without_frame_stale_operation_and_fallback():
    history = EntryHistory()
    history.prepare((0, 0), "move", "initial", 0)
    old = history.expected
    history.prepare((0, 1), "move", "next", 0.1)
    current = history.expected
    history.accept(f"CHECKPOINT_READY {old[0]} {old[1]} 2")
    assert history.waiting and history.completed is None
    history.accept(f"CHECKPOINT_READY {current[0]} {current[1]} 3")
    assert history.waiting
    history.received.add(3)
    history.finish()
    assert not history.waiting and history.status == "checkpoint gotowy"
    history.prepare((0, 0), "move", "previous", 0.2)
    assert len(history.stack) == 1
    request, checkpoint = history.expected
    history.accept(f"CHECKPOINT_ERROR {request} {checkpoint} missing")
    history.accept("READY")
    assert "missing" in history.degraded
    assert not history.waiting
    history.prepare((0, 0), "move", "replay", 0.3)
    request, checkpoint = history.expected
    history.received.add(4)
    history.accept(f"RESTORE_DONE {request} {checkpoint} 4")
    history.finish()
    assert history.degraded is None and "początek" in history.status


def test_protocol_validation_fifo_stale_generation_duplicates_and_invalidated_entry():
    transport = LiveTransport()
    transport.PRESETS = {"move": lambda scene: None}
    transport.live_generation = None
    transport.live_request = transport.live_entry_counter = 0
    transport.live_reserved = None
    transport.live_loop = False
    transport.live_commands = deque()
    events = []
    transport.live_status = events.append
    for invalid in (
        "checkpoint",
        "checkpoint 0 g1_e1",
        "enter 1 g1_e1 unknown",
        "checkpoint 1 " + "g" * 65,
        "restore 1 g1_e1 extra",
    ):
        transport.live_queue_operation(invalid)
    assert not transport.live_commands and transport.live_reserved is None
    transport.live_queue_operation("checkpoint 1 g1_e1")
    assert transport.live_commands[0] == ("checkpoint", "1", "g1_e1")
    transport.live_queue_operation("checkpoint 1 g1_e1")
    transport.live_queue_operation("checkpoint 2 g1_e1")
    transport.live_queue_operation("restore 2 g2_e1")
    assert events[-1].endswith("stale_generation") and len(transport.live_commands) == 1
    transport.live_queue_operation("restore 2 g1_e1")
    assert len(transport.live_commands) == 2
    transport.live_commands.extend(["move"] * 126)
    transport.live_queue_operation("restore 3 g1_e1")
    assert len(transport.live_commands) == 128
    buffer = LineBuffer()
    buffer.feed(b"check")
    buffer.feed(b"point 1 g1_e1\nrestore 2 g1_e1\n")
    assert buffer.pop_line() == "checkpoint 1 g1_e1"
    assert buffer.pop_line() == "restore 2 g1_e1"
    with pytest.raises(ValueError, match="512"):
        buffer.feed(b"x" * 513)


def test_partial_restore_failure_is_fatal_and_protects_target(monkeypatch):
    from manim import Square

    scene = SimpleNamespace(
        mobjects=[Square()],
        foreground_mobjects=[],
        time=0,
        undo_stack=[],
        cursor=0,
        live_status=lambda _: None,
    )
    store = CheckpointStore(scene)
    store.checkpoint("g1_e1")
    snapshot = store.entries["g1_e1"][0]

    def fail(scene):
        scene.mobjects.clear()
        raise ValueError("po mutacji")

    monkeypatch.setattr(snapshot, "animate", fail)
    with pytest.raises(RestoreFailed):
        store.restore("g1_e1")
    assert "g1_e1" in store.entries and store.restoring is None


@pytest.fixture(params=["manimgl", "ce-cairo"])
def checkpoint_session(request):
    from test_live_corpus import is_ready
    from test_live_corpus import pump as live_pump

    from manimcue.live_session import LiveSession, LiveSpec

    engine, scene_name = (
        request.param if isinstance(request.param, tuple) else (request.param, "Panel")
    )
    session = LiveSession()
    session.checkpoint_engine = engine
    session.start(
        LiveSpec(
            str(
                Path(__file__).parent
                / "scenes"
                / ("checkpoint_ce.py" if engine == "ce-cairo" else "checkpoint_gl.py")
            ),
            scene_name,
            width=320,
            height=180,
            engine=engine,
        )
    )
    live_pump(session, is_ready, 15)
    yield session
    session.request_stop()
    live_pump(session, lambda events, frames: not session.running, 4)


def live_operation(session, command, prefix):
    from test_live_corpus import pump as live_pump

    session.send(command)

    def done(events, frames):
        statuses = [line for _, line in events if line.startswith(prefix)]
        return bool(statuses) and any(f.frame_id == int(statuses[-1].split()[-1]) for f in frames)

    return live_pump(session, done, 5)


def test_wire_checkpoint_restores_cursor_and_full_manual_history(checkpoint_session):
    from test_live_corpus import names
    from test_live_corpus import pump as live_pump

    session = checkpoint_session
    session.send("next")
    live_pump(session, lambda events, frames: "CUE_DONE step" in names(events), 3)
    _, frames = live_operation(session, "checkpoint 1 g1_e1", "CHECKPOINT_READY 1 ")
    expected = frames[-1].pixels
    session.send("release 2 g1_e1")
    live_pump(session, lambda events, frames: "ENTRY_RELEASED 2 g1_e1" in names(events), 3)
    session.send("next")
    session.send("paint")
    live_pump(session, lambda events, frames: "CUE_DONE paint" in names(events), 3)
    _, frames = live_operation(session, "restore 3 g1_e1", "RESTORE_DONE 3 ")
    assert frames[-1].pixels == expected
    session.send("release 4 g1_e1")
    live_pump(session, lambda events, frames: "ENTRY_RELEASED 4 g1_e1" in names(events), 3)
    session.send("back")
    _, frames = live_pump(session, lambda events, frames: any(f.boundary for f in frames), 3)
    assert frames[-1].pixels != expected
    session.send("next")
    _, frames = live_pump(session, lambda events, frames: "CUE_DONE step" in names(events), 3)
    assert frames[-1].pixels == expected


@pytest.mark.parametrize(
    "checkpoint_session", [("manimgl", "GraphPanel"), ("ce-cairo", "GraphPanel")], indirect=True
)
def test_wire_graph_topology_styles_and_updater_references(checkpoint_session):
    from test_live_corpus import names
    from test_live_corpus import pump as live_pump

    session = checkpoint_session
    _, first = live_operation(session, "checkpoint 1 g1_e1", "CHECKPOINT_READY 1 ")
    session.send("release 2 g1_e1")
    live_pump(session, lambda events, frames: "ENTRY_RELEASED 2 g1_e1" in names(events), 3)
    session.send("mutate")
    live_pump(session, lambda events, frames: "CUE_DONE mutate" in names(events), 3)
    _, frames = live_operation(session, "restore 3 g1_e1", "RESTORE_DONE 3 ")
    assert frames[-1].pixels == first[-1].pixels
    session.send("release 4 g1_e1")
    live_pump(session, lambda events, frames: "ENTRY_RELEASED 4 g1_e1" in names(events), 3)
    session.send("verify")
    live_pump(session, lambda events, frames: "GRAPH_VERIFIED" in names(events), 3)
    assert session.error is None


def test_wire_gl_camera_checkpoint_restore_reset(checkpoint_session):
    from test_live_corpus import names
    from test_live_corpus import pump as live_pump

    session = checkpoint_session
    _, first = live_operation(session, "checkpoint 1 g1_e1", "CHECKPOINT_READY 1 ")
    session.send("release 2 g1_e1")
    live_pump(session, lambda events, frames: "ENTRY_RELEASED 2 g1_e1" in names(events), 3)
    session.send("view zoom 1")
    if session.checkpoint_engine == "manimgl":
        live_pump(session, lambda events, frames: bool(frames), 3)
    _, restored = live_operation(session, "restore 3 g1_e1", "RESTORE_DONE 3 ")
    assert restored[-1].pixels == first[-1].pixels
    session.send("release 4 g1_e1")
    live_pump(session, lambda events, frames: "ENTRY_RELEASED 4 g1_e1" in names(events), 3)
    if session.checkpoint_engine == "manimgl":
        session.send("view zoom 1")
        live_pump(session, lambda events, frames: bool(frames), 3)
        session.send("view reset")
        _, frames = live_pump(session, lambda events, frames: bool(frames), 3)
        assert frames[-1].pixels == first[-1].pixels


def test_wire_reservation_unknown_cue_stale_generation_drop_and_disconnect(checkpoint_session):
    from test_live_corpus import names
    from test_live_corpus import pump as live_pump

    session = checkpoint_session
    live_operation(session, "checkpoint 1 g1_e1", "CHECKPOINT_READY 1 ")
    for command in ("next", "back", "paint", "view zoom 1"):
        session.send(command)
    events, _ = live_pump(
        session, lambda events, frames: names(events).count("LIVE_RESERVED") == 4, 3
    )
    assert not any(event.startswith("CUE_START") for event in names(events))
    session.send("enter 2 g1_e1 unknown")
    live_pump(
        session, lambda events, frames: "CHECKPOINT_ERROR 2 g1_e1 invalid" in names(events), 3
    )
    live_operation(session, "enter 3 g1_e1 move", "ENTRY_CUE_DONE 3 ")
    session.send("restore 4 g2_e1")
    live_pump(
        session,
        lambda events, frames: "CHECKPOINT_ERROR 4 g2_e1 stale_generation" in names(events),
        3,
    )
    session.send("drop_checkpoint 4 g1_e1")
    session.send("drop_checkpoint 5 g1_e1")
    live_pump(session, lambda events, frames: "CHECKPOINT_DROPPED 5 g1_e1" in names(events), 3)
    session.send("restore 6 g1_e1")
    live_pump(
        session, lambda events, frames: "CHECKPOINT_ERROR 6 g1_e1 missing" in names(events), 3
    )
    assert session.error is None
    session._socket.close()
    session._socket = None
    session.request_stop()
    live_pump(session, lambda events, frames: not session.running, 4)


def test_state_command_finishes_callable_and_loop_iteration(checkpoint_session):
    from test_live_corpus import names, pump_for
    from test_live_corpus import pump as live_pump

    session = checkpoint_session
    session.send("two_stage")
    pump_for(session, 0.1)
    began = time.perf_counter()
    live_operation(session, "checkpoint 1 g1_e1", "CHECKPOINT_READY 1 ")
    assert time.perf_counter() - began < 0.5
    session.send("release 2 g1_e1")
    live_pump(session, lambda events, frames: "ENTRY_RELEASED 2 g1_e1" in names(events), 3)
    session.send("verify_end")
    live_pump(session, lambda events, frames: "END_VERIFIED" in names(events), 3)
    session.send("cycle")
    live_pump(session, lambda events, frames: "CUE_START cycle" in names(events), 3)
    pump_for(session, 0.04)
    began = time.perf_counter()
    events, _ = live_operation(session, "checkpoint 3 g1_e2", "CHECKPOINT_READY 3 ")
    assert 0.08 < time.perf_counter() - began < 0.4
    assert "LOOP_WAIT 3 g1_e2" in names(events)
    assert "CUE_DONE cycle" in names(events)


def test_checkpoint_boundary_waits_for_ack_before_restore(checkpoint_session):
    from test_live_corpus import names, pump_for

    session = checkpoint_session
    session.send("checkpoint 1 g1_e1")
    events, boundary = [], None
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        events.extend(session.poll())
        frame = session.try_read_frame(acknowledge=False)
        if frame is not None and frame.boundary:
            boundary = frame
        if boundary and any(line.startswith("CHECKPOINT_READY 1 ") for line in events):
            break
        time.sleep(0.002)
    assert boundary is not None
    session.send("restore 2 g1_e1")
    observed, frames = pump_for(session, 0.15)
    assert not frames and not any(line.startswith("RESTORE_START") for line in names(observed))
    session.send(f"frame_seen {boundary.frame_id}")
    from test_live_corpus import pump as live_pump

    live_pump(
        session,
        lambda events, frames: (
            any(line.startswith("RESTORE_DONE 2 ") for line in names(events))
            and any(f.boundary for f in frames)
        ),
        3,
    )


def test_thirty_restore_trials_boundary_latency_and_gui_poll(qapp, make_player, checkpoint_decks):
    player = make_player()
    pump(qapp, lambda: persistent.initialized(player))
    session = player.live.sessions[0]
    player.load_next_slide()
    entered(qapp, player)
    durations, reads, rows = [], [], []
    original_poll, original_read = session.poll, session.try_read_frame

    def poll():
        began = time.perf_counter()
        result = original_poll()
        durations.append(1000 * (time.perf_counter() - began))
        return result

    def read(**kwargs):
        began = time.perf_counter()
        result = original_read(**kwargs)
        reads.append(1000 * (time.perf_counter() - began))
        return result

    session.poll, session.try_read_frame = poll, read
    current = None

    def received(index, frame, when):
        if current is not None and "boundary_ms" not in current:
            if frame.boundary:
                current["boundary_ms"] = 1000 * (when - current["began"])
            else:
                current["interior"].add(frame.pixels)

    player.live.frame_received.connect(received)
    for _ in range(30):
        current = {"began": time.perf_counter(), "interior": set()}
        player.replay()
        pump(qapp, lambda row=current: "boundary_ms" in row, timeout=5)
        entered(qapp, player)
        rows.append(
            {
                "boundary_ms": current["boundary_ms"],
                "different_interior_frames": len(current["interior"]),
            }
        )
        current = None
    session.poll, session.try_read_frame = original_poll, original_read
    values = sorted(row["boundary_ms"] for row in rows)
    result = {
        "engine": checkpoint_decks,
        "panel_size": [160, 90],
        "trials": rows,
        "p50_ms": statistics.median(values),
        "p95_ms": values[28],
        "max_ms": max(values),
        "poll_max_ms": max(durations),
        "read_max_ms": max(reads),
        "worker": session.checkpoint_metrics,
    }
    output = Path(__file__).parents[1] / ".tmp" / f"f5g-{checkpoint_decks}.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    assert all(row["different_interior_frames"] > 1 for row in rows)
    assert all(500 <= value <= 700 for value in values)
    assert max(durations) < 50 and max(reads) < 50
