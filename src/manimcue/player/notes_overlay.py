"""Nakładka notatek i ochrona niezapisanych buforów; wyłącznie biblioteka standardowa."""

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

HEADER = re.compile(r"<!-- manim-cue notes slides=(\d+) -->\n?")
MARKER = re.compile(r"<!-- manim-cue slide ([1-9]\d*) base=([0-9a-fA-F]{8}) -->\n?")


def normalize(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def notes_hash(text):
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:8]


@dataclass
class Section:
    number: int
    base: str
    text: str
    raw: str = ""


@dataclass
class Overlay:
    count: int | None = None
    sections: list[Section] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    read_only: bool = False


def parse(text):
    """Odczytaj sekcje bez obcinania białych znaków treści."""
    text = normalize(text.removeprefix("\ufeff"))
    parts = text.split("\n")
    lines = [part + "\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    result = Overlay()
    if lines and (match := HEADER.fullmatch(lines[0])):
        result.count = int(match[1])
        lines = lines[1:]
    current = []

    def finish():
        if current:
            match = MARKER.fullmatch(current[0])
            body = "".join(current[1:])
            result.sections.append(
                Section(
                    int(match[1]),
                    match[2],
                    body.removesuffix("\n"),
                    "".join(current),
                )
            )
            current.clear()

    for line in lines:
        if MARKER.fullmatch(line):
            finish()
            current.append(line)
        else:
            if line.startswith("<!-- manim-cue") or not current:
                result.errors.append(f"Niepoprawny wiersz: {line!r}")
            if current:
                current.append(line)
    finish()
    numbers = [section.number for section in result.sections]
    for number in sorted(set(numbers)):
        if numbers.count(number) > 1:
            result.errors.append(f"Duplikat slajdu {number}")
    result.read_only = bool(result.errors)
    return result


def serialize(overlay):
    """Zapisz LF i jeden terminator, zachowując surowe sekcje spoza zakresu."""
    header = (
        f"<!-- manim-cue notes slides={overlay.count} -->\n" if overlay.count is not None else ""
    )
    # Surowa sekcja z końca pliku bez \n dostaje terminator, inaczej skleiłaby się z następną.
    return header + "".join(
        (section.raw if section.raw.endswith("\n") else section.raw + "\n")
        if section.raw
        else f"<!-- manim-cue slide {section.number} base={section.base} -->\n{normalize(section.text)}\n"
        for section in sorted(overlay.sections, key=lambda section: section.number)
    )


def apply(rendered, overlay):
    """Zwróć efektywne notatki i ostrzeżenia; konflikt nie blokuje nakładki."""
    notes = [normalize(text) for text in rendered]
    warnings = list(overlay.errors)
    if overlay.count != len(notes):
        warnings.append(f"Nakładka wstrzymana: było {overlay.count} slajdów, jest {len(notes)}")
        return notes, warnings
    numbers = [section.number for section in overlay.sections]
    for section in overlay.sections:
        if section.number > len(notes) or numbers.count(section.number) != 1:
            continue
        index = section.number - 1
        if section.base.lower() != notes_hash(rendered[index]):
            warnings.append(f"Slajd {section.number}: notatki w kodzie zmienione po edycji")
        notes[index] = section.text
    return notes, warnings


def validate_text(text):
    if any(line.startswith("<!-- manim-cue") for line in normalize(text).splitlines()):
        raise ValueError("Znacznik manim-cue w treści notatki")


def update(overlay, rendered, dirty, *, acknowledge=False):
    """Podmień wyłącznie brudne sekcje albo świadomie zmień sam nagłówek."""
    if overlay.read_only:
        raise ValueError("Nakładka tylko do odczytu: " + "; ".join(overlay.errors))
    if overlay.count not in (None, len(rendered)) and not acknowledge:
        raise ValueError("Nakładka wstrzymana")
    if acknowledge:
        return Overlay(len(rendered), list(overlay.sections))
    sections = {section.number: section for section in overlay.sections}
    for number, text in dirty.items():
        if not 1 <= number <= len(rendered):
            raise ValueError("Slajd poza zakresem")
        text = normalize(text)
        validate_text(text)
        sections.pop(number, None)
        if text != normalize(rendered[number - 1]):
            sections[number] = Section(number, notes_hash(rendered[number - 1]), text)
    return Overlay(len(rendered), list(sections.values()))


def canonical_path(path):
    return os.path.normcase(str(Path(path).resolve()))


def read_overlay(path):
    try:
        return parse(Path(path).read_bytes().decode("utf-8-sig"))
    except FileNotFoundError:
        return Overlay()
    except UnicodeDecodeError as error:
        return Overlay(errors=[f"Błędny UTF-8: {error}"], read_only=True)


def atomic_write(path, text):
    """Zamknij plik przed replace; usuń temp także przy sharing violation."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=Path(path).parent, delete=False
        ) as stream:
            temporary = stream.name
            stream.write(normalize(text))
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def save_overlay(path, rendered, dirty, *, acknowledge=False):
    overlay = read_overlay(path)
    if Path(path).exists() and overlay.count is None and not acknowledge:
        raise ValueError("Nakładka wstrzymana: brak nagłówka")
    updated = update(overlay, rendered, dirty, acknowledge=acknowledge)
    atomic_write(path, serialize(updated))
    return updated


def rescue(path, rendered, dirty):
    """Zwróć ścieżkę ratunku albo pełną treść dla schowka i stderr w UI."""
    text = serialize(
        Overlay(
            len(rendered),
            [
                Section(number, notes_hash(rendered[number - 1]), normalize(value))
                for number, value in dirty.items()
            ],
        )
    )
    name = f"{Path(path).stem}.unsaved-{datetime.now():%Y%m%d-%H%M%S}-{os.getpid()}"
    directories = [Path(path).parent]
    try:
        directories.append(Path(tempfile.gettempdir()))
    except OSError:
        pass
    for directory in directories:
        for suffix in range(1000):
            target = directory / f"{name}{'-' + str(suffix) if suffix else ''}.md"
            try:
                with open(target, "x", encoding="utf-8", newline="\n") as stream:
                    stream.write(text)
                return target, text
            except FileExistsError:
                continue
            except OSError:
                break
    return None, text


class DirtyBuffers:
    """Magazyn należący do runtime, niezależny od życia widoku Info."""

    def __init__(self):
        self.buffers = {}

    def set(self, path, number, text):
        self.buffers[canonical_path(path), number] = text

    def pending(self, path):
        path = canonical_path(path)
        return {number: text for (key, number), text in self.buffers.items() if key == path}

    def flush(self, path, rendered):
        dirty = self.pending(path)
        if dirty:
            save_overlay(path, rendered, dirty)
            self._clear(path)

    def rescue(self, path, rendered):
        result = rescue(path, rendered, self.pending(path))
        if result[0] is not None:
            self._clear(path)
        return result

    def _clear(self, path):
        for key in list(self.buffers):
            if key[0] == canonical_path(path):
                del self.buffers[key]
