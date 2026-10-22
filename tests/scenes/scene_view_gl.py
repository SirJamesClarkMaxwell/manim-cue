"""Gospodarz `SceneView` dla manimgl (F6a) — ta sama oś czasu co `scene_view_ce.py`.

Bez `wait()`: w slajdach manimgl (fork manim-slides, `subdivide_output`) każde `wait()` to osobny
plik częściowy, a slajdy kroją pliki po liczbie `play()` — przesunęłyby się (ostrzeżenie upstreamu
w walidatorze `PreSlideConfig`). Pauzy to `play()` innego, niewidocznego obiektu.
Używane przez `tests/test_scene_view.py`, nie przez użytkownika.
"""

import os

from manimlib import LEFT, RIGHT, Dot, FadeIn

from manimcue.scene_view import SceneView
from manimcue.slides.slide.manimlib import Slide


class ViewTimingGL(Slide):
    def construct(self) -> None:
        marker = Dot().set_opacity(0)
        self.add(marker)

        def hold(seconds: float) -> None:
            self.play(marker.animate.shift(0.01 * RIGHT), run_time=seconds)

        view = SceneView(self, os.environ["MANIMCUE_TEST_CLIP"], height=4, loop=True)
        self.play(FadeIn(view), run_time=0.5)
        hold(0.5)
        self.play(view.animate.shift(3 * RIGHT).scale(0.5), run_time=1)
        hold(1)
        view.pause()
        hold(0.5)
        self.next_slide()
        view.resume()
        self.play(view.animate.set_opacity(1), run_time=0.5)


class TwoViewsGL(Slide):
    """Dwa niezależne widoki jednego klipu: osobne tekstury mimo wspólnego pliku źródła."""

    def construct(self) -> None:
        clip = os.environ["MANIMCUE_TEST_CLIP"]
        left = SceneView(self, clip, height=2, loop=True).shift(3 * LEFT)
        right = SceneView(self, clip, height=2, loop=True).shift(3 * RIGHT).seek(1.0)
        marker = Dot().set_opacity(0)
        self.add(left, right, marker)
        self.play(marker.animate.shift(0.01 * RIGHT), run_time=0.5)
