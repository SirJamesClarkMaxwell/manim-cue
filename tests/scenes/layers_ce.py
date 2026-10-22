"""Decki z warstwą live dla Manim CE (F3): klip bazowy plus scena GL w prawym górnym rogu.

Używane przez `tests/test_layers.py`, nie przez użytkownika.
"""

from pathlib import Path

from manim import LEFT, RED, Create, Square

from manimcue.slides import LiveLayer
from manimcue.slides.slide.manim import Slide

LIVE_FILE = Path(__file__).with_name("live_gl.py")
LAYER_RECT = (0.5, 0.0, 0.5, 0.5)


class LayersCE(Slide):
    """Slajd 1 bez warstwy, slajd 2 z warstwą `LiveGLCorners`. F3."""

    def construct(self) -> None:
        square = Square(color=RED)
        self.next_slide(notes="bez warstwy")
        self.play(Create(square))
        self.next_slide(
            notes="z warstwą",
            layers=[LiveLayer(scene_file=LIVE_FILE, scene_name="LiveGLCorners", rect=LAYER_RECT)],
        )
        self.play(square.animate.shift(LEFT))


class LayersCEBuildRaises(Slide):
    """Negatywna: scena warstwy pada w `build_objects` — render ma paść z treścią błędu. F3."""

    def construct(self) -> None:
        self.next_slide(
            layers=[LiveLayer(scene_file=LIVE_FILE, scene_name="LiveGLBuildRaises")],
        )
        self.play(Create(Square()))
