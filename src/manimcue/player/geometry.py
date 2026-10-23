"""Geometria logiczna: kadr, kontener i przycięcie, bez zależności od DPI."""

from itertools import pairwise


def fit(aspect: float, container: tuple) -> tuple:
    """Wyśrodkuj obraz o zadanych proporcjach wewnątrz kontenera."""
    x, y, width, height = container
    if width <= 0 or height <= 0 or aspect <= 0:
        return x, y, 0.0, 0.0
    fitted_width = min(width, height * aspect)
    fitted_height = fitted_width / aspect
    return (
        x + (width - fitted_width) / 2,
        y + (height - fitted_height) / 2,
        fitted_width,
        fitted_height,
    )


def layer_box(frame: tuple, rect: tuple) -> tuple:
    """Przelicz ułamki kadru na logiczne współrzędne kontenera."""
    x, y, width, height = frame
    rx, ry, rw, rh = rect
    return x + rx * width, y + ry * height, rw * width, rh * height


def clip(box: tuple, frame: tuple) -> tuple:
    """Przetnij kontener z kadrem; pusty wynik ma zerowy rozmiar."""
    x, y, width, height = box
    fx, fy, fw, fh = frame
    left, top = max(x, fx), max(y, fy)
    return (
        left,
        top,
        max(0.0, min(x + width, fx + fw) - left),
        max(0.0, min(y + height, fy + fh) - top),
    )


def rect_at(media: dict, now: float) -> tuple:
    """Liniowa interpolacja D30; poza keyframes zachowaj skrajny prostokąt."""
    frames = media.get("keyframes", [])
    if not frames:
        return tuple(media.get("rect", (0, 0, 1, 1)))
    if now <= frames[0]["t"]:
        return tuple(frames[0]["rect"])
    for left, right in pairwise(frames):
        if now <= right["t"]:
            ratio = (now - left["t"]) / (right["t"] - left["t"])
            return tuple(a + ratio * (b - a) for a, b in zip(left["rect"], right["rect"]))
    return tuple(frames[-1]["rect"])


def hit_test(commands: list, point: tuple):
    """Najwyższy kontener blokuje niższe także na przezroczystych marginesach."""
    px, py = point
    for command in reversed(commands):
        if "container" not in command:
            continue
        x, y, w, h = clip(command["container"], command["clip"])
        if x <= px < x + w and y <= py < y + h:
            return command["source"]
    return None
