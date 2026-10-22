"""Testy akceptacyjne F2 na korpusie scen `tests/scenes/live_gl.py`.

Testy `gpu` uruchamiają prawdziwy manimgl w osobnym procesie bez okna.

Czasy: zdarzenia mierzymy po czasie odbioru w `pump()` (`time.monotonic()` w odbiorniku),
klatki po `OwnedFrame.timestamp` (ten sam zegar na jednej maszynie). Kolory z tolerancją ±40
na kanał. Współrzędne sceny przelicza `to_px`: (0, 0) to środek, y rośnie w górę.
"""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scenes.live_gl import (
    FRAME_HEIGHT,
    FRAME_WIDTH,
    PURE_BLUE,
    PURE_GREEN,
    PURE_RED,
    PURE_WHITE,
)

SCENE_FILE = str(Path(__file__).parent / "scenes" / "live_gl.py")
WIDTH = 960
HEIGHT = 540
READY_TIMEOUT = 30.0
"""Start procesu manimgl z kontekstem GL bywa wolny — pierwszy READY dostaje zapas."""

CUE_TIMEOUT = 15.0
BLACK = "#000000"


# --- helpery ---------------------------------------------------------------


def spec(scene_name: str, **kw: Any) -> Any:
    """`LiveSpec` dla sceny z korpusu."""
    from manimcue.live_session import LiveSpec

    return LiveSpec(scene_file=SCENE_FILE, scene_name=scene_name, **kw)


def to_px(x: float, y: float, w: int = WIDTH, h: int = HEIGHT) -> tuple[int, int]:
    """Współrzędne sceny -> piksel (0, 0) = lewy górny róg."""
    px = (x / FRAME_WIDTH + 0.5) * w
    py = (0.5 - y / FRAME_HEIGHT) * h
    return round(px), round(py)


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def near(rgba: tuple[int, int, int, int], color: str, tol: int = 40) -> bool:
    """Czy piksel jest w kolorze `color` z tolerancją ±tol na kanał."""
    return all(abs(a - b) <= tol for a, b in zip(rgba[:3], hex_to_rgb(color), strict=True))


def as_array(frame: Any) -> np.ndarray:
    """Klatka jako tablica (h, w, 4) uint8."""
    return np.frombuffer(frame.pixels, dtype=np.uint8).reshape(frame.height, frame.width, 4)


def center_row_white_x(frame: Any) -> float | None:
    """Środek w poziomie białych pikseli na wierszu y = 0, we współrzędnych sceny.

    Używane do znalezienia kwadratu/kropki. Próbkujemy co 2 piksele dla szybkości.
    """
    arr = as_array(frame)
    _, row = to_px(0, 0, frame.width, frame.height)
    white = np.where((arr[row, ::2, :3] > 200).all(axis=1))[0] * 2
    if white.size == 0:
        return None
    center_px = (white.min() + white.max()) / 2
    return (center_px / frame.width - 0.5) * FRAME_WIDTH


def pixel_at(frame: Any, x: float, y: float) -> tuple[int, int, int, int]:
    return frame.pixel(*to_px(x, y, frame.width, frame.height))


def names(events: list[tuple[float, str]]) -> list[str]:
    return [name for _, name in events]


def event_time(events: list[tuple[float, str]], name: str) -> float:
    """Czas odbioru pierwszego zdarzenia o tej nazwie."""
    return next(t for t, n in events if n == name)


def last_boundary(frames: list[Any]) -> Any | None:
    boundary = [f for f in frames if f.boundary]
    return boundary[-1] if boundary else None


def _loop(
    session: Any,
    until: Callable[[list, list], bool] | None,
    deadline: float,
) -> tuple[list, list, bool]:
    """Pętla `poll()` + `try_read_frame()`. Zwraca zdarzenia, klatki i czy warunek spełniony."""
    events: list[tuple[float, str]] = []
    frames: list[Any] = []
    while time.monotonic() < deadline:
        now = time.monotonic()
        events.extend((now, name) for name in session.poll())
        frame = session.try_read_frame()
        if frame is not None:
            frames.append(frame)
        if until is not None and until(events, frames):
            return events, frames, True
        time.sleep(0.002)
    return events, frames, until is None


def pump(
    session: Any,
    until: Callable[[list, list], bool],
    timeout: float,
) -> tuple[list[tuple[float, str]], list[Any]]:
    """Pompuje sesję, aż `until(events, frames)` będzie prawdziwe; inaczej porażka z listą zdarzeń.

    Zwraca zdarzenia i klatki z tego wywołania (poprzednie wywołania zwracają swoje).
    """
    events, frames, ok = _loop(session, until, time.monotonic() + timeout)
    if not ok:
        pytest.fail(f"timeout {timeout} s; zdarzenia: {names(events)}; klatek: {len(frames)}")
    return events, frames


def pump_for(session: Any, seconds: float) -> tuple[list[tuple[float, str]], list[Any]]:
    """Pompuje sesję przez ustalony czas, bez warunku."""
    events, frames, _ = _loop(session, None, time.monotonic() + seconds)
    return events, frames


def is_ready(events: list, frames: list) -> bool:
    return "READY" in names(events)


@pytest.fixture
def live():
    """Fabryka sesji. Po teście: request_stop() i dociągnięcie poll() do stanu końcowego."""
    created: list[Any] = []

    def start(scene_name: str, **kw: Any) -> Any:
        from manimcue.live_session import LiveSession

        session = LiveSession()
        session.start(spec(scene_name, **kw))
        created.append(session)
        return session

    yield start

    for session in created:
        session.request_stop()
        deadline = time.monotonic() + 5
        # F2: stan error nie oznacza jeszcze odebrania procesu i zwolnienia IPC.
        while session._process is not None and time.monotonic() < deadline:
            session.poll()
            time.sleep(0.01)


# --- testy ----------------------------------------------------------------


@pytest.mark.gpu
def test_first_frame_size_and_center(live) -> None:
    session = live("LiveGLFirstFrame")
    _, frames = pump(session, lambda ev, fr: is_ready(ev, fr) and len(fr) >= 1, READY_TIMEOUT)

    first = frames[0]
    assert (first.width, first.height) == (WIDTH, HEIGHT)
    assert first.boundary
    assert near(pixel_at(first, 0, 0), PURE_RED)
    assert near(first.pixel(0, 0), BLACK)


@pytest.mark.gpu
def test_corners_orientation(live) -> None:
    session = live("LiveGLCorners")
    _, frames = pump(session, lambda ev, fr: is_ready(ev, fr) and len(fr) >= 1, READY_TIMEOUT)

    frame = frames[-1]
    dx = FRAME_WIDTH / 2 - 1
    dy = FRAME_HEIGHT / 2 - 1
    assert near(pixel_at(frame, -dx, dy), PURE_RED)
    assert near(pixel_at(frame, dx, dy), PURE_GREEN)
    assert near(pixel_at(frame, -dx, -dy), PURE_BLUE)
    assert near(pixel_at(frame, dx, -dy), PURE_WHITE)


@pytest.mark.gpu
def test_five_second_cue(live) -> None:
    session = live("LiveGLMoveFiveSeconds")
    pump(session, is_ready, READY_TIMEOUT)

    session.send("next")
    events, frames = pump(
        session,
        lambda ev, fr: (
            "CUE_DONE move" in names(ev)
            and (b := last_boundary(fr)) is not None
            and abs(center_row_white_x(b) - 4.0) < 0.1
        ),
        CUE_TIMEOUT,
    )

    # Czas cue mierzony odbiorem zdarzeń CUE_START / CUE_DONE w tej samej pompie.
    duration = event_time(events, "CUE_DONE move") - event_time(events, "CUE_START move")
    assert 4.9 <= duration <= 5.2, duration

    # Klatki pośrednie (bez granicznych) pokazują kwadrat między start a koniec.
    intermediate = [center_row_white_x(f) for f in frames if not f.boundary]
    intermediate = [x for x in intermediate if x is not None]
    assert intermediate, "brak klatek pośrednich w trakcie cue"
    assert all(-4.1 < x < 4.1 for x in intermediate)
    assert any(-3.0 < x < 3.0 for x in intermediate)

    final = last_boundary(frames)
    assert abs(center_row_white_x(final) - 4.0) < 0.1


@pytest.mark.gpu
def test_interrupt_final_frame(live) -> None:
    session = live("LiveGLInterruptTwoPlays")
    pump(session, is_ready, READY_TIMEOUT)

    session.send("next")
    pump_for(session, 1.0)

    # Przerwanie w trakcie pierwszego play: CUE_DONE musi przyjść szybko, a klatka graniczna
    # ma być po dokończeniu obu animacji.
    interrupt_sent = time.monotonic()
    session.send("next")
    events, frames = pump(
        session,
        lambda ev, fr: (
            "CUE_DONE two_step" in names(ev)
            and (b := last_boundary(fr)) is not None
            and abs(center_row_white_x(b) - 4.0) < 0.1
        ),
        CUE_TIMEOUT,
    )

    assert event_time(events, "CUE_DONE two_step") - interrupt_sent < 1.0
    assert abs(center_row_white_x(last_boundary(frames)) - 4.0) < 0.1


@pytest.mark.gpu
def test_back_add_remove(live) -> None:
    session = live("LiveGLAddRemoveBack")
    pump(session, is_ready, READY_TIMEOUT)

    session.send("next")
    pump(session, lambda ev, fr: "CUE_DONE swap" in names(ev), CUE_TIMEOUT)

    session.send("back")
    _, frames = pump_for(session, 1.5)  # cofnięcie trwa 0.6 s; zapas na klatkę graniczną

    final = last_boundary(frames)
    assert final is not None
    assert near(pixel_at(final, -3.0, 0), PURE_RED)
    # Po cofnięciu koło w x = +3 ma zniknąć: w środku nie może być niebieskiego.
    assert not near(pixel_at(final, 3.0, 0), PURE_BLUE)


@pytest.mark.gpu
def test_updater_wait(live) -> None:
    session = live("LiveGLUpdaterWait")
    pump(session, is_ready, READY_TIMEOUT)

    session.send("next")
    _, frames = pump(
        session,
        lambda ev, fr: (
            "CUE_DONE wait_two" in names(ev)
            and (b := last_boundary(fr)) is not None
            and abs(center_row_white_x(b) - (-1.0)) < 0.3
        ),
        CUE_TIMEOUT,
    )
    assert abs(center_row_white_x(last_boundary(frames)) - (-1.0)) < 0.3


@pytest.mark.gpu
def test_idle_updater_frozen(live) -> None:
    session = live("LiveGLIdleUpdater")
    _, frames = pump(session, is_ready, READY_TIMEOUT)

    _, more = pump_for(session, 1.0)
    frames += more

    # Bez cue updater nie działa: kropka stoi w x = -3.
    x = center_row_white_x(frames[-1])
    assert x is not None
    assert abs(x - (-3.0)) < 0.2


@pytest.mark.gpu
def test_static_wait_duration(live) -> None:
    session = live("LiveGLStaticWait")
    pump(session, is_ready, READY_TIMEOUT)

    session.send("next")
    events, _ = pump(session, lambda ev, fr: "CUE_DONE pause" in names(ev), CUE_TIMEOUT)

    duration = event_time(events, "CUE_DONE pause") - event_time(events, "CUE_START pause")
    assert 1.4 <= duration <= 1.7, duration


@pytest.mark.gpu
def test_loop_ends_on_boundary(live) -> None:
    session = live("LiveGLLoopBoundary")
    pump(session, is_ready, READY_TIMEOUT)

    session.send("next")
    pump_for(session, 0.5)
    session.send("next")

    # Kwadrat ma być obrócony o wielokrotność 90 stopni: wtedy punkt (0.9, 0.9) leży
    # wewnątrz (biały). Przy kącie pośrednim (np. 45 stopni) leży poza nim (czarny).
    pump(
        session,
        lambda ev, fr: (
            "CUE_DONE spin" in names(ev)
            and (b := last_boundary(fr)) is not None
            and near(pixel_at(b, 0.9, 0.9), PURE_WHITE)
        ),
        CUE_TIMEOUT,
    )


@pytest.mark.gpu
def test_three_d_orbit_changes_view(live) -> None:
    session = live("LiveGLThreeD")
    _, frames = pump(session, is_ready, READY_TIMEOUT)
    start = frames[-1]

    session.send("next")
    _, frames = pump(
        session,
        lambda ev, fr: "CUE_DONE orbit" in names(ev) and last_boundary(fr) is not None,
        CUE_TIMEOUT,
    )
    after = last_boundary(frames)

    changed = np.any(as_array(after)[..., :3] != as_array(start)[..., :3], axis=2).sum()
    assert changed > 0.01 * WIDTH * HEIGHT, changed


@pytest.mark.gpu
@pytest.mark.tex
def test_tex_renders(live) -> None:
    # F2: `latex --version` nie wystarcza — manimgl woła `latex -no-pdf`, a pdfTeX z MiKTeX tej
    # opcji nie przyjmuje. Sonda to ta sama kompilacja, której użyje scena.
    from manimlib.utils.tex_file_writing import LatexError, latex_to_svg

    try:
        latex_to_svg(r"\int_0^1 x\,dx", show_message_during_execution=False)
    except (LatexError, OSError) as exc:
        pytest.skip(f"TeX nie kompiluje dla manimgl: {type(exc).__name__}: {exc}")
    session = live("LiveGLTex")
    _, frames = pump(session, lambda ev, fr: is_ready(ev, fr) and len(fr) >= 1, 120.0)

    arr = as_array(frames[-1])
    x0, y0 = to_px(-1.5, 0.5)
    x1, y1 = to_px(1.5, -0.5)
    region = arr[y0:y1, x0:x1, :3]
    white = (region > 200).all(axis=2).sum()
    assert white > 50, white


@pytest.mark.gpu
def test_slow_build_ready_after_build(live) -> None:
    t0 = time.monotonic()
    session = live("LiveGLSlowBuild")

    slowest = 0.0
    ready_at = None
    deadline = t0 + READY_TIMEOUT
    while ready_at is None and time.monotonic() < deadline:
        began = time.monotonic()
        events = session.poll()
        slowest = max(slowest, time.monotonic() - began)

        began = time.monotonic()
        session.try_read_frame()
        slowest = max(slowest, time.monotonic() - began)

        if "READY" in events:
            ready_at = time.monotonic()
        time.sleep(0.002)

    assert ready_at is not None, "brak READY"
    assert ready_at - t0 >= 3.0, ready_at - t0
    # Podczas budowania sesja nie blokuje GUI: każde wywołanie krótkie.
    assert slowest < 0.05, slowest


@pytest.mark.gpu
def test_cue_raises_reports_error(live) -> None:
    session = live("LiveGLCueRaises")
    pump(session, is_ready, READY_TIMEOUT)

    session.send("next")
    events, _ = pump(
        session,
        lambda ev, fr: any(n.startswith("ERROR") for n in names(ev)),
        CUE_TIMEOUT,
    )

    error = next(n for n in names(events) if n.startswith("ERROR"))
    assert "boom from cue" in error
    assert session.state == "error"
    # Proces nie zostaje w tle: teardown doprowadzi go do stopped albo error.


@pytest.mark.gpu
def test_build_raises_no_false_ready(live) -> None:
    session = live("LiveGLBuildRaises")
    events, _ = pump(
        session,
        lambda ev, fr: any(n.startswith("ERROR") for n in names(ev)),
        READY_TIMEOUT,
    )

    assert "READY" not in names(events)
    error = next(n for n in names(events) if n.startswith("ERROR"))
    assert "boom from build" in error
    assert session.state == "error"
