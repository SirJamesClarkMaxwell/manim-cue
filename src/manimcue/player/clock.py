"""Wewnętrzny zegar mediów D43, niezależny od czasu rzeczywistego Info."""


def media_time(clock: dict, now: float) -> float:
    """Czas aktywny; pauza nie przesuwa kotwicy mediów."""
    elapsed = max(0.0, now - clock["anchor"]) if clock["playing"] else 0.0
    return clock["position"] + elapsed * clock["rate"]


def set_playing(clock: dict, playing: bool, now: float) -> dict:
    """Zmień stan bez skoku czasu przy wznowieniu."""
    return {**clock, "position": media_time(clock, now), "anchor": now, "playing": playing}


def new_clock(now: float, rate: float = 1.0) -> dict:
    """Nowa, zatrzymana oś czasu przygotowywanego wejścia."""
    return {"anchor": now, "position": 0.0, "rate": rate, "playing": False}
