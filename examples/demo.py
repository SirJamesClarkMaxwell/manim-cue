"""Demo deck fazy 1: fork ma działać jak manim-slides, w obu silnikach.

    uv run manim-cue render examples/demo.py Demo        # Manim CE
    uv run manim-cue render --GL examples/demo.py Demo   # manimgl
    uv run manim-cue present Demo

Co sprawdzić w oknie (kryterium 5 fazy 1): notatki w oknie Info, podgląd następnego slajdu,
slajd 2 zapętlony do naciśnięcia `→`, cofanie (`←`).

Faza 3/4: slajd 3 ma warstwę live `Panel` w prawym górnym rogu, slajd 4 — scenę 3D `Panel3D`.
Przed startem procesu widać miniaturę (pierwszą klatkę sceny), potem obraz live. Klik w warstwę
daje jej strzałki (żółta obwódka), Esc oddaje je slajdom. Na `Panel3D` mysz obraca kamerę.
"""

from pathlib import Path

from manimcue.slides import LiveLayer, Slide
from manimcue.slides.slide import MANIM

if MANIM:
    from manim import (
        BLUE,
        DL,
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
        DL,
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


PANEL_3D = LiveLayer(
    scene_file=Path(__file__).with_name("live_panel.py"),
    scene_name="Panel3D",
    rect=(0.1, 0.1, 0.8, 0.8),
)


class Demo(Slide):
    """Cztery slajdy: wzrost, pętla, obrót z panelem live, scena 3D."""

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

        self.next_slide(
            notes="**4/4** — scena 3D live: klik, potem przeciąganie obraca kamerę, Shift "
            "przesuwa, kółko przybliża, dwuklik wraca; strzałki: spin, lift. Esc — slajdy.",
            layers=[PANEL_3D],
        )
        self.play(square.animate.scale(0.5).to_corner(DL))
