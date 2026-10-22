"""Demo deck fazy 1: fork ma działać jak manim-slides, w obu silnikach.

    uv run manim-cue render examples/demo.py Demo        # Manim CE
    uv run manim-cue render --GL examples/demo.py Demo   # manimgl
    uv run manim-cue present Demo

Co sprawdzić w oknie (kryterium 5 fazy 1): notatki w oknie Info, podgląd następnego slajdu,
slajd 2 zapętlony do naciśnięcia `→`, cofanie (`←`).
"""

from manimcue.slides import Slide
from manimcue.slides.slide import MANIM

if MANIM:
    from manim import (
        BLUE,
        ORIGIN,
        PI,
        RED,
        Circle,
        Dot,
        GrowFromCenter,
        MoveAlongPath,
        Rotate,
        Square,
        linear,
    )
else:
    from manimlib import (
        BLUE,
        ORIGIN,
        PI,
        RED,
        Circle,
        Dot,
        GrowFromCenter,
        MoveAlongPath,
        Rotate,
        Square,
        linear,
    )


class Demo(Slide):
    """Trzy slajdy: wzrost, pętla, obrót."""

    def construct(self) -> None:
        circle = Circle(radius=2, color=BLUE)
        dot = Dot().move_to(circle.point_from_proportion(0))
        square = Square(side_length=1, color=RED)

        # Notatki należą do slajdu, który dane next_slide() otwiera.
        self.next_slide(notes="**1/3** — okrąg rośnie ze środka. Podgląd obok pokazuje slajd 2.")
        self.play(GrowFromCenter(circle))
        self.add(dot)

        self.next_slide(notes="**2/3** — pętla: kropka krąży, dopóki nie naciśniesz `→`.", loop=True)
        self.play(MoveAlongPath(dot, circle), run_time=2, rate_func=linear)

        self.next_slide(notes="**3/3** — kropka wraca do środka i zamienia się w obrót kwadratu.")
        self.play(dot.animate.move_to(ORIGIN))
        self.remove(dot)
        self.add(square)
        self.play(Rotate(square, PI / 2))
