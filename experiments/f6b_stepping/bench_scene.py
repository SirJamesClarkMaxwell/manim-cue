import random
import time

from manim import BLUE, LEFT, RIGHT, Circle, Scene, VGroup, linear
from stepped import ChildStepper, ChildView


class Busy(Scene):
    """~20 mobjectów w ruchu przez 5 s."""

    def construct(self):
        dots = VGroup(
            *[
                Circle(radius=0.3, color=BLUE, fill_opacity=0.6).shift((i - 10) * 0.6 * RIGHT)
                for i in range(20)
            ]
        )
        self.add(dots)
        self.play(dots.animate.shift(2 * LEFT).rotate(1.0), run_time=5, rate_func=linear)


class BusyHost(Scene):
    def construct(self):
        random.seed(7)
        before = random.random()
        random.seed(7)
        stepper = ChildStepper(Busy, self)
        after = random.random()
        print(f"RNG preserved: {before == after}", flush=True)
        view = ChildView(stepper, self, height=4)
        self.add(view)
        t = time.perf_counter()
        self.play(view.animate.shift(RIGHT), run_time=5, rate_func=linear)
        print(f"HOST_PLAY_S {time.perf_counter() - t:.2f}", flush=True)
