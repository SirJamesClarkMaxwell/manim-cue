"""Czyste przejścia nawigacji; każdy efekt identyfikuje wejście."""

from .clock import new_clock, set_playing
from .state import snapshot


def _slide(state):
    deck, slide = state["index"]
    return state["manifest"]["presentations"][deck]["slides"][slide]


def _message(state, text, now):
    state["message_revision"] = state.get("message_revision", 0) + 1
    state["message"] = text
    state["message_until"] = now + 2


def _neighbor(state, step):
    decks = state["manifest"]["presentations"]
    deck, slide = state["index"]
    slide += step
    if slide < 0:
        if deck == 0:
            return None
        deck -= 1
        slide = len(decks[deck]["slides"]) - 1
    elif slide >= len(decks[deck]["slides"]):
        if deck + 1 == len(decks):
            return None
        deck, slide = deck + 1, 0
    return [deck, slide]


def _enter(state, index, now, *, reverse=False, preserve_live=False):
    old = state["entry_id"]
    state.update(
        index=index,
        entry_id=old + 1,
        preparing=True,
        requested_playing=True,
        paused=True,
        ended=False,
        reverse=reverse,
        loop_exit_requested=False,
        termination_achieved=False,
        preview=None,
    )
    deck = state["manifest"]["presentations"][index[0]]
    state["resolution"] = deck.get("resolution", state["manifest"]["resolution"])[:]
    slide = _slide(state)
    rate = state.get("playback_rate", 1) * slide.get("reverse_rate" if reverse else "rate", 1)
    state["clock"] = new_clock(now, rate)
    effect = {"type": "prepare", "entry_id": state["entry_id"]}
    if preserve_live:
        effect["preserve_live"] = True
    return [{"type": "cancel", "entry_id": old}, effect]


def reduce(state: dict, event: dict, now: float) -> tuple[dict, list[dict]]:
    """Przejdź po tabeli kontraktu bez efektów ubocznych i bez zegara ściennego."""
    result, effects = snapshot(state), []
    if event.get("entry_id", state["entry_id"]) != state["entry_id"]:
        return result, effects
    action = event["type"]
    if action in ("quit", "close"):
        result["closing"] = True
        effects = [{"type": "begin_shutdown", "entry_id": result["entry_id"]}]
    elif result.get("closing"):
        return result, effects
    elif action == "message_expired":
        if event.get("revision") == result.get("message_revision") and now >= result.get(
            "message_until", 0
        ):
            result["message"] = None
    elif action == "message":
        _message(result, event["text"], now)
    elif action == "ready" and result["preparing"]:
        result["preparing"] = False
        result["paused"] = not result["requested_playing"]
        if not result["paused"]:
            effects.append({"type": "start", "entry_id": result["entry_id"]})
        result["clock"] = set_playing(result["clock"], not result["paused"], now)
    elif action == "pause":
        if result["preparing"]:
            result["requested_playing"] = not result["requested_playing"]
        else:
            result["paused"] = not result["paused"]
            playing = not result["paused"] and not result["ended"]
            result["clock"] = set_playing(result["clock"], playing, now)
            effects.append(
                {"type": "pause" if result["paused"] else "resume", "entry_id": result["entry_id"]}
            )
    elif action in ("previous", "reverse", "replay", "start_at"):
        if action == "replay":
            if result["preparing"]:
                return result, effects
            effects = _enter(result, result["index"], now, reverse=result["reverse"])
        elif action == "start_at":
            decks = result["manifest"]["presentations"]
            deck, slide = event["index"]
            if deck < 0:
                deck += len(decks)
            if not 0 <= deck < len(decks):
                raise ValueError("Niepoprawny indeks prezentacji")
            if slide < 0:
                slide += len(decks[deck]["slides"])
            if not 0 <= slide < len(decks[deck]["slides"]):
                raise ValueError("Niepoprawny indeks slajdu")
            effects = _enter(result, [deck, slide], now)
        else:
            index = _neighbor(result, -1)
            if index is None:
                _message(result, "Początek prezentacji", now)
            else:
                effects = _enter(result, index, now, reverse=action == "reverse")
    elif action in ("eof", "iteration_end") and not result["preparing"]:
        slide = _slide(result)
        looping = slide.get("loop", False) and not result.get("skip_all")
        if action == "iteration_end" and looping and not result.get("loop_exit_requested"):
            result["clock"] = set_playing(
                new_clock(now, result["clock"]["rate"]), not result["paused"], now
            )
            effects = [{"type": "loop", "entry_id": result["entry_id"]}]
        else:
            result.update(ended=True, termination_achieved=True)
            result["clock"] = set_playing(result["clock"], False, now)
            effects = [{"type": "stop_files", "entry_id": result["entry_id"]}]
            if slide.get("auto_next") or result.get("skip_all"):
                next_state, next_effects = reduce(result, {"type": "next"}, now)
                return next_state, effects + next_effects
    elif action == "next":
        if result["preparing"] and not result["requested_playing"]:
            result["requested_playing"] = True
        elif (
            not result["preparing"]
            and result["paused"]
            and not result.get("termination_achieved", result["ended"])
        ):
            result["paused"] = False
            result["clock"] = set_playing(result["clock"], True, now)
            effects = [{"type": "start", "entry_id": result["entry_id"]}]
        elif (
            not result["preparing"]
            and not result["ended"]
            and _slide(result).get("loop")
            and result.get("next_terminates_loop")
            and not result.get("skip_all")
        ):
            result["loop_exit_requested"] = True
        elif result["reverse"] and not result["preparing"]:
            effects = _enter(result, result["index"], now, preserve_live=True)
        else:
            index = _neighbor(result, 1)
            if index is None:
                if result.get("exit_after_last_slide") or result.get("skip_all"):
                    result["closing"] = True
                    effects = [{"type": "begin_shutdown", "entry_id": result["entry_id"]}]
                else:
                    _message(result, "Koniec prezentacji", now)
                    effects = [{"type": "last_slide", "entry_id": result["entry_id"]}]
            else:
                effects = _enter(result, index, now)
    return result, effects
