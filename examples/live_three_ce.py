"""Stała kamera i panel pokazu F5b oraz kontrolowany znacznik pomiaru."""

from typing import ClassVar

from manim import PI, Rotate, Square, linear

from manimcue.live_scene_ce import LiveSceneCE


class ThreePanel(LiveSceneCE):
    """Zmiana koloru natychmiast, potem obrót obiektu; kamera pozostaje nieruchoma."""

    SEQUENCE: ClassVar[list] = ["flip"]
    LOOPS: ClassVar[set] = set()

    def build_objects(self):
        self.square = Square().set_fill("#FF0000", 1).set_stroke(width=0)
        self.add(self.square)

    def flip(self):
        self.square.become(Square().set_fill("#00FF00", 1).set_stroke(width=0))
        self.play(Rotate(self.square, PI / 2), run_time=2, rate_func=linear)

    PRESETS: ClassVar[dict] = {"flip": flip}
