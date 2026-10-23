"""Macierz opcji wspólnego CLI i wyboru backendu."""

import json

import pytest
from click.testing import CliRunner
from PIL import Image

from manimcue.player.desktop import run_desktop as run_desktop_real
from manimcue.player.desktop import screen_options
from manimcue.slides.present import present


@pytest.fixture
def invoke(tmp_path, monkeypatch):
    from manimcue.player import desktop

    image = tmp_path / "image.png"
    Image.new("RGBA", (4, 4), "red").save(image)
    data = {
        "resolution": [100, 100],
        "slides": [{"file": str(image), "rev_file": str(image), "type": "image"}],
    }
    (tmp_path / "Scene.json").write_text(json.dumps(data), encoding="utf-8")
    seen = []
    monkeypatch.setattr(
        desktop, "run_desktop", lambda manifest, options: seen.append((manifest, options)) or 0
    )

    def run(arguments=(), input=None):
        result = CliRunner().invoke(
            present, ["--folder", str(tmp_path), "--player", "imgui", *arguments], input=input
        )
        assert result.exit_code == 0, (result.output, result.exception)
        return seen[-1]

    return run


def test_backend_default():
    player = next(param for param in present.params if param.name == "player")
    assert player.default == "qt" and set(player.type.choices) == {"qt", "imgui"}
    result = CliRunner().invoke(present, ["--help"])
    assert result.exit_code == 0 and "--player" in result.output


def test_selection_and_common_options(invoke, tmp_path):
    manifest, options = invoke(["Scene", "Scene", "--verbosity", "DEBUG"])
    assert len(manifest["presentations"]) == 2
    assert options["config"]["keys"]["NEXT"]["ids"] == [16777236]
    assert invoke([], input="1\n")[0]["presentations"]
    from manimcue.slides.config import Config

    config = Config()
    config.keys.NEXT.ids = {ord("T")}
    path = tmp_path / "custom.toml"
    config.to_file(path)
    assert invoke(["Scene", "--config", str(path)])[1]["config"]["keys"]["NEXT"]["ids"] == [
        ord("T")
    ]


def test_playback_flags(invoke):
    _, options = invoke(["Scene", "--start-paused", "-s"])
    assert options["start_paused"] and options["skip_all"] and options["exit_after_last_slide"]


@pytest.mark.parametrize("flag", ["-F", "--full-screen", "--fullscreen"])
def test_aliases(invoke, flag):
    _, options = invoke(["Scene", flag, "-H"])
    assert options["full_screen"] and options["hide_mouse"]


def test_geometry_and_rate(invoke):
    _, options = invoke(["Scene", "--aspect-ratio", "ignore", "--playback-rate", "2"])
    assert options["aspect_ratio"] == "ignore" and options["playback_rate"] == 2
    with pytest.raises(ValueError, match="playback_rate"):
        run_desktop_real({"presentations": [{"slides": [{}]}]}, {"playback_rate": float("nan")})


def test_start_indices(invoke):
    _, options = invoke(["Scene", "--sacn", "-1", "--sasn", "-1", "--sa", "0,0"])
    assert options["start_at_scene_number"] == 0 and options["start_at_slide_number"] == 0
    _, options = invoke(["Scene", "--start-at", ",-1"])
    assert options["start_at_slide_number"] == -1
    from manimcue.player.desktop import start_options

    manifest = {"presentations": [{"slides": [{}, {}]}, {"slides": [{}]}]}
    assert start_options(manifest, {"start_at_scene_number": -1})["start_at_scene_number"] == 1
    assert start_options(manifest, {"start_at_slide_number": -1})["start_at_slide_number"] == 1
    with pytest.raises(ValueError, match="slajdu"):
        start_options(manifest, {"start_at_slide_number": 2})


def test_screens():
    assert not screen_options({}, 1)["show_info"]
    assert screen_options({}, 2)["info_window_screen_number"] == 1
    assert screen_options({"hide_info_window": "never"}, 1)["show_info"]
    with pytest.warns(UserWarning, match="Ignoring"):
        assert not screen_options(
            {"hide_info_window": "always", "info_window_screen_number": 999}, 2
        )["show_info"]
    with pytest.raises(ValueError, match="Invalid screen"):
        screen_options({"screen_number": 2}, 2)


def test_desktop_gui_without_native_windows(monkeypatch):
    from types import SimpleNamespace

    from imgui_bundle import imgui, immapp
    from test_imgui_info import FakeSource, manifest

    from manimcue.player import desktop
    from manimcue.player.app import App

    class Windows:
        def __init__(self):
            self.monitors = [(0, 0, 1000, 800)]
            self.handles = {}
            self.close_requested = True

        def attach(self, name, handle, monitor):
            self.handles[name] = handle

    monkeypatch.setattr(desktop, "Windows", Windows)
    monkeypatch.setattr(
        desktop,
        "App",
        lambda manifest, options: App(
            manifest,
            options,
            FakeSource,
            lambda update: SimpleNamespace(texture=1, close=lambda: None),
        ),
    )

    def run(params, add_ons=None):
        assert add_ons.with_markdown
        context = imgui.create_context()
        try:
            io = imgui.get_io()
            io.display_size = (960, 540)
            io.delta_time = 1 / 60
            io.backend_flags |= imgui.BackendFlags_.renderer_has_textures
            io.set_ini_filename(None)
            params.callbacks.setup_imgui_config()
            params.callbacks.post_init()
            for _ in range(3):
                imgui.new_frame()
                params.callbacks.show_gui()
                imgui.render()
                for texture in imgui.get_platform_io().textures:
                    if texture.status == imgui.ImTextureStatus.want_create:
                        texture.set_tex_id(99)
                        texture.set_status(imgui.ImTextureStatus.ok)
                params.callbacks.after_swap()
            assert params.app_shall_exit
        finally:
            imgui.destroy_context(context)

    monkeypatch.setattr(immapp, "run", run)
    assert desktop.run_desktop(manifest(), {"hide_info_window": "never"}) == 0


def test_warning_once_per_audio_material(tmp_path):
    import wave

    from manimcue.player.desktop import warn_audio

    path = tmp_path / "audio.wav"
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(8000)
        file.writeframes(bytes(160))
    media = {"kind": "video", "file": str(path)}
    with pytest.warns(UserWarning, match="audio nie jest odtwarzane") as warnings:
        warn_audio({"presentations": [{"slides": [{**media, "layers": [media]}, media]}]})
    assert len(warnings) == 1


def test_reverse_freezes_clip_at_end_thumbnail_and_final_rect():
    from types import SimpleNamespace

    from test_imgui_info import FakeSource

    from manimcue.player.app import App

    manifest = {
        "resolution": [100, 100],
        "presentations": [
            {
                "slides": [
                    {
                        "kind": "video",
                        "file": "base",
                        "rev_file": "reverse",
                        "layers": [
                            {
                                "kind": "video",
                                "file": "clip",
                                "end_thumbnail": "last.png",
                                "keyframes": [
                                    {"t": 0, "rect": [0, 0, 0.5, 1]},
                                    {"t": 1, "rect": [0.5, 0, 0.5, 1]},
                                ],
                            }
                        ],
                    },
                    {"kind": "image", "file": "next"},
                ]
            }
        ],
    }
    app = App(
        manifest,
        {"start_at_slide_number": 1, "show_info": False},
        FakeSource,
        lambda update: SimpleNamespace(texture=1, close=lambda: None),
    )
    app.dispatch({"type": "reverse"}, app.started_at + 1)
    assert app.sources["base"].media["file"] == "reverse"
    assert app.sources["0"].media == {"kind": "image", "file": "last.png"}
    app.tick(app.started_at + 2)
    layer = next(command for command in app.composition if command.get("source") == "0")
    assert layer["container"] == (50, 0, 50, 100)
