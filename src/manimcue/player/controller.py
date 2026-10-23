"""Czysty reducer wejścia; podstawowe przejścia wymagane przez bramkę importów."""

from .clock import new_clock, set_playing
from .state import snapshot


def reduce(state: dict, event: dict, now: float) -> tuple[dict, list[dict]]:
    """Przyjmij zdarzenie tylko aktualnego wejścia i oddaj jawne efekty."""
    if event.get("entry_id", state["entry_id"]) != state["entry_id"]:
        return snapshot(state), []
    result, effects = snapshot(state), []
    action = event["type"]
    if action == "ready" and result["preparing"]:
        result["preparing"] = False
        result["paused"] = not result["requested_playing"]
        if result["requested_playing"]:
            effects.append({"type": "start", "entry_id": result["entry_id"]})
        result["clock"] = set_playing(result["clock"], not result["paused"], now)
    elif action == "pause":
        if result["preparing"]:
            result["requested_playing"] = not result["requested_playing"]
        else:
            result["paused"] = not result["paused"]
            result["clock"] = set_playing(result["clock"], not result["paused"], now)
            effects.append(
                {"type": "pause" if result["paused"] else "start", "entry_id": result["entry_id"]}
            )
    elif action == "next":
        if result["preparing"] and not result["requested_playing"]:
            result["requested_playing"] = True
        elif result["paused"] and not result["preparing"] and not result["ended"]:
            result["paused"] = False
            result["clock"] = set_playing(result["clock"], True, now)
            effects.append({"type": "start", "entry_id": result["entry_id"]})
        else:
            deck, slide = result["index"]
            decks = result["manifest"]["presentations"]
            if slide + 1 < len(decks[deck]["slides"]):
                slide += 1
            elif deck + 1 < len(decks):
                deck, slide = deck + 1, 0
            else:
                return result, [{"type": "last_slide", "entry_id": result["entry_id"]}]
            effects.append({"type": "cancel", "entry_id": result["entry_id"]})
            result.update(
                index=[deck, slide],
                entry_id=result["entry_id"] + 1,
                preparing=True,
                requested_playing=True,
                paused=True,
                ended=False,
                reverse=False,
                clock=new_clock(now),
            )
            effects.append({"type": "prepare", "entry_id": result["entry_id"]})
    return result, effects
