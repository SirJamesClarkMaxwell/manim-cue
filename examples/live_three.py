"""Stała kamera i panel pokazu F5b oraz kontrolowany znacznik pomiaru."""

from typing import ClassVar

from manimlib import PI, Rotate, Square, linear

from manimcue.live_scene import LiveScene


class ThreePanel(LiveScene):
    """Zmiana koloru natychmiast, potem obrót obiektu; kamera pozostaje nieruchoma."""

    SEQUENCE: ClassVar[list] = ["flip"]
    LOOPS: ClassVar[set] = set()

    def build_objects(self):
        self.square = Square().set_fill("#FF0000", 1).set_stroke(width=0)
        self.add(self.square)
        self.green = False

    def flip(self):
        self.green = not self.green
        self.square.set_fill("#00FF00" if self.green else "#FF0000", 1)
        self.play(Rotate(self.square, PI / 2), run_time=0.4, rate_func=linear)

    PRESETS: ClassVar[dict] = {"flip": flip}
