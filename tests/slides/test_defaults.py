from pathlib import Path

from manimcue.slides.defaults import CONFIG_PATH, FOLDER_PATH


def test_folder_path() -> None:
    assert FOLDER_PATH == Path("./slides")


def test_config_path() -> None:
    assert CONFIG_PATH == Path(".manim-slides.toml")
