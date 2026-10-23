"""Walidacja manifestu JSON bez modelu Pydantic i adapterów PC."""

import math
from copy import deepcopy


def _number(value, path, *, positive=False):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or (value <= 0 if positive else value < 0)
    ):
        raise ValueError(f"{path}: niepoprawna liczba {value!r}")


def _resolution(value, path):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{path}: wymagane [width, height]")
    for size in value:
        _number(size, path, positive=True)
        if not isinstance(size, int):
            raise TypeError(f"{path}: rozmiary muszą być całkowite")


def _media(media, path):
    if not isinstance(media, dict):
        raise TypeError(f"{path}: wymagany obiekt")
    if media.get("kind") not in ("video", "image", "gif", "live"):
        raise ValueError(f"{path}.kind: nieznany rodzaj")
    for field in ("duration", "rate", "reverse_rate"):
        if field in media:
            _number(media[field], f"{path}.{field}", positive=field != "duration")
    if "rect" in media:
        rect = media["rect"]
        if not isinstance(rect, list) or len(rect) != 4:
            raise ValueError(f"{path}.rect: wymagane [x, y, width, height]")
        for index, value in enumerate(rect):
            # Pozycja może wychodzić poza kadr, rozmiar nie może być ujemny.
            if index < 2:
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise ValueError(f"{path}.rect: niepoprawna pozycja")
            else:
                _number(value, f"{path}.rect", positive=True)
    layers = media.get("layers", [])
    if not isinstance(layers, list):
        raise TypeError(f"{path}.layers: wymagana lista")
    for index, layer in enumerate(layers):
        _media(layer, f"{path}.layers[{index}]")


def validate_manifest(data: dict) -> dict:
    """Sprawdź wersję, rozdzielczości i skończone czasy/rate; zwróć kopię danych."""
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("manifest.version: obsługiwana wersja to 1")
    _resolution(data.get("resolution"), "manifest.resolution")
    presentations = data.get("presentations")
    if not isinstance(presentations, list) or not presentations:
        raise ValueError("manifest.presentations: wymagana niepusta lista")
    for index, presentation in enumerate(presentations):
        path = f"manifest.presentations[{index}]"
        if not isinstance(presentation, dict):
            raise TypeError(f"{path}: wymagany obiekt")
        if "resolution" in presentation:
            _resolution(presentation["resolution"], f"{path}.resolution")
        slides = presentation.get("slides")
        if not isinstance(slides, list) or not slides:
            raise ValueError(f"{path}.slides: wymagana niepusta lista")
        for slide_index, slide in enumerate(slides):
            _media(slide, f"{path}.slides[{slide_index}]")
    return deepcopy(data)
