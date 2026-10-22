"""Sceny prerender dla Manim CE (F1): dwa slajdy, notatki i klip na każdy.

Używane przez `tests/test_scene_corpus.py`, nie przez użytkownika.
"""

from manim import PI, RED, Create, Rotate, Square

from manimcue.slides.slide.manim import Slide


class PrerenderCETwoSlides(Slide):
    """Slajd 1: pojawienie się czerwonego kwadratu. Slajd 2: obrót. F1."""

    def construct(self) -> None:
        square = Square(color=RED)
        self.next_slide(notes="slide 1")
        self.play(Create(square))
        self.next_slide(notes="slide 2")
        self.play(Rotate(square, PI / 2))
