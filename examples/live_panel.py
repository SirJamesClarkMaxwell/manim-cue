"""Panele live do demo decku: presety fazy 0 (`Panel`) i scena 3D z nawigacją myszą (`Panel3D`).

Warstwa wskazuje podklasę z tego pliku, nie samo `LiveScene`: worker ładuje plik sceny pod własną
nazwą modułu, więc `live_scene.py` wczytany po ścieżce dałby drugą, obcą klasę `LiveScene`.
"""

from typing import ClassVar

from manimlib import BLUE, DEGREES, OUT, PI, Cube, Rotate, ThreeDAxes

from manimcue.live_scene import LiveScene


class Panel(LiveScene):
    """Kwadrat i koło z fazy 0; po kliknięciu warstwy strzałki: rotate → pulse → sweep."""


class Panel3D(LiveScene):
    """Sześcian na osiach 3D. Po kliknięciu: przeciąganie obraca kamerę, Shift+przeciąganie
    przesuwa, kółko przybliża, dwuklik wraca do widoku; strzałki: spin → lift."""

    def build_objects(self) -> None:
        self.cube = Cube(side_length=2, color=BLUE, opacity=0.8)
        self.add(ThreeDAxes(), self.cube)
        self.frame.set_euler_angles(theta=-30 * DEGREES, phi=70 * DEGREES)

    def cue_spin(self) -> None:
        self.play(Rotate(self.cube, PI / 2, axis=OUT), run_time=1)

    def cue_lift(self) -> None:
        self.play(self.cube.animate.shift(2 * OUT), run_time=1)

    PRESETS: ClassVar[dict] = {"spin": cue_spin, "lift": cue_lift}
    SEQUENCE: ClassVar[list] = ["spin", "lift"]
    LOOPS: ClassVar[set] = set()
