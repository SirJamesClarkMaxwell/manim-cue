from manim import (
    BLUE,
    DOWN,
    LEFT,
    RED,
    RIGHT,
    UR,
    YELLOW,
    Dot,
    FadeIn,
    FadeOut,
    Scene,
    Square,
    linear,
)
from stepped import ChildStepper, ChildView


class Child(Scene):
    """Zwykła scena CE — bez żadnej wiedzy o krokowaniu, poza odczytem gospodarza w wait_until."""

    def construct(self):
        square = Square(side_length=2, color=RED, fill_opacity=1).shift(3 * LEFT)
        self.play(FadeIn(square), run_time=0.5)
        self.play(square.animate.shift(6 * RIGHT), run_time=2, rate_func=linear)
        # Reakcja na gospodarza: czekaj, aż jego kropka przejdzie przez x = 0.
        self.wait_until(lambda: self.host.dot.get_x() > 0)
        self.play(square.animate.set_color(BLUE), run_time=0.5)
        self.play(FadeOut(square), run_time=0.5)


class Host(Scene):
    def construct(self):
        self.dot = Dot(color=YELLOW).shift(6 * LEFT + 3 * DOWN)
        self.add(self.dot)
        view = ChildView(ChildStepper(Child, self), self, height=4)
        self.add(view)
        self.play(
            self.dot.animate.shift(3 * RIGHT), view.animate.scale(0.5).to_corner(UR), run_time=3
        )
        self.play(self.dot.animate.shift(6 * RIGHT), run_time=2)
        self.wait(1)
