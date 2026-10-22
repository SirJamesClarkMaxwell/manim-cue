"""Metadane i klatki plików warstw (F5, D29): miniatury z renderu i walidacja długości.

Bez Qt i Manima — używane w renderze (`_save_slides`) i raz przed prezentacją.
"""

import math
from functools import cache
from pathlib import Path

import av
from PIL import Image

from manimcue.slides.config import ClipLayer, PresentationConfig, SlideConfig, SlideType


def video_info(file: Path) -> tuple[float, float]:
    """(długość w s, fps) pierwszego strumienia wideo, z metadanych — bez dekodowania całości.

    Pamięć podręczna po ścieżce, rozmiarze i mtime: jeden render bywa bazą wielu slajdów.
    """
    path = Path(file).resolve()
    stat = path.stat()
    return _video_info(path, stat.st_size, stat.st_mtime_ns)


@cache
def _video_info(file: Path, size: int, mtime_ns: int) -> tuple[float, float]:
    with av.open(str(file)) as container:
        stream = container.streams.video[0]
        rate = stream.average_rate
        if stream.duration is None or stream.time_base is None or not rate:
            raise ValueError(f"Nieznana długość albo fps klipu {file}")
        return float(stream.duration * stream.time_base), float(rate)


def edge_frames(file: Path) -> tuple[Image.Image, Image.Image]:
    """Pierwsza i ostatnia klatka klipu. Dekoduje całość — tylko w renderze, z cache."""
    first = last = None
    with av.open(str(file)) as container:
        for frame in container.decode(video=0):
            last = frame
            if first is None:
                first = frame.to_image()
    if first is None:
        raise ValueError(f"Klip {file} nie ma klatek")
    return first, last.to_image()


def check_layer_durations(slide: SlideConfig, label: str = "") -> None:
    """Klip wideo bez `loop` nad bazą wideo trwa efektywnie tyle co baza (decyzja 4, D29).

    Tolerancja: większy z czasów klatki obu materiałów po szybkości. Zwolnione: `loop`, obrazy,
    GIF i baza statyczna (koniec slajdu ręczny).
    """
    clips = [layer for layer in slide.layers if isinstance(layer, ClipLayer)]
    checked = [clip for clip in clips if clip.is_video and not clip.loop]
    base_static = slide.type == SlideType.Image or Path(slide.file).suffix.lower() == ".gif"
    if not checked or base_static:
        return
    if not math.isfinite(slide.playback_rate) or slide.playback_rate <= 0:
        raise ValueError(f"{label}playback_rate bazy {slide.playback_rate} musi być dodatnie")
    try:
        base_duration, base_fps = video_info(slide.file)
    except (ValueError, OSError, av.error.FFmpegError) as e:
        raise ValueError(f"{label}klip bazowy: {e}") from e
    base = base_duration / slide.playback_rate
    for clip in checked:
        try:
            duration, fps = video_info(clip.file)
        except (ValueError, OSError, av.error.FFmpegError) as e:
            raise ValueError(f"{label}warstwa {clip.describe()}: {e}") from e
        effective = duration / clip.playback_rate
        tolerance = max(1 / (base_fps * slide.playback_rate), 1 / (fps * clip.playback_rate))
        if abs(effective - base) > tolerance + 1e-9:
            raise ValueError(
                f"{label}warstwa {clip.describe()} trwa {effective:.3f} s, a klip bazowy "
                f"{Path(slide.file).name} {base:.3f} s (tolerancja {tolerance:.3f} s); "
                "wyrównaj długości albo ustaw loop=True"
            )


def check_presentation_durations(config: PresentationConfig, name: str = "") -> None:
    """Walidacja długości wszystkich slajdów — raz przed prezentacją, po rozwiązaniu ścieżek."""
    for index, slide in enumerate(config.slides, start=1):
        check_layer_durations(slide, f"{name} slajd {index}: ".lstrip())
