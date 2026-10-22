"""Mała scena do osadzenia jako warstwa w demo decku (F5): render `Orbit` wjeżdża na slajd 5.

uv run manim-cue render examples/orbit.py Orbit    # przed renderem examples/demo.py
"""

from manimcue.slides import Slide
from manimcue.slides.slide import MANIM

if MANIM:
    from manim import YELLOW, Circle, Dot, MoveAlongPath, linear
else:
    from manimlib import YELLOW, Circle, Dot, MoveAlongPath, linear


class Orbit(Slide):
    """Kropka okrąża koło w 2 s — klip zapętlony jako warstwa innego slajdu."""

    def construct(self) -> None:
        circle = Circle(radius=2.5, color=YELLOW)
        dot = Dot(color=YELLOW).scale(2).move_to(circle.point_from_proportion(0))
        self.add(circle, dot)
        self.play(MoveAlongPath(dot, circle), run_time=2, rate_func=linear)
