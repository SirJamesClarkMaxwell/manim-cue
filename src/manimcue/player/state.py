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
        "loop_exit_requested": False,
        "termination_achieved": False,
        "resolution": manifest["presentations"][0].get("resolution", manifest["resolution"])[:],
        "preview": None,
        "message_revision": 0,
        "message": None,
        "clock": new_clock(now),
        "presenter_timer": {"anchor": now, "elapsed": 0.0, "paused": False},
        "notes_size": 24,
    }


def snapshot(state: dict) -> dict:
    """Niezależny snapshot prostych danych dla UI i raportu stanu.

    Manifest jest tylko do odczytu, więc snapshot go współdzieli; jego głęboka kopia
    w każdym ticku kosztowała ok. 2 ms pętli UI.
    """
    result = deepcopy({key: value for key, value in state.items() if key != "manifest"})
    if "manifest" in state:
        result["manifest"] = state["manifest"]
    return result
