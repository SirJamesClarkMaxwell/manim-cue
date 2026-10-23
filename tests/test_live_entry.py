"""Lokalna historia po skoku miniaturą zachowuje monotoniczną korelację socketu."""

from manimcue.live_entry import EntryHistory


def test_jump_live_history_during_restore_stale_status_previous_v_r():
    history = EntryHistory()
    history.prepare((0, 0), "move", "initial", 0)
    history.prepare((0, 1), "move", "next", 1)
    history.prepare((0, 0), "move", "previous", 2)
    request, checkpoint = history.expected
    history.accept(f"RESTORE_START {request} {checkpoint}")
    generation, counter = history.generation, history.counter
    assert history.prepare((0, 1), "move", "start_at", 3) is None
    expected = history.expected
    assert history.generation == generation and history.counter > counter
    assert len(history.stack) == 1 and not history.stack[0].has_predecessor
    assert int(expected[0]) > int(request)
    history.accept(f"RESTORE_DONE {request} {checkpoint} 9")
    assert history.expected == expected and history.completed is None
    assert not any(command.startswith("enter ") for command in history.outgoing)
    history.prepare((0, 0), "move", "reverse", 4)
    assert history.degraded and history.expected is None
