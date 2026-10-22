"""Klatki gotowego klipu po czasie (F6a, D32) — bez Manima i Qt, wspólne dla CE i manimgl.

Dekodowanie `av` sekwencyjne; cofnięcie czasu otwiera plik od nowa. W pamięci tylko bieżąca
klatka (1080p RGBA to ~8 MB na klatkę).
"""

import math
from pathlib import Path

import av
import numpy as np

from manimcue.media import video_info


class FrameSource:
    """Klatka klipu dla czasu ``t`` (sekundy materiału, bez szybkości odtwarzania)."""

    def __init__(self, file: Path | str, loop: bool = False) -> None:
        self.file = Path(file).resolve()
        self.loop = loop
        self.duration, self.fps = video_info(self.file)
        with av.open(str(self.file)) as container:
            frames = container.streams.video[0].frames
        # Liczba klatek z kontenera, gdy jest; inaczej z długości i fps (metadane bez dekodowania).
        self.count = frames or max(1, round(self.duration * self.fps))
        stat = self.file.stat()
        self.key = f"{self.file}|{stat.st_size}|{stat.st_mtime_ns}"
        """Tożsamość źródła: zmienia się z nowym renderem (hash cache CE, D32)."""
        self._container = None
        self._frames = None
        self.index = -1
        self.array: np.ndarray | None = None

    def index_at(self, t: float) -> int:
        """Indeks klatki pokazywanej w chwili ``t``; ε chroni granice przed błędem float."""
        index = math.floor(t * self.fps + 1e-6)
        if self.loop:
            return index % self.count
        return min(max(index, 0), self.count - 1)

    def rgba(self, t: float) -> np.ndarray:
        """Klatka RGBA uint8 (wiersze od góry) dla chwili ``t``."""
        target = self.index_at(t)
        if self.array is not None and target == self.index:
            return self.array
        if self._frames is None or target < self.index:
            # ponytail: cofnięcie dekoduje od początku pliku — przy długich klipach i częstym
            # seek wstecz przejść na container.seek do klatki kluczowej i dekodować dalej.
            self._reopen()
        frame = None
        while self.index < target:
            try:
                frame = next(self._frames)
            except StopIteration:
                break  # metadane obiecały więcej klatek — zostaje ostatnia zdekodowana
            self.index += 1
        if frame is not None:
            self.array = frame.to_ndarray(format="rgba")
        return self.array

    def _reopen(self) -> None:
        self.close()
        self._container = av.open(str(self.file))
        self._frames = self._container.decode(video=0)
        self.index = -1
        self.array = None
        # Pierwsza klatka od razu: rgba(t) zawsze coś zwraca.
        self.array = next(self._frames).to_ndarray(format="rgba")
        self.index = 0

    def close(self) -> None:
        if self._container is not None:
            self._container.close()
        self._container = None
        self._frames = None

    def __deepcopy__(self, memo) -> "FrameSource":
        # Kopie mobjectu (cele `.animate`, `copy()`) dzielą dekoder — kontener av się nie kopiuje.
        return self
