"""Przypadki brzegowe adaptera CE: historia, czas, lifecycle i pomiar."""

import time
from typing import ClassVar

from manim import BLUE, PI, RED, RIGHT, Circle, Rectangle, Rotate, Square, VGroup, linear

from manimcue.live_scene_ce import LiveSceneCE


class GraphPanel(LiveSceneCE):
    def build_objects(self):
        self.child = Square(1, fill_opacity=1, color="#FFFFFF").set_stroke(width=0)
        self.update_count = 0
        self.tracker = self.track
        self.child.add_updater(self.tracker)
        self.left = VGroup(self.child)
        self.right = VGroup(self.child, Circle(0.3).shift(2 * RIGHT))
        self.add(self.left, self.right)

    def track(self, mobject, dt):
        self.update_count += 1

    def change(self):
        self.play(self.child.animate.shift(2 * RIGHT), run_time=0.1)
        self.left.add(Square(0.3))
        self.right.remove(self.child)

    def named(self):
        self.play(self.child.animate.shift(RIGHT), run_time=0.1)

    def verify(self):
        assert self.left[0] is self.child
        assert self.right[0] is self.child
        assert len(self.left) == 1 and len(self.right) == 2
        assert abs(self.child.get_center()[0]) < 1e-8
        assert self.child.updaters[0] is self.tracker

    PRESETS: ClassVar[dict] = {"change": change, "named": named, "verify": verify, "zażółć": named}
    SEQUENCE: ClassVar[list] = ["change"]


class WaitMatrix(LiveSceneCE):
    def build_objects(self):
        self.dot = Square(0.3, fill_opacity=1, color="#FFFFFF").set_stroke(width=0)
        self.add(self.dot)

    def condition(self):
        began = self.time
        self.wait(2, stop_condition=lambda: self.time - began >= 0.2)
        assert 0.2 <= self.time - began < 0.3

    def frozen(self):
        self.dot.set_color("#FF0000")
        self.dot.add_updater(lambda m, dt: m.shift(RIGHT * dt))
        start = self.dot.get_center().copy()
        self.wait(0.2, frozen_frame=True)
        assert abs(self.dot.get_center()[0] - start[0]) < 1e-8

    def invalid(self):
        self.wait(0.2, frozen_frame=True, stop_condition=lambda: True)

    def dynamic_condition(self):
        self.dot.add_updater(lambda m, dt: m.shift(RIGHT * dt))
        self.wait(2, stop_condition=lambda: self.dot.get_x() >= 0.3)
        assert 0.3 <= self.dot.get_x() < 0.4

    def interrupted_wait(self):
        began = self.time
        self.wait(2)
        self.play(self.dot.animate.shift(2 * RIGHT), run_time=2)
        self.wait(2)
        assert self.time - began == 6
        assert abs(self.dot.get_x() - 2) < 1e-8

    def interrupt(self):
        began = self.time
        self.dot.add_updater(lambda m, dt: m.shift(dt * RIGHT))
        other = Square().shift(-2 * RIGHT)
        self.add(other)
        self.play(other.animate.shift(RIGHT), run_time=2)
        assert self.time - began == 2
        assert self.dot.get_x() < 1
        self.wait(2)
        assert self.time - began == 4
        self.play(other.animate.shift(RIGHT), run_time=2)
        assert self.time - began == 6
        assert abs(other.get_x()) < 1e-8

    def skip(self):
        self.next_section(skip_animations=True)

    PRESETS: ClassVar[dict] = {
        "condition": condition,
        "frozen": frozen,
        "invalid": invalid,
        "interrupt": interrupt,
        "skip": skip,
        "dynamic_condition": dynamic_condition,
        "interrupted_wait": interrupted_wait,
    }
    SEQUENCE: ClassVar[list] = ["interrupt"]


class ShutdownTail(WaitMatrix):
    def tail(self):
        self.wait(10)
        raise RuntimeError("shutdown wykonał resztę callable")

    PRESETS: ClassVar[dict] = {"tail": tail}
    SEQUENCE: ClassVar[list] = ["tail"]


class MeasurePanel(WaitMatrix):
    def motion(self):
        self.dot.move_to(-5 * RIGHT)
        self.play(self.dot.animate.move_to(5 * RIGHT), run_time=35, rate_func=linear)

    PRESETS: ClassVar[dict] = {"motion": motion}
    SEQUENCE: ClassVar[list] = ["motion"]


class MeasurePanel2D(LiveSceneCE):
    def build_objects(self):
        self.square = Square(2).set_fill(BLUE, 0.5).shift(-3 * RIGHT)
        self.circle = Circle(1).set_fill(RED, 0.5).shift(3 * RIGHT)
        self.add(self.square, self.circle)

    def motion(self):
        self.play(
            Rotate(self.square, 30 * PI),
            self.circle.animate.shift(0.5 * RIGHT),
            run_time=35,
            rate_func=linear,
        )

    PRESETS: ClassVar[dict] = {"motion": motion}
    SEQUENCE: ClassVar[list] = ["motion"]
    LOOPS: ClassVar[set] = set()


class SlowImport(LiveSceneCE):
    def build_objects(self):
        time.sleep(20)


class CirclePanel(LiveSceneCE):
    def build_objects(self):
        self.add(Circle(1, color="#FFFFFF", fill_opacity=1).set_stroke(width=0))


class EmptyAlpha(LiveSceneCE):
    def build_objects(self):
        self.camera.background_color = "#336699"
        self.camera.init_background()


class LetterboxEdges(LiveSceneCE):
    def build_objects(self):
        # Nadmiar względem kadru usuwa antyaliasing brzegów z wyroczni pasów.
        self.add(
            Rectangle(width=16, height=9, fill_color="#FF0000", fill_opacity=1, stroke_width=0)
        )
