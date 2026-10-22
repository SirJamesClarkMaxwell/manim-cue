"""`SceneView` (F6a, D32): klatki gotowego renderu innej sceny jako mobject sceny-gospodarza.

    view = SceneView(self, slide_file("slides/Orbit.json", 0), height=3, loop=True)
    self.add(view)
    self.play(view.animate.scale(0.5).to_corner(UL), run_time=2)   # wideo gra w trakcie

Czas widoku to **absolutny czas gospodarza** (`scene.time`) od pierwszego odświeżenia, nie suma
`dt` updaterów — CE nie domyka przedziałów `play()` i gubiłby ~1/fps na każde wywołanie (runda 13,
p. 3). Stan odtwarzania i dekoder są wspólne dla widoku i jego kopii (cele `.animate`, `copy()`),
więc wszystkie pokazują tę samą klatkę, a dekoder nie skacze w tył i w przód.

Ograniczenia (runda 13): klipy CFR; `pause`/`resume`/`seek` to natychmiastowe komendy, nie
animacje (`view.animate.pause()` nie ma sensu); `become`/`Transform` między dwoma widokami nie
przenosi źródła — gwarantowane są geometria i krycie.
"""

import itertools
import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np

from manimcue.frame_source import FrameSource
from manimcue.slides.slide import MANIM


class Playback:
    """Czas widoku z zegara gospodarza: start przy pierwszym odczycie, pauza, seek."""

    def __init__(self, source: FrameSource, clock: Callable[[], float], rate: float) -> None:
        self.source = source
        self.clock = clock
        self.rate = rate
        self.started_at: float | None = None
        self.paused_at: float | None = None
        self.offset = 0.0

    def now(self) -> float:
        host = self.clock()
        if self.started_at is None:
            self.started_at = host
        if self.paused_at is not None:
            host = self.paused_at
        return self.offset + (host - self.started_at) * self.rate

    def pause(self) -> None:
        if self.paused_at is None:
            self.now()
            self.paused_at = self.clock()

    def resume(self) -> None:
        if self.paused_at is not None:
            self.started_at += self.clock() - self.paused_at
            self.paused_at = None

    def seek(self, t: float) -> None:
        self.now()
        self.offset = t
        self.started_at = self.paused_at if self.paused_at is not None else self.clock()


# Stan poza `__dict__` mobjectu: hash cache CE serializuje `__dict__` (z referencją do sceny
# i dekodera serializowałby wszystko). W mobjecie zostaje deterministyczny identyfikator —
# klucz źródła i numer widoku — więc hash zmienia się z nowym renderem źródła (runda 13, p. 5).
# ponytail: rejestr żyje do końca procesu renderu; zamykanie dodać, gdy render w jednym
# procesie zacznie tworzyć setki widoków.
_PLAYBACKS: dict[str, Playback] = {}
_NUMBERS = itertools.count()


def _register(scene, file: Path | str, loop: bool, rate: float) -> str:
    source = FrameSource(file, loop)
    playback_id = f"{source.key}#{next(_NUMBERS)}"
    _PLAYBACKS[playback_id] = Playback(source, lambda: scene.time, rate)
    return playback_id


class _ViewMixin:
    """Sterowanie wspólne dla obu silników."""

    playback_id: str

    @property
    def playback(self) -> Playback:
        return _PLAYBACKS[self.playback_id]

    def pause(self):
        self.playback.pause()
        return self

    def resume(self):
        self.playback.resume()
        return self

    def seek(self, t: float):
        """Czas materiału ``t`` (sekundy klipu, bez szybkości)."""
        self.playback.seek(t)
        return self

    def current_frame(self) -> np.ndarray:
        return self.playback.source.rgba(self.playback.now())


if MANIM:
    from manim import ImageMobject as _ImageMobject
    from manim.utils.bezier import interpolate

    class SceneView(_ViewMixin, _ImageMobject):
        """Widok klipu w Manim CE (Cairo): piksele z dekodera podmieniane co klatkę."""

        def __init__(
            self,
            scene,
            file: Path | str,
            height: float | None = None,
            loop: bool = False,
            rate: float = 1.0,
            **kwargs,
        ) -> None:
            self.playback_id = _register(scene, file, loop, rate)
            self.view_opacity = 1.0
            super().__init__(self.playback.source.rgba(0), **kwargs)
            if height is not None:
                self.scale_to_fit_height(height)
            # Updater czasowy: `wait()` nie zamraża klatki widoku (runda 13, p. 2).
            self.add_updater(lambda mobject, dt: None)

        def update(self, dt: float = 0, recursive: bool = True):
            # Klatka także przy updaterach zawieszonych przez `.animate` (runda 13, p. 1);
            # scena woła update po interpolacji animacji, więc te piksele trafiają do renderu.
            self.show_frame()
            return super().update(dt, recursive)

        def show_frame(self) -> None:
            frame = self.current_frame()
            if self.view_opacity >= 1:
                self.pixel_array = frame
            else:
                array = frame.copy()
                array[:, :, 3] = (array[:, :, 3] * self.view_opacity).astype(np.uint8)
                self.pixel_array = array

        def set_opacity(self, alpha: float):
            # Bez super(): ta zapisuje kanał alfa w miejscu, czyli w klatce z pamięci dekodera.
            self.view_opacity = alpha
            self.show_frame()
            return self

        def interpolate_color(self, mobject1, mobject2, alpha: float):
            # Piksele są z dekodera, nie mieszanką kopii — interpolowane jest tylko krycie.
            self.view_opacity = interpolate(mobject1.view_opacity, mobject2.view_opacity, alpha)
            self.fill_opacity = interpolate(mobject1.fill_opacity, mobject2.fill_opacity, alpha)
            self.stroke_opacity = interpolate(
                mobject1.stroke_opacity, mobject2.stroke_opacity, alpha
            )
            return self

else:
    from manimlib import ImageMobject as _ImageMobject
    from PIL import Image

    _FIRST_FRAMES = Path(tempfile.mkdtemp(prefix="manimcue-sceneview-"))

    class SceneView(_ViewMixin, _ImageMobject):
        """Widok klipu w manimgl: klatki zapisywane do tekstury obrazu.

        Każdy widok ma własny plik pierwszej klatki, bo `image_path_to_texture` ma `lru_cache`
        po ścieżce — dwa widoki jednego klipu dzieliłyby teksturę. Kopie widoku (cele
        animacji) dostają z cache tę samą teksturę, co jest pożądane (runda 13, p. 7).
        """

        def __init__(
            self,
            scene,
            file: Path | str,
            height: float = 4.0,
            loop: bool = False,
            rate: float = 1.0,
            **kwargs,
        ) -> None:
            self.playback_id = _register(scene, file, loop, rate)
            first = _FIRST_FRAMES / f"view_{self.playback_id.rsplit('#', 1)[1]}.png"
            Image.fromarray(self.playback.source.rgba(0)).save(first)
            self.pending: np.ndarray | None = None
            self.written: np.ndarray | None = None
            super().__init__(str(first), height=height, **kwargs)
            self.add_updater(lambda mobject, dt: None)

        def update(self, dt: float = 0, recurse: bool = True):
            # Jak w CE: klatka także przy zawieszonych updaterach.
            self.show_frame()
            return super().update(dt, recurse)

        def show_frame(self) -> None:
            frame = self.current_frame()
            if frame is self.written:
                return
            wrapper = self.shader_wrapper
            if wrapper is None or not wrapper.textures:
                # Wrapper powstaje leniwie przy pierwszym renderze, `copy()` go zeruje
                # (runda 13, p. 6) — klatka czeka na init_shader_wrapper.
                self.pending = frame
                return
            wrapper.textures[0].write(frame.tobytes())
            self.written = frame
            self.pending = None

        def init_shader_wrapper(self, ctx) -> None:
            super().init_shader_wrapper(ctx)
            self.written = None
            if self.pending is not None:
                self.show_frame()
