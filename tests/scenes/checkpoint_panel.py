"""Wspólny deterministyczny korpus F5g obu silników."""

from typing import ClassVar


class CheckpointPanel:
    SEQUENCE: ClassVar[list] = ["step", "step", "step"]
    LOOPS: ClassVar[set] = {"cycle"}

    def build_objects(self):
        self.square = self.square_type(side_length=1).set_fill("#FF0000", 1).set_stroke(width=0)
        self.add(self.square)

    def step(self):
        self.play(self.square.animate.shift([0.5, 0, 0]), run_time=0.08)

    def enter_move(self):
        self.play(self.square.animate.shift([1, 0, 0]), run_time=0.15)

    def paint(self):
        self.square.set_fill("#00FF00", 1)

    def unsupported(self):
        self.square.external_resource = object()

    def limited(self):
        self.checkpoints.max_bytes = 1

    def fail_restore(self):
        def fail(scene):
            scene.square.set_fill("#00FF00", 1)
            raise RuntimeError("wstrzyknięty błąd restore")

        for snapshot, _, _ in self.checkpoints.entries.values():
            snapshot.animate = fail

    def two_stage(self):
        self.play(self.square.animate.shift([1, 0, 0]), run_time=0.6)
        self.wait(0.6)
        self.play(self.square.animate.shift([1, 0, 0]), run_time=0.6)

    def cycle(self):
        self.wait(0.2)

    def verify_end(self):
        assert abs(self.square.get_center()[0] - 2) < 1e-8
        self.live_status("END_VERIFIED")

    PRESETS: ClassVar[dict] = {
        "step": step,
        "move": enter_move,
        "paint": paint,
        "unsupported": unsupported,
        "limit": limited,
        "fail_restore": fail_restore,
        "two_stage": two_stage,
        "cycle": cycle,
        "verify_end": verify_end,
    }


class GraphCheckpointPanel(CheckpointPanel):
    def build_objects(self):
        super().build_objects()
        self.remove(self.square)
        self.left, self.right = self.group_type(self.square), self.group_type(self.square)
        self.initial_updater = lambda mob, dt: None
        self.square.add_updater(self.initial_updater)
        self.add(self.left, self.right)

    def mutate(self):
        self.square.clear_updaters()
        self.square.add_updater(lambda mob, dt: None)
        self.left.remove(self.square)
        self.right.add(self.square_type().shift([2, 0, 0]))
        self.square.set_fill("#00FF00", 1)

    def verify(self):
        assert self.left.submobjects == self.right.submobjects == [self.square]
        assert self.left.submobjects[0] is self.square is self.right.submobjects[0]
        assert self.square.updaters == [self.initial_updater]
        snapshot = next(iter(self.checkpoints.entries.values()))[0]
        assert self.time == snapshot.scene_time
        self.live_status("GRAPH_VERIFIED")

    PRESETS: ClassVar[dict] = {**CheckpointPanel.PRESETS, "mutate": mutate, "verify": verify}
