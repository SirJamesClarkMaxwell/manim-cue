"""Wspólny stan wejścia; snapshot nie udostępnia mutowalnego stanu kontrolera."""

from copy import deepcopy

from .clock import new_clock


def initial_state(manifest: dict, now: float = 0.0) -> dict:
    """Stan pierwszego wejścia przed przygotowaniem źródeł."""
    return {
        "manifest": manifest,
        "index": [0, 0],
        "entry_id": 1,
        "preparing": True,
        "requested_playing": False,
        "paused": True,
        "ended": False,
        "reverse": False,
        "clock": new_clock(now),
    }


def snapshot(state: dict) -> dict:
    """Niezależny snapshot prostych danych dla UI i raportu stanu."""
    return deepcopy(state)
