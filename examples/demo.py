"""Demo deck fazy 1: fork ma działać jak manim-slides, w obu silnikach.

    uv run manim-cue render examples/demo.py Demo        # Manim CE
    uv run manim-cue render --GL examples/demo.py Demo   # manimgl
    uv run manim-cue present Demo

Co sprawdzić w oknie (kryterium 5 fazy 1): notatki w oknie Info, podgląd następnego slajdu,
slajd 2 zapętlony do naciśnięcia `→`, cofanie (`←`).

Faza 3 (kryterium 8): slajd 3 ma warstwę live `examples/live_panel.py` w prawym górnym rogu —
w F3 widać jej miniaturę (pierwszą klatkę sceny), w oknie głównym, w Info i w podglądzie.
"""

from pathlib import Path

from manimcue.slides import LiveLayer, Slide
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


PANEL = LiveLayer(
    scene_file=Path(__file__).with_name("live_panel.py"),
    scene_name="Panel",
    rect=(0.6, 0.05, 0.35, 0.35),
)


class Demo(Slide):
    """Trzy slajdy: wzrost, pętla, obrót; na trzecim warstwa live."""

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

        self.next_slide(
            notes="**3/3** — kropka wraca do środka, obrót kwadratu. W rogu warstwa live.",
            layers=[PANEL],
        )
        self.play(dot.animate.move_to(ORIGIN))
        self.remove(dot)
        self.add(square)
        self.play(Rotate(square, PI / 2))
