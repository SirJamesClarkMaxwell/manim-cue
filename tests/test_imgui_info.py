"""Info: wspólny snapshot, niezależny podgląd i brak dekoderów po ukryciu."""

from types import SimpleNamespace

from manimcue.player.app import App
from manimcue.player.info import preview_target, state_text
from manimcue.player.live import LiveController


class FakeSource:
    def __init__(self):
        self.status = "ready"
        self.closed = False
        self.plays = []

    def prepare(self, entry_id, media):
        self.entry_id, self.media = entry_id, media

    def poll(self, now, target, budget_ms):
        return {
            "status": "ready",
            "frame_id": 1,
            "width": 1,
            "height": 1,
            "rgba": bytes(4),
            "pts": now % 1,
        }

    def play(self, now):
        self.plays.append(now)

    def pause(self):
        pass

    def request_close(self):
        self.closed = True

    def poll_closed(self, now):
        return self.closed


def manifest():
    return {
        "version": 1,
        "resolution": [100, 100],
        "presentations": [
            {"slides": [{"kind": "image", "file": "first", "notes": "**notes**"}]},
            {
                "resolution": [200, 100],
                "slides": [
                    {
                        "kind": "image",
                        "file": "next",
                        "layers": [
                            {
                                "kind": "image",
                                "file": "clip",
                                "keyframes": [
                                    {"t": 0, "rect": [0, 0, 0.5, 1]},
                                    {"t": 1, "rect": [0.5, 0, 0.5, 1]},
                                ],
                            }
                        ],
                    }
                ],
            },
        ],
    }


def make_app(**options):
    return App(
        manifest(),
        options,
        FakeSource,
        lambda update: SimpleNamespace(texture=1, close=lambda: None),
        LiveController(),
    )


def test_preview_target_resolution_normal_and_end():
    target = preview_target(manifest(), [0, 0])
    assert target["resolution"] == [200, 100] and target["index"] == [1, 0]
    assert preview_target(manifest(), [1, 0]) is None
    target["layers"].clear()
    assert manifest()["presentations"][1]["slides"][0]["layers"]


def test_hidden_preview_no_decoders_and_independent_motion():
    app = make_app(start_paused=True, show_info=False)
    assert not app.preview_sources
    app.set_info_visible(True)
    assert len(app.preview_sources) == 2
    now = app.started_at + 0.5
    state = app.tick(now)
    assert state["paused"] and state["notes"] == "**notes**"
    assert all(source.plays for source in app.preview_sources.values())
    assert not any(source.plays for source in app.sources.values())
    sources = list(app.preview_sources.values())
    app.set_info_visible(False)
    assert all(source.closed for source in sources) and not app.preview_sources


def test_info_and_s_snapshot_retains_degradation_and_elapsed():
    app = make_app()
    app.errors.append("restore nieznany wynik")
    state = app.tick(app.started_at + 0.5)
    assert state["elapsed"] == 0.5
    assert "restore nieznany wynik" in state_text(state)
    app.dispatch({"type": "pause"}, app.started_at + 1)
    assert app.presenter_snapshot(app.started_at + 4)["elapsed"] == 4


def test_live_input_media_order():
    app = make_app(show_info=False)
    observed = []
    poll = app.live.poll
    app.live.poll = lambda now: observed.append("live") or poll(now)
    source = app.sources["base"]
    original = source.poll
    source.poll = lambda *args: observed.append("media") or original(*args)
    app.tick(app.started_at + 0.1, lambda: observed.append("input"))
    assert observed == ["live", "input", "media"]
