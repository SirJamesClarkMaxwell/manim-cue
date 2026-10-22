"""PoC F6b: krokowanie sceny-dziecka (zwykła `Scene` CE) w gospodarzu, jeden wątek, greenlet.

Dziecko wykonuje zwykłe `self.play()`/`self.wait()`; adapter po każdej próbce oddaje sterowanie
gospodarzowi (`greenlet.switch`), a gospodarz wznawia dziecko raz na swoją klatkę. Widok w
gospodarzu: ramka (prostokąt) + kopie mobjectów dziecka odwzorowane w ramkę (skala jednorodna,
z obrysem), przebudowywane co klatkę.
"""

import random

import numpy as np
from greenlet import getcurrent, greenlet
from manim import Camera, ImageMobject, Rectangle, VGroup, config, tempconfig


class StepAdapter:
    """Mixin dziecka: play() krokuje animacje bez renderu i oddaje sterowanie po każdej próbce."""

    stepper: "ChildStepper"

    def play(self, *args, **kwargs):
        # compile_animation_data ustawia stop_condition z `Wait` (wait_until CE bez zmian).
        self.compile_animation_data(*args, **kwargs)
        self.begin_animations()
        fps = config.frame_rate
        stop = self.stop_condition
        for t in np.arange(0, self.duration, 1 / fps):
            self.update_to_time(t)
            self.stepper.child_time += 1 / fps
            self.stepper.yield_to_host()
            if stop is not None and stop():
                break
        for animation in self.animations:
            animation.finish()
            animation.clean_up_from_scene(self)
        self.update_mobjects(0)


class ChildStepper:
    """Właściciel greenleta dziecka; advance() = jedna próbka dziecka na klatkę gospodarza."""

    def __init__(self, child_class, host):
        stepped = type(f"Stepped{child_class.__name__}", (StepAdapter, child_class), {})
        state = (random.getstate(), np.random.get_state())
        try:
            # Konstruktor Scene tworzy renderer i writer — dry_run tylko na czas konstrukcji.
            with tempconfig({"dry_run": True}):
                self.child = stepped()
        finally:
            random.setstate(state[0])
            np.random.set_state(state[1])
        self.child.stepper = self
        self.child.host = host
        self.child_time = 0.0
        self.done = False
        self.last_host_time = None
        self.host_greenlet = None
        self.greenlet = greenlet(self._run)

    def _run(self):
        self.child.setup()
        self.child.construct()
        self.child.tear_down()
        self.done = True

    def yield_to_host(self):
        self.host_greenlet.switch()

    def advance(self, host_time: float) -> None:
        if self.done or host_time == self.last_host_time:
            return
        self.last_host_time = host_time
        self.host_greenlet = getcurrent()
        state = (random.getstate(), np.random.get_state())
        try:
            self.greenlet.switch()
        finally:
            random.setstate(state[0])
            np.random.set_state(state[1])


class Shared:
    """Stepper, gospodarz i treść — wspólne dla widoku i jego kopii (deepcopy zwraca to samo)."""

    def __init__(self, stepper, host):
        self.stepper = stepper
        self.host = host
        # Treść: jeden ImageMobject o stałej tożsamości — CE ustala rodziny ruchomych mobjectów
        # raz na `play()`, więc podmieniane kopie mobjectów dziecka byłyby niewidoczne.
        self.content = ImageMobject(np.zeros((2, 2, 4), dtype=np.uint8))
        self.content.add_updater(lambda mob, dt: None)  # czasowy: ruchomy, nie statyczny
        self.camera = None
        self.added = False

    def __deepcopy__(self, memo):
        return self


class ChildView(VGroup):
    """Ramka w gospodarzu (stała rodzina — animowalna jak każdy mobject); treść dziecka rysuje
    jego kamera Cairo w rozdzielczości ramki, z przezroczystym tłem."""

    def __init__(self, stepper: ChildStepper, host, height: float = 4.0, **kwargs):
        self.frame = Rectangle(
            width=height * config.frame_width / config.frame_height, height=height
        ).set_stroke(opacity=0)
        super().__init__(self.frame, **kwargs)
        self.shared = Shared(stepper, host)
        self.add_updater(lambda mob, dt: None)  # czasowy — wait() nie zamraża

    def update(self, dt: float = 0, recursive: bool = True):
        shared = self.shared
        shared.stepper.advance(shared.host.time)
        # Kopie z animacji (starting_mobject, target) dzielą `shared`, ale nie są w scenie.
        if any(mob is self for mob in shared.host.mobjects):
            if not shared.added:
                shared.host.add(shared.content)
                shared.added = True
            self.rebuild()
        return super().update(dt, recursive)

    def rebuild(self) -> None:
        shared = self.shared
        height = max(2, round(self.frame.height / config.frame_height * config.pixel_height))
        width = max(2, round(height * config.frame_width / config.frame_height))
        camera = shared.camera
        if camera is None or (camera.pixel_width, camera.pixel_height) != (width, height):
            camera = shared.camera = Camera(
                pixel_width=width, pixel_height=height, background_opacity=0
            )
        camera.reset()
        camera.capture_mobjects(shared.stepper.child.mobjects)
        content = shared.content
        content.pixel_array = camera.pixel_array.copy()
        content.stretch_to_fit_width(self.frame.width)
        content.stretch_to_fit_height(self.frame.height)
        content.move_to(self.frame.get_center())
