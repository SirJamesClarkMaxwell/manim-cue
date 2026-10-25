"""Testy formatu, trwałości i wspólnego wejścia obu playerów D49."""

import builtins
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from manimcue.player import notes_overlay as notes


def document(count=2, sections=None):
    return notes.Overlay(count, sections or [])


@pytest.mark.parametrize("text", ["", "tekst", "tekst\n", "tekst\n\n", "ąć\t\n  koniec"])
def test_round_trip(text):
    overlay = document(1, [notes.Section(1, notes.notes_hash(""), text)])
    serialized = notes.serialize(overlay)
    assert serialized.endswith(text + "\n")
    assert notes.parse(serialized).sections[0].text == text
    assert notes.serialize(notes.parse(serialized)) == serialized


def test_parse_errors_and_duplicate():
    text = notes.serialize(
        document(
            2,
            [
                notes.Section(1, "12345678", "a"),
                notes.Section(1, "12345678", "b"),
                notes.Section(2, "12345678", "c"),
            ],
        )
    )
    overlay = notes.parse(text + "<!-- manim-cue broken -->\n")
    assert overlay.read_only
    effective, warnings = notes.apply(["x", "y"], overlay)
    assert effective[0] == "x"
    assert effective[1].startswith("c")
    assert len(warnings) >= 3
    with pytest.raises(ValueError):
        notes.update(overlay, ["x", "y"], {1: "z"})


@pytest.mark.parametrize("header", ["", "<!-- manim-cue notes slides=1 -->\n"])
def test_suspension_and_acknowledge(header):
    overlay = notes.parse(header + "<!-- manim-cue slide 1 base=12345678 -->\na\n")
    assert notes.apply(["", ""], overlay)[0] == ["", ""]
    updated = notes.update(overlay, ["", ""], {}, acknowledge=True)
    assert updated.count == 2
    assert updated.sections == overlay.sections
    assert notes.apply(["", ""], updated)[0] == ["a", ""]


def test_out_of_range_literal_and_normalization():
    raw = "<!-- manim-cue slide 9 base=ABCDEF12 -->\n  poza\n\n"
    overlay = notes.parse("<!-- manim-cue notes slides=2 -->\r\n" + raw.replace("\n", "\r\n"))
    updated = notes.update(overlay, ["a\r\nb", "c"], {1: "a\nb"})
    assert notes.serialize(updated).endswith(raw)
    assert notes.notes_hash("a\r\nb\rc") == notes.notes_hash("a\nb\nc")
    assert len(updated.sections) == 1
    with pytest.raises(ValueError):
        notes.update(updated, ["a", "b"], {1: "<!-- manim-cue slide 2 base=12345678 -->"})


def test_conflict_empty_and_remove():
    overlay = document(1, [notes.Section(1, "12345678", "")])
    assert notes.apply(["render"], overlay)[0] == [""]
    assert notes.apply(["render"], overlay)[1]
    assert notes.update(overlay, ["render"], {1: "render"}).sections == []


def test_bom_utf8_and_atomic_failure(tmp_path, monkeypatch):
    path = tmp_path / "Demo.notes.md"
    path.write_bytes(b"\xef\xbb\xbf" + notes.serialize(document(1)).encode())
    notes.save_overlay(path, [""], {1: "nowe"})
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
    previous = path.read_bytes()
    previous_files = set(tmp_path.iterdir())
    buffers = notes.DirtyBuffers()
    buffers.set(path, 1, "zmiana")
    with monkeypatch.context() as context:
        context.setattr(notes.os, "replace", lambda *args: (_ for _ in ()).throw(PermissionError()))
        with pytest.raises(PermissionError):
            buffers.flush(path, [""])
    assert path.read_bytes() == previous
    assert set(tmp_path.iterdir()) == previous_files
    assert buffers.pending(path) == {1: "zmiana"}
    buffers.flush(path, [""])
    assert not buffers.pending(path)
    path.write_bytes(b"\xff")
    assert notes.read_overlay(path).read_only
    with pytest.raises(ValueError):
        notes.save_overlay(path, [""], {1: "utrata"})
    assert path.read_bytes() == b"\xff"


def test_read_modify_write(tmp_path):
    path = tmp_path / "Demo.notes.md"
    notes.save_overlay(path, ["a", "b"], {1: "pierwsza"})
    buffers = notes.DirtyBuffers()
    buffers.set(path, 1, "moja")
    notes.save_overlay(path, ["a", "b"], {2: "zewnętrzna"})
    buffers.flush(path, ["a", "b"])
    assert notes.apply(["a", "b"], notes.read_overlay(path))[0] == ["moja", "zewnętrzna"]
    buffers.set(path, 1, "bufor")
    path.write_text("uszkodzony", encoding="utf-8")
    with pytest.raises(ValueError):
        buffers.flush(path, ["a", "b"])
    assert buffers.pending(path) == {1: "bufor"}


def test_rescue_buffers_collision_and_fallback(tmp_path, monkeypatch):
    path = tmp_path / "Demo.notes.md"
    buffers = notes.DirtyBuffers()
    buffers.set(path, 1, "edycja A")
    with (
        patch.object(notes, "save_overlay", side_effect=PermissionError),
        pytest.raises(PermissionError),
    ):
        buffers.flush(path, ["a", "b"])
    buffers.set(path.parent / "." / path.name, 2, "edycja B")
    target, text = buffers.rescue(path, ["a", "b"])
    assert notes.apply(["a", "b"], notes.parse(text))[0] == ["edycja A", "edycja B"]
    assert not buffers.buffers
    assert str(notes.os.getpid()) in target.name
    now = notes.datetime.now()
    with patch.object(notes, "datetime") as clock:
        clock.now.return_value = now
        first, _ = notes.rescue(path, [""], {1: "a"})
        second, _ = notes.rescue(path, [""], {1: "b"})
        assert first != second
        assert "a" in first.read_text(encoding="utf-8")
    fallback = tmp_path / "fallback"
    fallback.mkdir()
    monkeypatch.setattr(notes.tempfile, "gettempdir", lambda: str(fallback))
    real_open = builtins.open

    def denied_deck(file, *args, **kwargs):
        if Path(file).parent == tmp_path:
            raise PermissionError()
        return real_open(file, *args, **kwargs)

    with patch("builtins.open", side_effect=denied_deck):
        rescued, _ = notes.rescue(path, [""], {1: "ratunek"})
        assert rescued.parent == fallback
    with patch("builtins.open", side_effect=PermissionError):
        buffers.set(path, 1, "ostatnia")
        rescued, text = buffers.rescue(path, [""])
        assert rescued is None and "ostatnia" in text
        assert buffers.pending(path)


@pytest.mark.parametrize("dedent", [False, True])
def test_present_configs_and_manifest(tmp_path, dedent):
    from manimcue.player.manifest import model_to_manifest
    from manimcue.slides.present import get_scenes_presentation_config

    image = tmp_path / "image.png"
    image.touch()
    config = {
        "slides": [
            {
                "file": str(image),
                "rev_file": str(image),
                "notes": "  render\n    dalej",
                "dedent_notes": dedent,
            }
        ]
    }
    (tmp_path / "Demo.json").write_text(json.dumps(config), encoding="utf-8")
    configs = get_scenes_presentation_config(["Demo", "Demo"], tmp_path)
    rendered = configs[0].slides[0].notes
    path = tmp_path / "Demo.notes.md"
    notes.save_overlay(path, [rendered], {1: "  nakładka\n    bez dedentu"})
    overlay = notes.read_overlay(path)
    assert overlay.sections[0].base == notes.notes_hash(rendered)
    for config in configs:
        effective, warnings = notes.apply([config.slides[0].notes], overlay)
        assert not warnings
        object.__setattr__(config, "_notes_file", notes.canonical_path(path))
        object.__setattr__(config, "_rendered_notes", [rendered])
        object.__setattr__(config.slides[0], "notes", effective[0])
    manifest = model_to_manifest(configs)
    assert manifest["presentations"][0] == manifest["presentations"][1]
    slide = manifest["presentations"][0]["slides"][0]
    assert slide["rendered_notes"] == rendered
    assert slide["notes"] == "  nakładka\n    bez dedentu"


@pytest.mark.parametrize("player", ["qt", "imgui"])
@pytest.mark.parametrize("count", [1, 2, None])
def test_present_both_players(tmp_path, monkeypatch, player, count):
    from unittest.mock import MagicMock

    from click.testing import CliRunner
    from PIL import Image

    import manimcue.media
    import manimcue.player.desktop
    import manimcue.slides.present.player as qt_player
    from manimcue.slides import qt_utils
    from manimcue.slides.present import present

    image = tmp_path / "image.png"
    Image.new("RGB", (2, 2)).save(image)
    (tmp_path / "Demo.json").write_text(
        json.dumps(
            {
                "slides": [
                    {
                        "file": str(image),
                        "rev_file": str(image),
                        "notes": "  render",
                        "dedent_notes": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    path = tmp_path / "Demo.notes.md"
    path.write_text(
        notes.serialize(
            document(count, [notes.Section(1, notes.notes_hash("  render"), "  edycja")])
        ),
        encoding="utf-8",
    )
    seen = []
    monkeypatch.setattr(manimcue.media, "check_presentation_durations", lambda *args: None)
    monkeypatch.setattr(
        manimcue.player.desktop, "run_desktop", lambda manifest, options: seen.append(manifest) or 0
    )
    app = MagicMock()
    app.screens.return_value = []
    app.exec.return_value = 0
    monkeypatch.setattr(qt_utils, "qapp", lambda: app)
    monkeypatch.setattr(
        qt_player, "Player", lambda config, configs, **kwargs: seen.append(configs) or MagicMock()
    )
    monkeypatch.setattr("signal.signal", lambda *args: None)
    result = CliRunner().invoke(
        present, ["--folder", str(tmp_path), "--player", player, "Demo", "Demo"]
    )
    assert result.exit_code == 0, (result.output, result.exception)
    expected = "  edycja" if count == 1 else "  render"
    if player == "imgui":
        presentations = seen[0]["presentations"]
        assert (
            presentations[0]["notes_file"]
            == presentations[1]["notes_file"]
            == notes.canonical_path(path)
        )
        assert presentations[0]["slides"][0]["rendered_notes"] == "  render"
        assert presentations[0]["slides"][0]["notes"] == expected
    else:
        assert [config.slides[0].notes for config in seen[0]] == [expected, expected]


@pytest.mark.parametrize(
    "marker",
    [
        "<!-- manim-cue slide x base=12345678 -->",
        "<!-- manim-cue slide 0 base=12345678 -->",
        "<!-- manim-cue slide 1 base=short -->",
        "<!-- manim-cue other -->",
    ],
)
def test_invalid_marker(marker):
    overlay = notes.parse("<!-- manim-cue notes slides=1 -->\n" + marker + "\n")
    assert overlay.read_only and overlay.errors


def test_acknowledge_changes_only_header(tmp_path):
    path = tmp_path / "Demo.notes.md"
    body = "<!-- manim-cue slide 5 base=ABCDEF12 -->\npoza bez terminatora"
    path.write_bytes(("<!-- manim-cue notes slides=1 -->\n" + body).encode())
    notes.save_overlay(path, [""] * 5, {}, acknowledge=True)
    # Terminator dopisany do ostatniej sekcji; treść po odczycie bez zmian.
    assert path.read_bytes().decode() == "<!-- manim-cue notes slides=5 -->\n" + body + "\n"
    assert notes.read_overlay(path).sections[0].text == "poza bez terminatora"


def test_rescue_gettempdir_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(notes.tempfile, "gettempdir", lambda: (_ for _ in ()).throw(OSError()))
    with patch("builtins.open", side_effect=PermissionError):
        target, text = notes.rescue(tmp_path / "Demo.notes.md", [""], {1: "zachowane"})
    assert target is None and "zachowane" in text


def test_raw_last_section_without_newline():
    # Ręcznie edytowany plik bez końcowego \n nie może skleić sekcji przy zapisie.
    overlay = notes.parse(
        "<!-- manim-cue notes slides=5 -->\n<!-- manim-cue slide 3 base=12345678 -->\ntekst"
    )
    updated = notes.update(overlay, ["a", "b", "c", "d", "e"], {5: "nowe"})
    again = notes.parse(notes.serialize(updated))
    assert [(section.number, section.text) for section in again.sections] == [
        (3, "tekst"),
        (5, "nowe"),
    ]
    assert not again.errors
