"""Kontrakt D33 i routing playera powtórzony z rzeczywistym backendem Cairo."""

from pathlib import Path

import pytest
import test_persistent_live as persistent

make_player = persistent.make_player
qapp = persistent.qapp


@pytest.fixture(autouse=True)
def ce_decks(monkeypatch):
    original = persistent.presentation
    monkeypatch.setattr(
        persistent, "SCENE", Path(__file__).parents[1] / "examples/live_three_ce.py"
    )

    def presentation(*args, **kwargs):
        deck = original(*args, **kwargs)
        for slide in deck.slides:
            for layer in slide.layers:
                if layer.kind == "live":
                    layer.engine = "ce-cairo"
        return deck

    monkeypatch.setattr(persistent, "presentation", presentation)


def test_ce_persistent_pid_image_remap_and_focus(qapp, make_player):
    persistent.test_persistent_pid_image_remap_and_focus(qapp, make_player)


@pytest.mark.parametrize("mode", ["missing_id", "stopping", "error", "gap"])
def test_ce_sessions_not_reclaimed(qapp, make_player, mode):
    persistent.test_sessions_not_reclaimed(qapp, make_player, mode)


@pytest.mark.parametrize(
    "action",
    [
        "next",
        "auto_next",
        "skip_all",
        "previous",
        "reverse",
        "replay",
        "reverse_normal",
        "loop",
        "close",
    ],
)
def test_ce_entry_navigation(qapp, make_player, action):
    persistent.test_entry_cue_navigation_callbacks(qapp, make_player, action)


def test_ce_barrier_pause_timeout(qapp, make_player):
    persistent.test_live_only_static_barrier_pause_and_timeout(qapp, make_player)


def test_ce_entry_first_actual_start(qapp, make_player):
    persistent.test_entry_waits_until_first_actual_start(qapp, make_player)


def test_ce_presentation_isolation(qapp, make_player):
    persistent.test_navigation_boundaries_and_presentation_isolation(qapp, make_player)


def test_ce_retained_alpha_over_new_base(qapp, tmp_path, monkeypatch):
    import test_preview_alpha_border as alpha

    from manimcue.slides.config import LiveLayer

    monkeypatch.setattr(alpha, "SCENE", Path(__file__).parent / "scenes/live_ce_extra.py")
    monkeypatch.setattr(alpha, "LiveLayer", lambda **kwargs: LiveLayer(engine="ce-cairo", **kwargs))
    alpha.test_retained_alpha_remixes_after_index_and_base_change(qapp, tmp_path)


def test_two_ce_and_gl_animate_and_close(qapp, tmp_path):
    from test_live_layers import pump

    from manimcue.slides.config import Config, LiveLayer
    from manimcue.slides.present.player import Player

    deck = persistent.presentation(tmp_path)
    for slide in deck.slides:
        slide.layers += [
            LiveLayer(
                scene_file=Path(__file__).parents[1] / "examples/live_panel_ce.py",
                scene_name="Panel",
                engine="ce-cairo",
                rect=(0, 0, 0.4, 0.5),
                fps=30,
                background_opacity=0.5,
                session_id="second",
            ),
            LiveLayer(
                scene_file=Path(__file__).parents[1] / "examples/live_three.py",
                scene_name="ThreePanel",
                rect=(0.1, 0.5, 0.3, 0.4),
                session_id="gl",
            ),
        ]
    player = Player(Config(), [deck])
    try:
        pump(
            qapp,
            lambda: all(
                s.state == "ready"
                and s in player.live.last_frames
                and not player.live.histories[s].reserved
                for s in player.live.sessions.values()
            ),
        )
        sessions = list(player.live.sessions.values())
        frames = {s: player.live.last_frames[s].frame_id for s in sessions}
        for s in sessions:
            s.send("next")
        pump(
            qapp, lambda: all(player.live.last_frames[s].frame_id > frames[s] + 2 for s in sessions)
        )
        assert len({s._process.pid for s in sessions}) == 3
        player.load_next_slide()
        pump(
            qapp,
            lambda: (
                not player.clips.preparing
                and all(not history.reserved for history in player.live.histories.values())
            ),
        )
        assert list(player.live.sessions.values()) == sessions
        player.previous()
        pump(
            qapp,
            lambda: (
                not player.clips.preparing
                and all(not history.reserved for history in player.live.histories.values())
            ),
        )
        assert not any(history.degraded for history in player.live.histories.values())
        player.close()
        player.live.shutdown()
        assert all(not s.running and s._shm is None for s in sessions)
    finally:
        player.close()
        player.live.shutdown()
