"""Puste kolorowe tło do bramki wykonalności alfy GL."""

from manimcue.live_scene import LiveScene


class EmptyAlpha(LiveScene):
    def build_objects(self):
        self.camera.background_rgba[:3] = (0.2, 0.4, 0.6)


class EmptyBlack(LiveScene):
    def build_objects(self):
        self.camera.background_rgba[:3] = (0, 0, 0)
