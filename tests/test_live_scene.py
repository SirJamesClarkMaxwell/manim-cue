"""Testy części, które dają się sprawdzić bez okna.

Kryteria 1, 2, 5 i 6 z SPEC.md wymagają otwartego okna i przechodzi się je ręcznie
(instrukcja w README.md). Tutaj bez OpenGL: framing bajtów (kryterium 4), nieznana
komenda (kryterium 3), brak okna (kryterium 7), czekanie na `select` zamiast
busy-loopa (kryterium 8) oraz obie pułapki z SPEC.md.
"""

import socket
import time
from types import SimpleNamespace

import pytest

from manimcue.live_scene import KEY_BACK, KEY_NEXT, POLL_TIMEOUT, LineBuffer, LiveScene

LINE_ROTATE = ("rotate" + chr(10)).encode()
LINE_PULSE = ("pulse" + chr(10)).encode()

MAX_POLLS = 100
"""Górna granica obrotów pętli w testach — żeby błąd był porażką, nie zawieszeniem."""


@pytest.fixture(params=["manimgl", "ce-cairo"])
def transport_scene(request):
    """Prawdziwy parser TCP, publikacja obu backendów i bufor; tylko kamera bez GPU."""
    from collections import deque
    from threading import Lock

    import numpy as np

    from manimcue.frame_buffer import FrameBuffer, buffer_size
    from manimcue.live_checkpoint import CheckpointStore
    from manimcue.live_scene_ce import LiveSceneCE
    from manimcue.live_transport import LiveTransport

    class TransportScene(LiveTransport):
        live_publish = (
            LiveScene.live_publish if request.param == "manimgl" else LiveSceneCE.live_publish
        )

        def save_state(self):
            self.undo_stack.append(self.checkpoints.capture())

        def rewind(self):
            self.undo_stack.pop().restore(self)

    scene = TransportScene()
    scene.SEQUENCE, scene.PRESETS, scene.LOOPS = [], {}, set()
    scene.buffer = LineBuffer()
    scene.listener = socket.socket()
    scene.listener.bind(("127.0.0.1", 0))
    scene.listener.listen(1)
    peer = socket.create_connection(scene.listener.getsockname())
    scene.client, _ = scene.listener.accept()
    scene.client.setblocking(False)
    scene.live_commands = deque()
    scene.live_step = None
    scene.live_step_request = scene.live_step_progress = 0
    scene.live_reserved = scene.live_generation = None
    scene.live_request = scene.live_reservation_request = scene.live_entry_counter = 0
    scene.live_frame_id = scene.live_boundary_id = scene.live_seen = 0
    scene.live_boundary_request = "0"
    scene.live_loop = scene.abort_cue = False
    scene.live_outgoing = bytearray()
    scene.cursor = 0
    scene.undo_stack = []
    scene.mobjects = []
    scene.time = 0
    scene.assemble_render_groups = lambda: None
    scene.live_bootstrap = SimpleNamespace(send=lambda value: None)
    scene.camera = SimpleNamespace(
        get_raw_fbo_data=lambda **kw: bytes(4),
        get_pixel_shape=lambda: (1, 1),
        pixel_array=np.zeros((1, 1, 4), dtype=np.uint8),
        fps=60,
    )
    scene.frame = SimpleNamespace(copy=lambda: None)
    scene.update_frame = lambda *args, **kw: None
    scene.renderer = SimpleNamespace(update_frame=lambda scene: None)
    scene.live_metrics = {name: [0.0, 0] for name in ("render", "readback", "publish")}
    memory = SimpleNamespace(size=buffer_size(1, 1), buf=bytearray(buffer_size(1, 1)))
    scene.live_buffer = FrameBuffer(memory, Lock(), 1, 1)
    scene.checkpoints = CheckpointStore(scene)
    try:
        yield scene, peer
    finally:
        peer.close()
        scene.close_sockets()


@pytest.mark.parametrize("direction,result", [("next", "end"), ("back", "start")])
def test_sequence_start_end_empty(transport_scene, direction, result):
    scene, peer = transport_scene
    peer.sendall(f"step 3 {direction}\n".encode())
    scene.live_poll(0.1)
    scene.live_execute_step(*scene.live_commands.popleft()[1:])
    frame = scene.live_buffer.try_read()
    assert frame.boundary and frame.frame_id == scene.live_boundary_id == 1
    statuses = peer.recv(4096).decode()
    assert "BOUNDARY 3 1\n" in statuses
    assert f"STEP_RESULT 3 {result} 1\n" in statuses
    peer.sendall(b"frame_seen 1\n")
    scene.live_barrier()
    assert scene.live_seen == 1 and scene.cursor == 0


@pytest.mark.parametrize("barrier", [False, True])
def test_step_fifo_one_recv_and_ack_barrier(transport_scene, barrier):
    scene, peer = transport_scene
    if barrier:
        scene.live_publish(boundary=True)
    peer.sendall(b"step 1 next\nstep 2 back\n" + (b"frame_seen 1\n" if barrier else b""))
    if barrier:
        scene.live_barrier()
    else:
        scene.live_poll(0.1)
    assert list(scene.live_commands) == [("step", "1", "next"), ("step", "2", "back")]
    scene.live_execute_step(*scene.live_commands.popleft()[1:])
    # Wykonywany krok przyjmuje tylko jednego następcę.
    scene.live_step = "1"
    peer.sendall(b"step 3 next\n")
    scene.live_poll(0.1)
    assert list(scene.live_commands) == [("step", "2", "back")]
    assert "STEP_RESULT 3 error 0" in peer.recv(4096).decode()


# --- bufor bajtów ----------------------------------------------------------


def test_two_commands_in_one_packet():
    buffer = LineBuffer()
    buffer.feed(b"rotate\npulse\n")
    assert buffer.pop_line() == "rotate"
    assert buffer.pop_line() == "pulse"
    assert not buffer.has_line()


def test_command_split_across_packets():
    buffer = LineBuffer()
    buffer.feed(b"rot")
    assert not buffer.has_line()
    buffer.feed(b"ate\n")
    assert buffer.pop_line() == "rotate"


def test_multibyte_character_split_across_packets():
    """Pułapka z SPEC.md: dekodowanie per recv() rozwaliłoby się tutaj."""
    buffer = LineBuffer()
    payload = "zażółć\n".encode()
    buffer.feed(payload[:4])  # cięcie w środku znaku wielobajtowego
    buffer.feed(payload[4:])
    assert buffer.pop_line() == "zażółć"


def test_crlf_is_stripped():
    buffer = LineBuffer()
    buffer.feed(b"rotate\r\n")
    assert buffer.pop_line() == "rotate"


def test_partial_line_survives_pop():
    buffer = LineBuffer()
    buffer.feed(b"rotate\npul")
    assert buffer.pop_line() == "rotate"
    assert not buffer.has_line()
    buffer.feed(b"se\n")
    assert buffer.pop_line() == "pulse"


def test_clear_drops_partial_line():
    buffer = LineBuffer()
    buffer.feed(b"pul")
    buffer.clear()
    buffer.feed(b"se\n")
    assert buffer.pop_line() == "se"


# --- presety i tryb okna ---------------------------------------------------


def test_unknown_command_is_not_in_presets():
    assert "nie-ma-takiej" not in LiveScene.PRESETS
    assert set(LiveScene.PRESETS) == {"rotate", "pulse", "sweep"}


def test_construct_without_window_raises_before_binding():
    """Kryterium 7: render offline daje czytelny RuntimeError, nie ciche nic."""
    with pytest.raises(RuntimeError, match="trybie okna"):
        LiveScene.construct(SimpleNamespace(window=None))


# --- transport bez okna ----------------------------------------------------


class HeadlessScene(LiveScene):
    """``LiveScene`` bez okna i bez renderowania — do testów samego transportu.

    Pętla odbioru nie dotyka kamery, więc da się ją sprawdzić bez OpenGL.
    Pompowanie klatki zastępuje licznik.
    """

    def __init__(self):
        self.buffer = LineBuffer()
        self.client = None
        self.listener = None
        self.frames = 0
        self.undos = 0
        self.saves = 0
        self.setup()

    def update_frame(self, dt=0, force_draw=False):
        self.frames += 1

    def is_window_closing(self):
        return False

    def emit_frame(self):
        pass

    def get_animation_time_progression(self, animations):
        return [0.1 * (i + 1) for i in range(10)]

    def rewind(self):
        """Animacji cofania nie da sie sprawdzic bez kamery; liczymy wywolania."""
        self.undos += 1

    def save_state(self):
        self.saves += 1


@pytest.fixture
def scene(monkeypatch):
    monkeypatch.setenv("MANIMCUE_PORT", "0")  # port efemeryczny, bez kolizji
    headless = HeadlessScene()
    headless.listener = headless.open_listener()
    yield headless
    headless.close_sockets()


def connect(scene: HeadlessScene) -> socket.socket:
    return socket.create_connection(scene.listener.getsockname(), timeout=5)


def poll_until(scene: HeadlessScene, predicate) -> None:
    """Kręci pętlą odbioru, dopóki warunek nie zajdzie; inaczej pada na asercji."""
    for _ in range(MAX_POLLS):
        if predicate():
            return
        scene.poll_once()
    raise AssertionError("warunek nie zaszedl w MAX_POLLS obrotach petli")


def test_listener_accepts_first_client(scene):
    """Pułapka z SPEC.md: bez accept() na listenerze pętla nie przyjmie nikogo."""
    assert scene.client is None
    with connect(scene) as sock:
        sock.sendall(b"rotate\n")
        assert scene.next_command() == "rotate"
        assert scene.client is not None


def test_two_commands_in_one_recv(scene):
    with connect(scene) as sock:
        sock.sendall(b"rotate\npulse\n")
        assert scene.next_command() == "rotate"
        assert scene.next_command() == "pulse"


def test_split_command_is_reassembled(scene):
    with connect(scene) as sock:
        sock.sendall(b"ro")
        poll_until(scene, lambda: scene.buffer._data == b"ro")
        sock.sendall(b"tate\n")
        assert scene.next_command() == "rotate"


def test_client_disconnect_does_not_end_scene(scene):
    """Kryterium 6 bez okna: EOF rozłącza klienta, scena przyjmuje następnego."""
    with connect(scene) as sock:
        sock.sendall(b"rotate\n")
        assert scene.next_command() == "rotate"
    poll_until(scene, lambda: scene.client is None)
    with connect(scene) as sock:
        sock.sendall(b"pulse\n")
        assert scene.next_command() == "pulse"


def test_second_client_is_rejected(scene):
    with connect(scene) as first:
        first.sendall(b"rotate\n")
        assert scene.next_command() == "rotate"
        with connect(scene) as second:
            scene.poll_once()  # listener przyjmuje i od razu zamyka nadmiarowego
            assert scene.client is not None
            try:
                second.sendall(b"pulse\n")
            except OSError:
                pass  # zamknięte gniazdo może odpowiedzieć RST — tego też oczekujemy
            for _ in range(5):
                scene.poll_once()
            assert not scene.buffer.has_line()
        first.sendall(b"pulse\n")
        assert scene.next_command() == "pulse"


def test_new_client_accepted_while_previous_eof_pending(scene):
    """Regresja: rozlaczony klient nie moze blokowac nastepnego.

    Oba zdarzenia — EOF poprzedniego klienta i nowe polaczenie — czekaja w tym samym
    `select`. Gdy listener jest obslugiwany pierwszy, nowy klient zostaje odrzucony
    przez polaczenie, ktore juz nie zyje, i jego komenda ginie.
    """
    first = connect(scene)
    first.sendall(LINE_ROTATE)
    assert scene.next_command() == "rotate"
    first.close()
    with connect(scene) as second:
        second.sendall(LINE_PULSE)
        poll_until(scene, scene.buffer.has_line)
        assert scene.buffer.pop_line() == "pulse"


def test_idle_loop_waits_on_select(scene):
    """Kryterium 8: bezczynność to klatki w rytm timeoutu, nie busy-loop."""
    rounds = 10
    start = time.monotonic()
    for _ in range(rounds):
        scene.poll_once()
    elapsed = time.monotonic() - start
    assert scene.frames == rounds
    # Gdyby select nie czekał, pętla przeleciałaby w zerowym czasie.
    assert elapsed >= rounds * POLL_TIMEOUT * 0.5


# --- sterowanie strzalkami -------------------------------------------------


def test_arrow_right_walks_the_sequence(scene):
    assert scene.cursor == 0
    assert [scene.advance() for _ in LiveScene.SEQUENCE] == LiveScene.SEQUENCE
    assert scene.cursor == len(LiveScene.SEQUENCE)
    # Za koncem sekwencji strzalka nie wywraca sceny, tylko nic nie robi.
    assert scene.advance() is None
    assert scene.cursor == len(LiveScene.SEQUENCE)


def test_arrow_left_restores_previous_state(scene):
    scene.advance()
    scene.advance()
    assert scene.cursor == 2
    scene.step_back()
    assert scene.cursor == 1
    assert scene.undos == 1
    assert scene.advance() == LiveScene.SEQUENCE[1]


def test_arrow_left_at_start_is_a_no_op(scene):
    scene.step_back()
    assert scene.cursor == 0
    assert scene.undos == 0


def test_key_press_queues_without_touching_manimgl(scene):
    from pyglet.window import key

    scene.on_key_press(key.RIGHT, 0)
    scene.on_key_press(key.LEFT, 0)
    assert list(scene.key_queue) == [KEY_NEXT, KEY_BACK]


def test_keys_take_precedence_over_socket(scene):
    """Prelegent przy maszynie bije zdalna komende, gdy oba czekaja."""
    with connect(scene) as sock:
        sock.sendall(LINE_ROTATE)
        poll_until(scene, scene.buffer.has_line)
        scene.key_queue.append(KEY_NEXT)
        assert scene.next_command() == KEY_NEXT
        assert scene.next_command() == "rotate"


def test_position_hint_names_the_next_cue(scene):
    scene.advance()
    hint = scene.position_hint()
    assert f"1/{len(LiveScene.SEQUENCE)}" in hint
    assert LiveScene.SEQUENCE[1] in hint


def test_non_looping_cue_runs_once(scene):
    calls = []
    scene.run_cue("rotate", lambda _s: calls.append(1))
    assert len(calls) == 1
    assert scene.saves == 0


def test_sequence_history_keeps_equal_positions_bounded_and_clears_redo():
    state = object()
    scene = SimpleNamespace(undo_stack=[], redo_stack=[object()], get_state=lambda: state)
    for _ in range(55):
        LiveScene.save_state(scene)
    assert len(scene.undo_stack) == 50
    assert all(saved is state for saved in scene.undo_stack)
    assert not scene.redo_stack


def test_looping_cue_repeats_until_something_arrives(scene):
    """Jak `next_slide(loop=True)` w manim-slides: przerwanie na koncu powtorzenia."""
    assert "pulse" in LiveScene.LOOPS
    calls = []

    def preset(inner):
        calls.append(1)
        if len(calls) == 3:
            inner.key_queue.append(KEY_NEXT)

    scene.run_cue("pulse", preset)
    assert len(calls) == 3
    assert list(scene.key_queue) == [KEY_NEXT]


def test_looping_cue_breaks_on_socket_command(scene):
    """Petla musi zobaczyc komende z gniazda, choc play() jej nie czytal."""
    calls = []

    def preset(_inner):
        calls.append(1)
        if len(calls) == 2:
            sender.sendall(LINE_ROTATE)

    sender = connect(scene)
    try:
        scene.run_cue("pulse", preset)
    finally:
        sender.close()
    assert len(calls) >= 2
    assert scene.buffer.has_line() or scene.key_queue


# --- przerywalne animacje --------------------------------------------------


class FakeAnimation:
    """Minimalna animacja: liczy klatki, ktore dostala."""

    run_time = 1.0

    def __init__(self):
        self.alphas = []

    def update_mobjects(self, dt):
        pass

    def interpolate(self, alpha):
        self.alphas.append(alpha)


def test_animation_runs_all_frames_when_nothing_waits(scene):
    anim = FakeAnimation()
    scene.progress_through_animations([anim])
    assert len(anim.alphas) == 10
    assert scene.abort_cue is False


def test_animation_breaks_on_queued_key(scene):
    """Kryterium odczucia: klawisz urywa animacje w dowolnej klatce."""
    anim = FakeAnimation()

    class Interrupting(FakeAnimation):
        def interpolate(self, alpha):
            super().interpolate(alpha)
            if len(self.alphas) == 3:
                scene.key_queue.append(KEY_NEXT)

    anim = Interrupting()
    scene.progress_through_animations([anim])
    assert len(anim.alphas) == 3
    assert scene.abort_cue is True


def test_aborted_cue_skips_remaining_plays(scene):
    """Dwuetapowe cue nie gra drugiej polowy po przerwaniu."""
    scene.abort_cue = True
    anim = FakeAnimation()
    scene.progress_through_animations([anim])
    assert anim.alphas == []


def test_run_cue_clears_abort_flag(scene):
    scene.abort_cue = True
    scene.run_cue("rotate", lambda _s: None)
    assert scene.abort_cue is False


def test_socket_preset_does_not_claim_a_sequence_position(scene):
    """D2: preset z gniazda nie przesuwa kursora, wiec nie moze go tez pokazywac."""
    scene.advance()
    assert scene.position_hint() != ""
    assert scene.cue_line("rotate", from_sequence=False) == "Cue: rotate"
    assert "1/" in scene.cue_line("rotate", from_sequence=True)


def test_cue_line_marks_a_looping_cue(scene):
    assert scene.cue_line("pulse", from_sequence=False).endswith("[petla]")
    assert not scene.cue_line("rotate", from_sequence=False).endswith("[petla]")
