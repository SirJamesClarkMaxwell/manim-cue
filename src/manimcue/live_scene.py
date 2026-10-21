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
import select
import socket
import time
from collections import deque
from collections.abc import Callable
from typing import ClassVar

from manimlib.animation.rotation import Rotate
from manimlib.animation.transform import Transform
from manimlib.constants import BLUE, LEFT, PI, RED, RIGHT
from manimlib.logger import log
from manimlib.mobject.geometry import Circle, Square
from manimlib.scene.scene import EndScene, Scene
from pyglet.window import key as PygletWindowKeys

from manimcue import DEFAULT_PORT, HOST, PORT_ENV_VAR

POLL_TIMEOUT = 1 / 60
"""Timeout `select` równy jednej klatce: bez busy-loopa i bez blokującego czytania."""

RECV_SIZE = 4096

REWIND_TIME = 0.6
"""Czas animowanego cofania [s]."""

KEY_NEXT = "__next__"
KEY_BACK = "__back__"

TRANSPORT_COMMANDS = {"next": KEY_NEXT, "back": KEY_BACK}
"""Komendy z gniazda rownowazne strzalkom. D2 mowi, ze preset z gniazda nie przesuwa
kursora prelegenta — ale `next`/`back` sa jawnymi komendami transportowymi, nie presetami,
wiec kursor przesuwaja. Dzieki nim ta sama sciezka da sie skryptowac i zmierzyc."""


class LineBuffer:
    """Bufor bajtów z framingiem po ``b"\\n"``.

    Trzyma bajty, nie tekst: pojedynczy ``recv()`` może rozciąć znak wielobajtowy
    UTF-8, a ``.decode()`` na takim kawałku rzuca wyjątkiem. Dekodujemy dopiero
    kompletną linię.
    """

    def __init__(self) -> None:
        self._data = b""

    def feed(self, chunk: bytes) -> None:
        self._data += chunk

    def clear(self) -> None:
        self._data = b""

    def has_line(self) -> bool:
        return b"\n" in self._data

    def pop_line(self) -> str:
        """Zdejmuje pierwszą kompletną linię i dekoduje ją jako UTF-8."""
        line, _, rest = self._data.partition(b"\n")
        self._data = rest
        return line.decode("utf-8", errors="replace").strip()


class LiveScene(Scene):
    """Scena, która zamiast lecieć liniowo kręci się na komendach z gniazda.

    To nadal normalna ``Scene``: ``self.play()``, ``self.add()`` i metody mobjectów
    działają jak wszędzie. Jedyna różnica jest w ``construct()``.
    """

    def setup(self) -> None:
        """Kolejka klawiszy musi istniec, zanim okno wysle pierwsze zdarzenie.

        `setup()` wola `Scene.run()` przed `construct()`, wiec to najwczesniejszy
        moment, w ktorym mozemy ja przygotowac.
        """
        self.key_queue: deque[str] = deque()
        self.cursor = 0
        self.abort_cue = False

    def construct(self) -> None:
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

    def drain_socket(self, timeout: float) -> None:
        """Obsluguje gniazda bez pompowania klatki.

        Rozdzielone z `poll_once`, zeby petla animacji mogla zagladac do gniazda
        bez dorysowywania dodatkowej klatki.
        """
        watch = [self.listener]
        if self.client is not None:
            watch.append(self.client)
        ready, _, _ = select.select(watch, [], [], timeout)
        # Klienta obslugujemy PRZED listenerem. Jesli poprzedni klient rozlaczyl sie
        # w czasie animacji, jego EOF czeka nieodczytany; przyjecie nowego klienta
        # przed odczytaniem tego EOF odrzucilo by go przez martwe juz polaczenie.
        if self.client in ready:
            self.read_client()
        if self.listener in ready:
            self.accept_client()

    def accept_client(self) -> None:
        """Przyjmuje jednego klienta; kolejnych zamyka od razu."""
        conn, addr = self.listener.accept()
        if self.client is not None:
            log.warning(f"Odrzucono dodatkowego klienta {addr}: obslugujemy jednego na raz")
            conn.close()
            return
        conn.setblocking(False)
        self.client = conn
        log.info(f"Klient {addr} podlaczony")

    def read_client(self) -> None:
        """Dociąga bajty; EOF (``b""``) rozłącza klienta, ale nie kończy sceny."""
        try:
            chunk = self.client.recv(RECV_SIZE)
        except OSError:
            chunk = b""
        if chunk:
            self.buffer.feed(chunk)
        else:
            self.drop_client()

    def drop_client(self) -> None:
        """Zamyka gniazdo klienta i zeruje bufor — niekompletna linia jest do wyrzucenia."""
        self.client.close()
        self.client = None
        self.buffer.clear()
        log.info("Klient rozlaczony; scena czeka na nastepnego")

    def close_sockets(self) -> None:
        """Zamyka oba gniazda na każdej ścieżce wyjścia z ``construct()``."""
        for sock in (self.client, self.listener):
            if sock is not None:
                sock.close()
        self.client = None
        self.listener = None

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
        t0 = time.perf_counter()
        state = self.undo_stack[-1]
        pairs = [
            (mob, copy)
            for mob, copy in state.mobjects_to_copies.items()
            if mob in self.mobjects
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

    def advance(self) -> str | None:
        """Nazwa kolejnego cue z sekwencji albo None, gdy sekwencja sie skonczyla."""
        if self.cursor >= len(self.SEQUENCE):
            log.info(f"Koniec sekwencji ({len(self.SEQUENCE)} cue); strzalka w lewo cofa")
            return None
        name = self.SEQUENCE[self.cursor]
        self.cursor += 1
        return name

    def step_back(self) -> None:
        """Cofa ostatnie cue, przywracajac stan mobjectow zapisany przed nim.

        Cofanie jest animowane (`rewind()`), ale sciezka jest interpolacja miedzy
        stanem koncowym i poczatkowym, nie odwroceniem pierwotnej animacji.
        """
        if self.cursor == 0:
            log.info("Jestes na poczatku sekwencji; nie ma czego cofac")
            return
        self.cursor -= 1
        self.rewind()
        log.info(f"Cofnieto do pozycji {self.cursor}/{len(self.SEQUENCE)}")

    def cue_line(self, name: str, from_sequence: bool) -> str:
        """Linia dla prelegenta: co leci, gdzie jesteśmy, co dalej.

        Pozycje pokazujemy tylko dla cue z sekwencji: preset z gniazda kursora nie
        przesuwa (D2), wiec dopisanie do niego pozycji wprowadzaloby w blad.
        """
        position = self.position_hint() if from_sequence else ""
        loop = "  [petla]" if name in self.LOOPS else ""
        return f"Cue: {name}{position}{loop}"

    def position_hint(self) -> str:
        """Dopisek do logu: pozycja w sekwencji i nazwa nastepnego cue."""
        if self.cursor == 0 or self.cursor > len(self.SEQUENCE):
            return ""
        nxt = self.SEQUENCE[self.cursor] if self.cursor < len(self.SEQUENCE) else "-"
        return f"  [{self.cursor}/{len(self.SEQUENCE)}, nastepne: {nxt}]"

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
