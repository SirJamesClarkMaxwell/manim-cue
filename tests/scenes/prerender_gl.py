"""Sceny prerender dla manimgl (F1): dwa slajdy, notatki i klip na każdy.

Używane przez `tests/test_scene_corpus.py`, nie przez użytkownika.
"""

from manimlib import PI, RED, Rotate, ShowCreation, Square

from manimcue.slides.slide.manimlib import Slide


class PrerenderGLTwoSlides(Slide):
    """Slajd 1: pojawienie się czerwonego kwadratu. Slajd 2: obrót. F1."""

    def construct(self) -> None:
        square = Square(color=RED)
        self.next_slide(notes="slide 1")
        self.play(ShowCreation(square))
        self.next_slide(notes="slide 2")
        self.play(Rotate(square, PI / 2))
