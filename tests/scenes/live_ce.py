"""Korpus scen live (CE Cairo) do testów F2 i testów statycznych.

Każda scena to podklasa ``CorpusScene`` (czarne tło, puste presety). Sceny nie wołają
``update_frame()`` — publikacją klatki zajmuje się implementacja F2. Opis każdej sceny
jest w docstringu i w ``tests/scenes/MANIFEST.md``.
"""

import time
from typing import ClassVar

from manim import (
    ORIGIN,
    PI,
    RIGHT,
    UP,
    Circle,
    Dot,
    FadeIn,
    FadeOut,
    MathTex,
    Mobject,
    Rotate,
    Square,
    linear,
)

from manimcue.live_scene_ce import LiveSceneCE

FRAME_HEIGHT = 8.0
FRAME_WIDTH = 8.0 * 16 / 9

PURE_RED = "#FF0000"
PURE_GREEN = "#00FF00"
PURE_BLUE = "#0000FF"
PURE_WHITE = "#FFFFFF"

MOVE_START_X = -4.0
MOVE_END_X = 4.0
MOVE_RUN_TIME = 5.0

SLOW_BUILD_SECONDS = 3.0


def solid(mobject: Mobject, color: str) -> Mobject:
    """Pełne, nieobrysowane wypełnienie: kolor piksela jest wtedy jednoznaczny."""
    return mobject.set_fill(color, opacity=1).set_stroke(width=0)


class CorpusScene(LiveSceneCE):
    """Baza scen korpusu: czarne tło, presety ustawiają podklasy."""

    PRESETS: ClassVar[dict] = {}
    SEQUENCE: ClassVar[list] = []
    LOOPS: ClassVar[set] = set()


class LiveCEFirstFrame(CorpusScene):
    """Sprawdza pierwszą klatkę: rozmiar 960x540 i czerwony kwadrat w środku. F2."""

    def build_objects(self) -> None:
        self.square = solid(Square(side_length=2), PURE_RED)
        self.add(self.square)


class LiveCECorners(CorpusScene):
    """Sprawdza orientację: cztery narożne kwadraty w swoich kolorach. F2."""

    def build_objects(self) -> None:
        dx = FRAME_WIDTH / 2 - 1
        dy = FRAME_HEIGHT / 2 - 1
        corners = [
            (-dx, dy, PURE_RED),
            (dx, dy, PURE_GREEN),
            (-dx, -dy, PURE_BLUE),
            (dx, -dy, PURE_WHITE),
        ]
        for x, y, color in corners:
            self.add(solid(Square(side_length=1), color).shift(x * RIGHT + y * UP))


class LiveCEMoveFiveSeconds(CorpusScene):
    """Pięciosekundowy przejazd kwadratu: czas cue i klatki pośrednie. F2."""

    def build_objects(self) -> None:
        self.square = solid(Square(side_length=1), PURE_WHITE).shift(MOVE_START_X * RIGHT)
        self.add(self.square)

    def cue_move(self) -> None:
        """Przejazd z x = -4 do x = 4 w 5 s, liniowo."""
        self.play(
            self.square.animate.move_to(MOVE_END_X * RIGHT),
            run_time=MOVE_RUN_TIME,
            rate_func=linear,
        )

    PRESETS: ClassVar[dict] = {"move": cue_move}
    SEQUENCE: ClassVar[list] = ["move"]


class LiveCEInterruptTwoPlays(CorpusScene):
    """Dwa kolejne play w jednym cue; przerwanie ma dokończyć ostatnią klatkę. F2."""

    def build_objects(self) -> None:
        self.square = solid(Square(side_length=1), PURE_WHITE).shift(MOVE_START_X * RIGHT)
        self.add(self.square)

    def cue_two_step(self) -> None:
        """Najpierw do środka, potem do x = 4; każdy krok 3 s, liniowo."""
        self.play(self.square.animate.move_to(ORIGIN), run_time=3, rate_func=linear)
        self.play(self.square.animate.move_to(MOVE_END_X * RIGHT), run_time=3, rate_func=linear)

    PRESETS: ClassVar[dict] = {"two_step": cue_two_step}
    SEQUENCE: ClassVar[list] = ["two_step"]


class LiveCEAddRemoveBack(CorpusScene):
    """Wymiana mobjectów w cue i cofnięcie: czerwony wraca, niebieski znika. F2."""

    def build_objects(self) -> None:
        self.square = solid(Square(side_length=2), PURE_RED).shift(-3 * RIGHT)
        self.circle = solid(Circle(radius=1), PURE_BLUE).shift(3 * RIGHT)
        self.add(self.square)

    def cue_swap(self) -> None:
        """Znika kwadrat, pojawia się koło (koło nie jest na starcie w scenie)."""
        self.play(FadeOut(self.square), run_time=0.5)
        self.play(FadeIn(self.circle), run_time=0.5)

    PRESETS: ClassVar[dict] = {"swap": cue_swap}
    SEQUENCE: ClassVar[list] = ["swap"]


class LiveCEUpdaterWait(CorpusScene):
    """Updater przesuwa kropkę w czasie cue (1 j./s), `wait` nie zatrzymuje go. F2."""

    def build_objects(self) -> None:
        self.dot = solid(Dot(radius=0.2), PURE_WHITE).shift(-3 * RIGHT)
        self.dot.add_updater(lambda m, dt: m.shift(dt * RIGHT))
        self.add(self.dot)

    def cue_wait_two(self) -> None:
        """Czekanie 2 s; kropka ma przejechać 2 jednostki."""
        self.wait(2)

    PRESETS: ClassVar[dict] = {"wait_two": cue_wait_two}
    SEQUENCE: ClassVar[list] = ["wait_two"]


class LiveCEStaticWait(CorpusScene):
    """Samo `wait` w cue trwa dokładnie tyle, ile podano. F2."""

    def build_objects(self) -> None:
        self.square = solid(Square(side_length=1), PURE_WHITE)
        self.add(self.square)

    def cue_pause(self) -> None:
        """Pauza 1.5 s bez animacji."""
        self.wait(1.5)

    PRESETS: ClassVar[dict] = {"pause": cue_pause}
    SEQUENCE: ClassVar[list] = ["pause"]


class LiveCEIdleUpdater(CorpusScene):
    """Updater bez żadnego cue: między cue updatery są zamrożone. F2."""

    def build_objects(self) -> None:
        self.dot = solid(Dot(radius=0.2), PURE_WHITE).shift(-3 * RIGHT)
        self.dot.add_updater(lambda m, dt: m.shift(dt * RIGHT))
        self.add(self.dot)


class LiveCELoopBoundary(CorpusScene):
    """Pętla cue kończy się na granicy powtórzenia, nie w połowie obrotu. F2."""

    def build_objects(self) -> None:
        self.square = solid(Square(side_length=2), PURE_WHITE)
        self.add(self.square)

    def cue_spin(self) -> None:
        """Obrót o 90 stopni w 1 s; w pętli powtarzany do następnej komendy."""
        self.play(Rotate(self.square, PI / 2), run_time=1)

    PRESETS: ClassVar[dict] = {"spin": cue_spin}
    LOOPS: ClassVar[set] = {"spin"}
    SEQUENCE: ClassVar[list] = ["spin"]


class LiveCETex(CorpusScene):
    """Wzór TeX w środku; wymaga LaTeX (znacznik `tex`). F2."""

    def build_objects(self) -> None:
        self.formula = solid(MathTex(r"\int_0^1 x\,dx"), PURE_WHITE).scale(2)
        self.add(self.formula)


class LiveCESlowBuild(CorpusScene):
    """Wolne budowanie sceny: READY dopiero po `build_objects`, a poll nie blokuje. F2."""

    def build_objects(self) -> None:
        time.sleep(SLOW_BUILD_SECONDS)
        self.square = solid(Square(side_length=1), PURE_WHITE)
        self.add(self.square)


class LiveCECueRaises(CorpusScene):
    """Negatywna: wyjątek w cue ma dać ERROR z treścią, nie cichy zawis. F2."""

    def build_objects(self) -> None:
        self.square = solid(Square(side_length=1), PURE_WHITE)
        self.add(self.square)

    def cue_boom(self) -> None:
        """Zawsze rzuca wyjątek."""
        raise RuntimeError("boom from cue")

    PRESETS: ClassVar[dict] = {"boom": cue_boom}
    SEQUENCE: ClassVar[list] = ["boom"]


class LiveCEBuildRaises(CorpusScene):
    """Negatywna: wyjątek w budowaniu nie może dać READY. F2."""

    def build_objects(self) -> None:
        raise ValueError("boom from build")
