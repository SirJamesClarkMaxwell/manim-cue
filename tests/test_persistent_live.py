"""D33: ciągi sesji, rzeczywiste callbacki nawigacji i bariera cue wejścia."""

import time
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_live_layers import key, png, pump, recorded_sends

from manimcue.slides.config import (
    ClipLayer,
    Config,
    LiveLayer,
    PresentationConfig,
    SlideConfig,
    SlideType,
)

SCENE = Path(__file__).resolve().parents[1] / "examples" / "live_three.py"


@pytest.fixture
def qapp():
    from manimcue.slides.qt_utils import qapp

    return qapp()


def presentation(tmp_path, *, session_id="panel", video=False, swapped=False):
    from test_clip_layers import make_clip

    base = make_clip(tmp_path / "base.mp4", 1) if video else png(tmp_path / "base.png", (0, 0, 60))
    live = LiveLayer(
        scene_file=SCENE,
        scene_name="ThreePanel",
        rect=(0.5, 0, 0.5, 0.5),
        session_id=session_id,
        enter_cue="flip",
    )
    clip = ClipLayer(file=png(tmp_path / "clip.png", (0, 0, 255)), rect=(0, 0, 0.2, 0.2))
    slides = [
        SlideConfig(
            file=base,
            rev_file=base,
            type=SlideType.Video if video else SlideType.Image,
            layers=[clip, live.model_copy()] if swapped and i == 1 else [live.model_copy(), clip],
        )
        for i in range(3)
    ]
    return PresentationConfig(slides=slides, resolution=(320, 180))


def test_model_roundtrip_legacy_and_runs(tmp_path):
    deck = presentation(tmp_path)
    path = tmp_path / "deck.json"
    deck.to_file(path)
    loaded = PresentationConfig.from_file(path)
    assert loaded.slides[0].layers[0].session_id == "panel"
    assert loaded.slides[0].layers[0].enter_cue == "flip"
    old = deck.model_dump(mode="json")
    for slide in old["slides"]:
        del slide["layers"][0]["session_id"]
        del slide["layers"][0]["enter_cue"]
    assert PresentationConfig.model_validate(old).slides[0].layers[0].session_id is None
    deck.slides[1].layers[0].rect = (0, 0.5, 0.5, 0.5)
    PresentationConfig.model_validate(deck.model_dump())
    deck.slides[1].layers[0].fps = 30
    with pytest.raises(ValidationError, match="slajdy 1, 2"):
        PresentationConfig.model_validate(deck.model_dump())
    # Po przerwie to nowa generacja, więc inny fps jest dozwolony.
    deck.slides[1].layers = []
    deck.slides[2].layers[0].fps = 20
    PresentationConfig.model_validate(deck.model_dump())
    deck.slides[0].layers.append(deck.slides[0].layers[0])
    with pytest.raises(ValidationError, match="slajd 1: duplikat"):
        PresentationConfig.model_validate(deck.model_dump())


@pytest.mark.parametrize(
    "field,value", [("scene_name", "Other"), ("fps", 30), ("rect", (0, 0, 0.4, 0.5))]
)
def test_inconsistent_run_from_file(tmp_path, field, value):
    import json

    deck = presentation(tmp_path).model_dump(mode="json")
    deck["slides"][1]["layers"][0][field] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(deck), encoding="utf-8")
    with pytest.raises(ValidationError, match="slajdy 1, 2"):
        PresentationConfig.from_file(path)


@pytest.fixture
def make_player(qapp, tmp_path):
    from qtpy.QtCore import Qt

    from manimcue.slides.present.player import Player

    players = []

    def make(**kwargs):
        options = {
            name: kwargs.pop(name) for name in ("session_id", "video", "swapped") if name in kwargs
        }
        player = Player(
            Config(),
            [presentation(tmp_path, **options)],
            aspect_ratio_mode=Qt.AspectRatioMode.KeepAspectRatio,
            **kwargs,
        )
        player.resize(320, 180)
        super(Player, player).show()
        players.append(player)
        return player

    yield make
    for player in players:
        player.close()
        player.live.shutdown()
    qapp.processEvents()


def initialized(player):
    return (
        player.live.sessions[0].state == "ready"
        and bool(player.live.last_frames)
        and not player.clips.preparing
    )


@pytest.mark.gpu
def test_persistent_pid_image_remap_and_focus(qapp, make_player):
    from qtpy.QtCore import Qt

    player = make_player(swapped=True)
    pump(qapp, lambda: initialized(player))
    session = player.live.sessions[0]
    pid = session._process.pid
    session.send("flip")
    before = player.live.last_frames[session].frame_id
    pump(qapp, lambda: player.live.last_frames[session].frame_id > before)
    # Poczekaj na końcową klatkę cue; bezczynna scena nie publikuje ponownie.
    until = time.monotonic() + 0.7
    pump(qapp, lambda: time.monotonic() > until)
    image = player.live.images[session]
    frame = player.live.last_frames[session]
    player.live.click(0)
    player.load_next_slide(reason="previous")
    assert player.live.sessions[1] is session and session._process.pid == pid
    assert player.live.active is None
    assert player.live.last_frames[session] is frame
    assert player.composition.layer_items[1].pixmap().toImage() == image.convertToFormat(
        player.composition.layer_items[1].pixmap().toImage().format()
    )
    player.live.click(1)
    sent = recorded_sends(session)
    key(player, Qt.Key.Key_Right)
    assert sent == ["next"] and player.current_slide_index == 1
    player.previous()
    assert player.live.sessions[0] is session
    player.load_next_slide(reason="previous")
    assert player.live.sessions[1] is session


@pytest.mark.gpu
@pytest.mark.parametrize("mode", ["missing_id", "stopping", "error", "gap"])
def test_sessions_not_reclaimed(qapp, make_player, mode):
    player = make_player(session_id=None if mode == "missing_id" else "panel")
    pump(qapp, lambda: initialized(player))
    session = player.live.sessions[0]
    if mode == "stopping":
        session.request_stop()
    if mode == "error":
        session._event("ERROR test")
    if mode == "gap":
        player.current_slide_index = 2
        player.load_current_slide()
    else:
        player.load_next_slide()
    assert player.live.sessions[0] is not session
    assert player.live.sessions[0]._process.pid != session._process.pid


@pytest.mark.gpu
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
def test_entry_cue_navigation_callbacks(qapp, make_player, action):
    from qtpy.QtCore import Qt
    from qtpy.QtMultimedia import QMediaPlayer

    player = make_player(
        video=action in ("auto_next", "skip_all", "loop"),
        slide_index=1 if action in ("previous", "reverse", "reverse_normal") else 0,
        skip_all=action == "skip_all",
    )
    pump(qapp, lambda: initialized(player))
    session = player.live.sessions[0]
    sent = recorded_sends(session)
    if action == "auto_next":
        player.current_slide_config.auto_next = True
        player.media_player.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)
    elif action == "skip_all":
        player.media_player.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.EndOfMedia)
    elif action == "loop":
        player.current_slide_config.loop = True
        player.media_player.positionChanged.emit(200)
        player.media_player.positionChanged.emit(0)
    elif action == "reverse_normal":
        player.reverse()
        player.next()
    elif action == "next":
        key(player, Qt.Key.Key_Right)
    else:
        getattr(player, action)()
    if action in ("next", "auto_next", "skip_all"):
        pump(qapp, lambda: "flip" in sent)
        assert sent.count("flip") == 1
        assert player.live.active is None
    else:
        assert "flip" not in sent and "back" not in sent


@pytest.mark.gpu
def test_live_only_static_barrier_pause_and_timeout(qapp, make_player):
    player = make_player()
    # Przejście podczas startu: nowa sesja ma READY dopiero po zwolnieniu sztucznej blokady.
    session = player.live.sessions[0]
    original_poll = session.poll
    session.poll = list
    player.load_next_slide()
    assert player.clips.preparing and "live" in player.clips.pending
    player.play_pause()
    sent = recorded_sends(session)
    player.clips.prime_timeout(player.clips.entry)
    assert not player.clips.preparing and not player.clips.running
    assert "flip" not in sent and not player.live.entry_cues
    session.poll = original_poll
    pump(qapp, lambda: session.state == "ready")
    player.play_pause()
    assert player.clips.running and "flip" not in sent


@pytest.mark.gpu
def test_entry_waits_until_first_actual_start(qapp, make_player):
    player = make_player()
    pump(qapp, lambda: initialized(player))
    session = player.live.sessions[0]
    sent = recorded_sends(session)
    player.current_slide_index = 1
    player.current_file = player.current_slide_config.file
    player.load_current_media(start_paused=True, reason="next")
    assert not player.clips.running and "flip" not in sent
    player.play_pause()
    assert sent.count("flip") == 1
    player.play_pause()
    player.play_pause()
    assert sent.count("flip") == 1


@pytest.mark.gpu
def test_three_scene_one_click_ten_trials(qapp, tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "measure_player", Path(__file__).resolve().parents[1] / "examples" / "measure_player.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.measure(qapp, tmp_path, 10, True)
    assert len(result["trials"]) == 10
    for row in result["trials"]:
        assert row["pid_before"] == row["pid_after"]
        assert row["cue_sent"] >= row["transition_requested"]
        assert all(
            row[name + "_changed_gui"] >= row["transition_requested"]
            for name in ("base", "clip", "live")
        )
        assert row["spread_ms"] >= 0
        assert all(
            row[name + "_changed_gui"] >= row["barrier_released"]
            for name in ("base", "clip", "live")
        )


def test_preparation_pins_first_frames(qapp, tmp_path):
    from qtpy.QtGui import QImage
    from qtpy.QtMultimedia import QVideoFrame
    from test_clip_layers import make_clip, make_player, video_deck

    clip = ClipLayer(file=make_clip(tmp_path / "clip.mp4", 1))
    player = make_player([video_deck(tmp_path, [clip])])
    try:
        group = player.clips
        group.pending.add("hold")
        pump(qapp, lambda: group.pending == {"hold"})
        base_frame, clip_frame = group.base_frame, group.frames[0]
        changed = QImage(16, 16, QImage.Format.Format_RGBA8888)
        changed.fill(0xFF00FF00)
        sinks = [
            player.composition.video_item.videoSink(),
            player.composition.layer_items[0].videoSink(),
        ]
        for sink in sinks:
            sink.setVideoFrame(QVideoFrame(changed))
        assert sinks[0].videoFrame() == base_frame
        assert sinks[1].videoFrame() == clip_frame
        group.pending.clear()
        group.maybe_start()
        assert group.running
    finally:
        player.close()


@pytest.mark.gpu
def test_navigation_boundaries_and_presentation_isolation(qapp, make_player):
    player = make_player()
    pump(qapp, lambda: initialized(player))
    first = player.live.sessions[0]
    sent = recorded_sends(first)
    player.reverse()
    player.previous()
    assert not player.playing_reversed_slide and player.current_slide_index == 0
    assert player.live.sessions[0] is first and not sent
    player.presentation_configs.append(player.current_presentation_config.model_copy(deep=True))
    player.current_slide_index = 2
    player.load_current_slide()
    second = player.live.sessions[0]
    player.next()
    assert player.current_presentation_index == 1
    assert player.live.sessions[0] is not second
    player.current_slide_index = 2
    player.load_current_slide()
    last = player.live.sessions[0]
    player.next()
    assert player.live.sessions[0] is last and player.current_slide_index == 2
