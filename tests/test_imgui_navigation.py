"""Tabela nawigacji F10 z kontrolowanym czasem."""

import pytest

from manimcue.player.clock import media_time
from manimcue.player.controller import reduce
from manimcue.player.state import initial_state


def make_state(**options):
    state = initial_state(
        {
            "resolution": [100, 100],
            "presentations": [
                {"slides": [{"kind": "video", "loop": True}, {"kind": "image"}]},
                {"resolution": [200, 100], "slides": [{"kind": "video"}]},
            ],
        }
    )
    return {**state, **options}


def act(state, action, now=1, **event):
    return reduce(state, {"type": action, **event}, now)


def running(**options):
    state, _ = act(make_state(requested_playing=True, **options), "ready")
    return state


def test_preparing_next_pause_replay_and_stale():
    state = make_state()
    assert act(state, "replay")[0] == state
    state, _ = act(state, "pause")
    assert state["requested_playing"]
    state, _ = act(state, "pause")
    assert not state["requested_playing"]
    state, effects = act(state, "next")
    assert state["preparing"] and state["requested_playing"] and not effects
    state, effects = act(state, "next")
    assert state["index"] == [0, 1] and state["entry_id"] == 2
    assert effects == [{"type": "cancel", "entry_id": 1}, {"type": "prepare", "entry_id": 2}]
    assert act(state, "ready", entry_id=1) == (state, [])


def test_paused_static_and_clock():
    state = running(index=[0, 1])
    state, _ = act(state, "pause", 2)
    assert media_time(state["clock"], 100) == 1
    state, _ = act(state, "next", 100)
    assert state["index"] == [0, 1] and not state["paused"]
    assert media_time(state["clock"], 101) == 2
    assert act(state, "next")[0]["index"] == [1, 0]


def test_loop_exit():
    state = running(next_terminates_loop=True)
    state, effects = act(state, "next")
    assert state["loop_exit_requested"] and not effects
    state, effects = act(state, "iteration_end", 3)
    assert state["ended"] and state["termination_achieved"]
    assert effects[0]["type"] == "stop_files"
    assert act(state, "next")[0]["index"] == [0, 1]
    state = running()
    state, effects = act(state, "iteration_end", 5)
    assert effects[0]["type"] == "loop" and media_time(state["clock"], 5) == 0


@pytest.mark.parametrize("action,reverse", [("previous", False), ("reverse", True)])
def test_backward_across_decks_and_beginning(action, reverse):
    state = running(index=[1, 0])
    state, effects = act(state, action)
    assert state["index"] == [0, 1] and state["reverse"] == reverse
    assert state["entry_id"] == 2 and effects[-1]["type"] == "prepare"
    state = running()
    first, effects = act(state, action)
    assert first["index"] == [0, 0] and first["entry_id"] == 1 and not effects
    assert first["message"]


def test_reverse_to_normal_preserves_live_and_replay_direction():
    state = running(index=[0, 1], reverse=True)
    replay, _ = act(state, "replay")
    assert replay["reverse"] and replay["preparing"]
    normal, effects = act(state, "next")
    assert normal["index"] == [0, 1] and not normal["reverse"]
    assert effects[-1]["preserve_live"]


@pytest.mark.parametrize("auto,skip", [(True, False), (False, True)])
def test_eof_and_auto_next(auto, skip):
    state = running(skip_all=skip)
    state["manifest"]["presentations"][0]["slides"][0]["auto_next"] = auto
    state, effects = act(state, "eof")
    assert state["index"] == [0, 1]
    assert [effect["type"] for effect in effects] == ["stop_files", "cancel", "prepare"]


def test_ended_pause_never_restarts_base():
    state, _ = act(running(), "eof", 3)
    state, _ = act(state, "pause", 4)
    state, _ = act(state, "pause", 10)
    assert state["ended"] and not state["clock"]["playing"]
    assert media_time(state["clock"], 100) == 2


def test_start_at_zero_negative_resolution_and_preview():
    state = running(preview={"old": True})
    state, _ = act(state, "start_at", index=[-1, -1])
    assert state["index"] == [1, 0] and state["resolution"] == [200, 100]
    assert state["preview"] is None
    state, _ = act(state, "start_at", index=[0, 0])
    assert state["index"] == [0, 0]
    with pytest.raises(ValueError):
        act(state, "start_at", index=[0, 100])


def test_last_quit_and_message_revision():
    state = running(index=[1, 0])
    state, _ = act(state, "next")
    revision = state["message_revision"]
    state, _ = act(state, "message", 2, text="nowy")
    assert act(state, "message_expired", 20, revision=revision)[0]["message"] == "nowy"
    assert act(state, "message_expired", 20, revision=revision + 1)[0]["message"] is None
    assert act({**state, "exit_after_last_slide": True}, "next")[0]["closing"]
    closed, effects = act(state, "quit")
    assert closed["closing"] and effects[0]["type"] == "begin_shutdown"
    assert act(closed, "next") == (closed, [])
