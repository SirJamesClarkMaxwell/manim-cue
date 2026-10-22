"""Demo deck fazy 1: fork ma działać jak manim-slides, w obu silnikach.

    uv run manim-cue render examples/demo.py Demo        # Manim CE
    uv run manim-cue render --GL examples/demo.py Demo   # manimgl
    uv run manim-cue present Demo

Co sprawdzić w oknie (kryterium 5 fazy 1): notatki w oknie Info, podgląd następnego slajdu,
slajd 2 zapętlony do naciśnięcia `→`, cofanie (`←`).

Faza 6a: slajd 6 osadza ten sam render w samej scenie (`SceneView`) — wideo gra, a animacja
gospodarza je przesuwa i skaluje; wynik to zwykły klip slajdu.

Faza 5: slajd 5 osadza render innej sceny (`examples/orbit.py`), który wjeżdża i rośnie obok
panelu live. Najpierw `uv run manim-cue render examples/orbit.py Orbit`.

Faza 3/4: slajd 3 ma warstwę live `Panel` w prawym górnym rogu, slajd 4 — scenę 3D `Panel3D`.
Przed startem procesu widać miniaturę (pierwszą klatkę sceny), potem obraz live. Klik w warstwę
daje jej strzałki (żółta obwódka), Esc oddaje je slajdom. Na `Panel3D` mysz obraca kamerę.
"""

from pathlib import Path

from manimcue.scene_view import SceneView
from manimcue.slides import ClipLayer, Keyframe, LiveLayer, Slide, slide_file
from manimcue.slides.slide import MANIM

if MANIM:
    from manim import (
        BLUE,
        DL,
        ORIGIN,
        PI,
        RED,
        UR,
        Circle,
        Dot,
        FadeIn,
        FadeOut,
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
        UR,
        Circle,
        Dot,
        FadeIn,
        FadeOut,
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

        self.next_slide(
            notes="**2/3** — pętla: kropka krąży, dopóki nie naciśniesz `→`.", loop=True
        )
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

        orbit_json = Path("slides/Orbit.json")
        if not orbit_json.exists():
            raise FileNotFoundError(
                "Slajd 5 osadza render sceny Orbit: najpierw "
                "`uv run manim-cue render examples/orbit.py Orbit`"
            )
        # Render innej sceny jako warstwa: wjeżdża zza prawej krawędzi i rośnie w 1,5 s.
        orbit = ClipLayer(
            file=slide_file(orbit_json, 0),
            loop=True,
            keyframes=[
                Keyframe(t=0, rect=(1.0, 0.3, 0.2, 0.2)),
                Keyframe(t=1.5, rect=(0.05, 0.1, 0.45, 0.45)),
            ],
        )
        self.next_slide(
            notes="**5/5** — render sceny Orbit wjeżdża i rośnie obok panelu live; "
            "spacja pauzuje bazę, klip i jego ruch; live działa dalej.",
            layers=[
                orbit,
                LiveLayer(
                    **PANEL.model_dump(exclude={"thumbnail"}) | {"rect": (0.55, 0.1, 0.4, 0.4)}
                ),
            ],
        )
        self.play(square.animate.move_to(ORIGIN).scale(2), run_time=1.5)

        self.next_slide(
            notes="**6/6** — `SceneView`: render Orbit gra wewnątrz sceny, a animacja "
            "gospodarza zjeżdża nim w róg i zmniejsza."
        )
        view = SceneView(self, slide_file(orbit_json, 0), height=4, loop=True)
        self.play(FadeOut(square), FadeIn(view), run_time=1)
        self.play(view.animate.scale(0.5).to_corner(UR), run_time=2)
        self.play(view.animate.to_corner(DL), run_time=2)

        self.remove(view)
        self.clear()
        marker = Square(side_length=1.5, color=BLUE).move_to((-4.7, 0, 0))
        self.add(marker)
        persistent = LiveLayer(
            scene_file=Path(__file__).with_name("live_three.py"),
            scene_name="ThreePanel",
            rect=(0.36, 0.15, 0.28, 0.6),
            session_id="three-panel",
            enter_cue="flip",
        )
        other = ClipLayer(file=slide_file(orbit_json, 0), rect=(0.69, 0.15, 0.28, 0.6))
        for number in (7, 8):
            self.next_slide(
                notes=f"**{number}/8** — jedno →: baza CE, trwały live i klip Orbit. "
                "Trzy stałe prostokąty i kamery; poruszają się obiekty. Esc oddaje strzałki. "
                "Spacja pauzuje bazę i klip; live działa dalej. S pokazuje stan na ekranie. "
                "Podgląd następnego slajdu pokazuje miniaturę live. "
                "Cofanie i replay nie cofają ani nie powtarzają cue live.",
                layers=[persistent.model_copy(), other.model_copy()],
            )
            self.play(Rotate(marker, PI / 2), run_time=2, rate_func=linear)
