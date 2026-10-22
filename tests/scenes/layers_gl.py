"""Deck z warstwą live dla manimgl (F3) — ten sam kontrakt co `layers_ce.py`.

Używane przez `tests/test_layers.py`, nie przez użytkownika.
"""

from pathlib import Path

from manimlib import LEFT, RED, ShowCreation, Square

from manimcue.slides import LiveLayer
from manimcue.slides.slide.manimlib import Slide

LIVE_FILE = Path(__file__).with_name("live_gl.py")
LAYER_RECT = (0.5, 0.0, 0.5, 0.5)


class LayersGL(Slide):
    """Slajd 1 bez warstwy, slajd 2 z warstwą `LiveGLCorners`. F3."""

    def construct(self) -> None:
        square = Square(color=RED)
        self.next_slide(notes="bez warstwy")
        self.play(ShowCreation(square))
        self.next_slide(
            notes="z warstwą",
            layers=[LiveLayer(scene_file=LIVE_FILE, scene_name="LiveGLCorners", rect=LAYER_RECT)],
        )
        self.play(square.animate.shift(LEFT))
