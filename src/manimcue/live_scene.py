"""Żywa scena manimgl wyzwalana komendami po TCP.

Uruchomienie (wymaga okna — manimgl otwiera je domyślnie):

    uv run manimgl src/manimcue/live_scene.py LiveScene

Port: zmienna środowiskowa MANIMCUE_PORT (domyślnie 47821). Scena wypisuje faktycznie
zbindowany host:port na stdout przy starcie.

Architektura i powody decyzji: SPEC.md. Dwie pułapki opisane tam i tutaj omijane:
`select` patrzy na listener (żeby w ogóle przyjąć klienta), a bufor trzyma bajty —
dekodujemy dopiero kompletną linię.
"""

from __future__ import annotations

import os
import socket
import time
from collections import deque
from collections.abc import Callable
from typing import ClassVar

from manimlib.animation.rotation import Rotate
from manimlib.animation.transform import Transform
from manimlib.constants import BLUE, FRAME_HEIGHT, FRAME_WIDTH, LEFT, PI, RED, RIGHT, UP
from manimlib.logger import log
from manimlib.mobject.geometry import Circle, Square
from manimlib.scene.scene import EndScene, Scene
from pyglet.window import key as PygletWindowKeys

from manimcue import DEFAULT_PORT, HOST, PORT_ENV_VAR
from manimcue.live_transport import LineBuffer, LiveTransport

POLL_TIMEOUT = 1 / 60
"""Timeout `select` równy jednej klatce: bez busy-loopa i bez blokującego czytania."""

RECV_SIZE = 4096

REWIND_TIME = 0.6

ZOOM_STEP = 0.9
"""Skala kadru kamery na jeden ząbek kółka myszy (D28): <1 przybliża."""
"""Czas animowanego cofania [s]."""

KEY_NEXT = "__next__"
KEY_BACK = "__back__"

TRANSPORT_COMMANDS = {"next": KEY_NEXT, "back": KEY_BACK}
"""Komendy z gniazda rownowazne strzalkom. D2 mowi, ze preset z gniazda nie przesuwa
kursora prelegenta — ale `next`/`back` sa jawnymi komendami transportowymi, nie presetami,
wiec kursor przesuwaja. Dzieki nim ta sama sciezka da sie skryptowac i zmierzyc."""


class LiveScene(LiveTransport, Scene):
    """Scena, która zamiast lecieć liniowo kręci się na komendach z gniazda.

    To nadal normalna ``Scene``: ``self.play()``, ``self.add()`` i metody mobjectów
    działają jak wszędzie. Jedyna różnica jest w ``construct()``.
    """

    shutdown_exception = EndScene

    def setup(self) -> None:
        """Kolejka klawiszy musi istniec, zanim okno wysle pierwsze zdarzenie.

        `setup()` wola `Scene.run()` przed `construct()`, wiec to najwczesniejszy
        moment, w ktorym mozemy ja przygotowac.
        """
        self.key_queue: deque[str] = deque()
        self.cursor = 0
        self.abort_cue = False

    def construct(self) -> None:
        if hasattr(self, "live_buffer"):
            return self.live_construct()
        # Tryb okna sprawdzamy PRZED zajęciem portu — inaczej render offline (-w/-o)
        # zostawiłby zbindowane gniazdo.
        if self.window is None:
            raise RuntimeError(
                "LiveScene dziala tylko w trybie okna. "
                "Uruchom bez -w/-s/-o; manimgl otwiera okno domyslnie."
            )

        self.buffer = LineBuffer()
        self.client: socket.socket | None = None
        self.listener: socket.socket | None = None
        try:
            self.listener = self.open_listener()
            self.build_objects()
            while True:
                command = self.next_command()
                if command == KEY_BACK:
                    self.step_back()
                    continue
                from_sequence = command == KEY_NEXT
                if from_sequence:
                    command = self.advance()
                    if command is None:
                        continue
                preset = self.PRESETS.get(command)
                if preset is None:
                    log.warning(f"Nieznana komenda: {command!r} (znane: {sorted(self.PRESETS)})")
                    continue
                self.run_cue(command, preset, from_sequence=from_sequence)
        finally:
            self.close_sockets()

    # --- transport ---------------------------------------------------------

    def open_listener(self) -> socket.socket:
        """Wiąże nieblokujące gniazdo nasłuchujące i ogłasza endpoint na stdout."""
        port = int(os.environ.get(PORT_ENV_VAR, DEFAULT_PORT))
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind((HOST, port))
        listener.listen(1)
        listener.setblocking(False)
        host, bound_port = listener.getsockname()
        print(f"manim-cue listening on {host}:{bound_port}", flush=True)
        return listener

    def next_command(self) -> str:
        """Czeka na jedną kompletną komendę, pompując okno co klatkę.

        ``update_frame(dt=0)`` jest tym, co trzyma okno żywe — ten sam mechanizm,
        którego używa ``InteractiveSceneEmbed.enable_gui``.
        """
        while not self.key_queue and not self.buffer.has_line():
            if self.is_window_closing():
                raise EndScene()
            self.poll_once()
        # Klawisz bije gniazdo: prelegent przy maszynie ma pierwszenstwo nad zdalna komenda.
        if self.key_queue:
            return self.key_queue.popleft()
        line = self.buffer.pop_line()
        return TRANSPORT_COMMANDS.get(line, line)

    def poll_once(self) -> None:
        """Jeden obrót pętli bezczynności: czeka maksymalnie klatkę i pompuje okno.

        `select` patrzy na listener dopóki klienta nie ma — i dalej patrzy, gdy już
        jest, żeby dodatkowego klienta odrzucić zamiast zostawiać go w backlogu.
        """
        self.drain_socket(POLL_TIMEOUT)
        self.update_frame(dt=0)

    # --- sterowanie strzalkami ---------------------------------------------

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        """Strzalki steruja sekwencja cue'ow; reszte klawiszy oddajemy manimgl.

        Zdarzenia klawiatury docieraja tu z `update_frame(dt=0)`, czyli z tej samej
        petli, ktora pompuje okno — takze w czasie `play()`. Dlatego klawisz wcisniety
        w trakcie animacji trafia do kolejki i wykona sie po niej, tak jak komenda
        z gniazda.
        """
        if symbol == PygletWindowKeys.RIGHT:
            self.key_queue.append(KEY_NEXT)
        elif symbol == PygletWindowKeys.LEFT:
            self.key_queue.append(KEY_BACK)
        else:
            super().on_key_press(symbol, modifiers)

    def run_cue(
        self,
        name: str,
        preset: Callable[[LiveScene], None],
        from_sequence: bool = False,
    ) -> None:
        """Odtwarza cue, a cue zapetlone powtarza, dopoki czegos nie przyjdzie.

        Semantyka zapetlenia jest ta sama co `next_slide(loop=True)` w manim-slides:
        przerwanie nastepuje na koncu powtorzenia, nie w jego srodku.
        """
        # Stan zapisujemy PRZED cue, zeby strzalka w lewo miala co przywrocic.
        if from_sequence:
            self.save_state()
        log.info(self.cue_line(name, from_sequence))
        preset(self)
        self.abort_cue = False
        if name not in self.LOOPS:
            return
        while True:
            # W czasie play() gniazdo nie bylo czytane, wiec najpierw zaciagamy to,
            # co przyszlo; bez tego petla nie zobaczylaby komendy zdalnej.
            self.poll_once()
            if self.key_queue or self.buffer.has_line():
                log.info(f"Petla {name} przerwana")
                return
            preset(self)
            self.abort_cue = False

    def interrupt_requested(self) -> bool:
        """Czy czeka klawisz albo komenda, ktora powinna urwac biezace cue."""
        return bool(self.key_queue) or self.buffer.has_line()

    def progress_through_animations(self, animations) -> None:
        """Petla klatek manimgl plus przerywanie w dowolnej klatce.

        Nadpisane, zeby `self.play()` w cue'ach pozostalo zwyklym `play()` — cue nie
        wie nic o przerywaniu. Po urwaniu `play()` manimgl i tak wola `finish_animations()`,
        wiec mobjecty domykaja sie do stanu koncowego: przerwanie nie zostawia sceny
        w polowie przeksztalcenia, a daje skok do konca, tak jak przewiniecie klipu
        w manim-slides.

        Flaga `abort_cue` zostaje podniesiona, zeby kolejne `play()` w tym samym cue
        tez przeleciały natychmiast — inaczej dwuetapowe cue (np. `sweep`) grałoby
        drugą połowę mimo przerwania.

        ponytail: `wait()` ma wlasna petle w manimgl i nie jest tu przerywany.
        Zadne cue w PRESETS go nie uzywa; gdy zacznie, trzeba nadpisac tez `wait()`
        albo podac mu `stop_condition=self.interrupt_requested`.
        """
        if hasattr(self, "live_buffer"):
            return self.live_progress(animations)
        if self.abort_cue:
            return
        last_t = 0
        for t in self.get_animation_time_progression(animations):
            dt = t - last_t
            last_t = t
            for animation in animations:
                animation.update_mobjects(dt)
                animation.interpolate(t / animation.run_time)
            self.update_frame(dt)
            self.emit_frame()
            # Klawisze przychodza z update_frame; gniazdo trzeba dociagnac samemu.
            self.drain_socket(0)
            if self.interrupt_requested():
                self.abort_cue = True
                log.info("Animacja przerwana")
                return

    def save_state(self) -> None:
        """Historia sekwencji bez deduplikacji identycznych pozycji (D37)."""
        self.redo_stack = []
        self.undo_stack.append(
            self.checkpoints.capture() if hasattr(self, "checkpoints") else self.get_state()
        )
        self.undo_stack[:] = self.undo_stack[-50:]

    def rewind(self) -> None:
        """Animowany powrot do stanu sprzed ostatniego cue.

        manim-slides cofa, odtwarzajac nagrany klip od konca; zywa scena nie ma klipu,
        wiec przeprowadzamy mobjecty `Transform`em do kopii zapisanych w `undo_stack`
        manimgl. Sciezka jest interpolacja miedzy dwoma stanami, nie dokladnym
        odwroceniem pierwotnej animacji — frame-exact rewind wymagalby nagrywania klatek.
        Po animacji wolamy `undo()`, zeby stan domknal sie dokladnie, takze dla mobjectow,
        ktore cue dodalo albo usunelo.
        """
        if not self.undo_stack:
            log.info("Brak zapisanego stanu; nie ma czego cofac")
            return
        if hasattr(self, "checkpoints"):
            self.checkpoints.reserve()
            self.abort_cue = False
            self.undo_stack.pop().animate(self)
            return
        t0 = time.perf_counter()
        state = self.undo_stack[-1]
        pairs = [
            (mob, copy) for mob, copy in state.mobjects_to_copies.items() if mob in self.mobjects
        ]
        t_pairs = time.perf_counter()
        anims = [Transform(mob, copy.copy()) for mob, copy in pairs]
        t_build = time.perf_counter()
        if anims:
            self.play(*anims, run_time=REWIND_TIME)
        t_play = time.perf_counter()
        self.undo()
        t_undo = time.perf_counter()
        log.debug(
            "rewind: pairs=%.1fms build=%.1fms play=%.1fms (run_time=%.0fms) undo=%.1fms",
            1000 * (t_pairs - t0),
            1000 * (t_build - t_pairs),
            1000 * (t_play - t_build),
            1000 * REWIND_TIME,
            1000 * (t_undo - t_play),
        )

    # --- proces zarządzany bez okna ---------------------------------------

    def live_view(self, command: str) -> None:
        """Nawigacja kamerą z playera (D28) — jak mysz w oknie manimgl, ale bez okna.

        `view orbit dx dy` obraca (jak `d` + ruch), `view pan dx dy` przesuwa (jak `f` + ruch):
        przesunięcie myszy w ułamkach warstwy, y w dół, przeliczane jak w
        `Window.pixel_coords_to_space_coords` manimgl. `view zoom kroki` — kółko, dodatnie
        przybliża. `view reset` — kadr kamery zastany na ostatniej klatce granicznej (READY,
        koniec cue, `back`), nie domyślny kadr `Scene`, bo scena może ustawić kamerę w
        `build_objects`.

        Nie jest cue: nie przerywa animacji i nie rusza sekwencji. Kamera należy jednak do
        `SceneState` (manimgl dodaje ją do `mobjects`), więc `back` przywraca także widok sprzed
        cue, a w trakcie cue animującego kamerę nawigacja przegrywa z animacją (runda 10).
        """
        name, *args = command.split()[1:] or [""]
        frame = self.frame
        try:
            values = [float(arg) for arg in args]
            if name in ("orbit", "pan"):
                dx, dy = values
                fixed = dx * FRAME_WIDTH * RIGHT - dy * FRAME_HEIGHT * UP
                if name == "orbit":
                    frame.increment_theta(-fixed[0] * self.pan_sensitivity)
                    frame.increment_phi(fixed[1] * self.pan_sensitivity)
                else:
                    # Płaszczyzna ekranu obróconej kamery, nie osie świata (runda 10, p. 3).
                    frame.shift(-frame.from_fixed_frame_point(fixed, relative=True))
            elif name == "zoom":
                (steps,) = values
                frame.scale(ZOOM_STEP**steps)
            elif name == "reset" and not values:
                frame.become(self.live_view_home)
            else:
                raise ValueError(name)
        except ValueError:
            log.warning(f"Niepoprawna komenda widoku: {command!r}")
            return
        self.live_view_dirty = True

    def live_publish(self, boundary: bool = False, dt: float = 0) -> None:
        began = time.monotonic()
        self.live_view_dirty = False
        if not (getattr(self, "live_prefetch", False) and self.live_frame_id):
            self.update_frame(dt, force_draw=True)
        rendered = time.monotonic()
        pixels = self.camera.get_raw_fbo_data(dtype="f1")
        width, height = self.camera.get_pixel_shape()
        target = self.live_buffer
        if (width, height) != (target.width, target.height):
            # Shader manimgl używa stałego 16:9; pasy zachowują proporcje bez łatania backendu.
            import numpy as np

            canvas = np.zeros((target.height, target.width, 4), dtype=np.uint8)
            canvas[:] = np.rint(np.array(self.camera.background_rgba) * 255).astype(np.uint8)
            x, y = (target.width - width) // 2, (target.height - height) // 2
            canvas[y : y + height, x : x + width] = np.frombuffer(pixels, dtype=np.uint8).reshape(
                height, width, 4
            )
            pixels = canvas.tobytes()
        read = time.monotonic()
        self.live_frame_id += 1
        self.live_buffer.publish(pixels, self.live_frame_id, boundary)
        if boundary:
            self.live_boundary_id = self.live_frame_id
            self.live_view_home = self.frame.copy()
            if hasattr(self, "live_boundary_request"):
                self.live_status(f"BOUNDARY {self.live_boundary_request} {self.live_frame_id}")
        published = time.monotonic()
        for name, elapsed in (
            ("render", rendered - began),
            ("readback", read - rendered),
            ("publish", published - read),
        ):
            self.live_metrics[name][0] += elapsed
            self.live_metrics[name][1] += 1

    def live_progress(self, animations) -> None:
        if self.abort_cue:
            return
        for elapsed, dt in self.live_times(self.get_run_time(animations)):
            for animation in animations:
                animation.update_mobjects(dt)
                animation.interpolate(min(1, elapsed / animation.run_time))
            self.live_publish(dt=dt)

    def wait(self, duration=None, stop_condition=None, note=None, ignore_presenter_mode=False):
        if not hasattr(self, "live_buffer"):
            return super().wait(duration, stop_condition, note, ignore_presenter_mode)
        if self.abort_cue:
            return
        duration = self.default_wait_time if duration is None else duration
        self.pre_play()
        for _, dt in self.live_times(duration):
            if self.should_update_mobjects() or self.live_view_dirty:
                self.live_publish(dt=dt)
            else:
                self.increment_time(dt)
            if stop_condition is not None and stop_condition():
                break
        self.post_play()

    # --- treść sceny -------------------------------------------------------

    def build_objects(self) -> None:
        """Mobjecty, na których działają presety."""
        self.square = Square(side_length=2).set_fill(BLUE, opacity=0.5).shift(3 * LEFT)
        self.circle = Circle(radius=1).set_fill(RED, opacity=0.5).shift(3 * RIGHT)
        self.add(self.square, self.circle)
        self.update_frame(force_draw=True)

    def cue_rotate(self) -> None:
        """Obrót kwadratu o 90 stopni."""
        self.play(Rotate(self.square, PI / 2, run_time=1))

    def cue_pulse(self) -> None:
        """Skok skali koła i powrót."""
        self.play(self.circle.animate.scale(1.6), run_time=0.5)
        self.play(self.circle.animate.scale(1 / 1.6), run_time=0.5)

    def cue_sweep(self) -> None:
        """Długi przejazd kwadratu tam i z powrotem (6 s).

        Istnieje po to, żeby dało się wysłać komendy w czasie trwania animacji.
        """
        self.play(self.square.animate.shift(6 * RIGHT), run_time=3)
        self.play(self.square.animate.shift(6 * LEFT), run_time=3)

    PRESETS: ClassVar[dict[str, Callable[[LiveScene], None]]] = {
        "rotate": cue_rotate,
        "pulse": cue_pulse,
        "sweep": cue_sweep,
    }
    """Nazwa komendy -> callable(self). Nieznana nazwa to log, nie wywrotka."""

    LOOPS: ClassVar[set[str]] = {"pulse"}
    """Cue, ktore powtarzaja sie do nastepnego klawisza albo komendy — jak `loop=True`
    w manim-slides."""

    SEQUENCE: ClassVar[list[str]] = ["rotate", "pulse", "sweep"]
    """Kolejnosc cue'ow dla strzalek. Gniazdo nadal wyzwala dowolny preset po nazwie,
    niezaleznie od tego kursora — zdalna komenda nie przesuwa pozycji prelegenta."""
