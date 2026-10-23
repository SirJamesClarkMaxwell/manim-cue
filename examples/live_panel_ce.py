"""Panel Cairo 2D do demo: rotate → pulse → sweep."""

from typing import ClassVar

from manim import BLUE, LEFT, PI, RED, RIGHT, Circle, Rotate, Square

from manimcue.live_scene_ce import LiveSceneCE


class Panel(LiveSceneCE):
    """Zwykłe animacje CE uruchamiane komendami live."""

    def build_objects(self):
        self.square = Square(2).set_fill(BLUE, 0.5).shift(3 * LEFT)
        self.circle = Circle(1).set_fill(RED, 0.5).shift(3 * RIGHT)
        self.add(self.square, self.circle)

    def rotate(self):
        self.play(Rotate(self.square, PI / 2), run_time=1)

    def pulse(self):
        self.play(self.circle.animate.scale(1.6), run_time=0.5)
        self.play(self.circle.animate.scale(1 / 1.6), run_time=0.5)

    def sweep(self):
        self.play(self.square.animate.shift(6 * RIGHT), run_time=3)
        self.play(self.square.animate.shift(6 * LEFT), run_time=3)

    PRESETS: ClassVar[dict] = {"rotate": rotate, "pulse": pulse, "sweep": sweep}
    SEQUENCE: ClassVar[list] = ["rotate", "pulse", "sweep"]
    LOOPS: ClassVar[set] = {"pulse"}
