"""Kontroler live bez Qt; historia i transport pozostają wspólne z playerem Qt."""

import time
from pathlib import Path

from manimcue.live_entry import EntryHistory
from manimcue.live_session import LiveSession, LiveSpec


class LiveController:
    """Oddziela kopiowanie klatki od akceptacji trwałego zasobu kompozycji."""

    def __init__(self, session_factory=LiveSession):
        self.session_factory = session_factory
        self.sessions = {}
        self.identities = {}
        self.histories = {}
        self.cues = {}
        self.frames = {}
        self.leases = {}
        self.restore_resources = {}
        self.pending = {}
        self.stopping = []
        self.failed = {}
        self.started = {}
        self.start_deadlines = {}
        self.frame_deadlines = {}
        self.entry = None
        self.active = None
        self.closing = False
        self.files_ready = False
        self.started_group = False
        self.events = []

    def enter(self, entry: dict) -> None:
        """Przejmiij zgodne sąsiednie sesje; nowe wejście rezerwuje checkpoint."""
        if self.closing:
            return
        now = entry.get("now", time.monotonic())
        old_entry = self.entry
        self.entry = dict(entry)
        self.files_ready = False
        self.started_group = False
        self.deadline = now + 5
        self.frame_deadlines.clear()
        self.start_deadlines.clear()
        self.active = None
        old = dict(self.sessions)
        identities = dict(self.identities)
        for session, frame in self.pending.items():
            if frame.boundary:
                session.send(f"frame_seen {frame.frame_id}")
        self.events = []
        self.sessions, self.identities, self.cues, self.pending, self.failed = {}, {}, {}, {}, {}
        same = old_entry and old_entry["index"] == entry["index"]
        adjacent = (
            old_entry
            and old_entry["index"][0] == entry["index"][0]
            and abs(old_entry["index"][1] - entry["index"][1]) == 1
        )
        for index, layer in enumerate(entry["slide"].get("layers", [])):
            if layer["kind"] != "live":
                continue
            width = max(1, round(entry["resolution"][0] * layer.get("rect", [0, 0, 1, 1])[2]))
            height = max(1, round(entry["resolution"][1] * layer.get("rect", [0, 0, 1, 1])[3]))
            identity = (
                layer.get("session_id"),
                str(Path(layer["scene_file"]).resolve()),
                layer["scene_name"],
                width,
                height,
                layer.get("fps", 60),
                layer.get("background_opacity", 1),
                layer.get("engine", "manimgl"),
            )
            reused = next(
                (
                    i
                    for i, session in old.items()
                    if (same or adjacent)
                    and (same or identity[0] is not None)
                    and identities[i] == identity
                    and session.state in ("starting", "ready")
                    and not session.stopping
                ),
                None,
            )
            if reused is None:
                session = self.session_factory()
                session.start(
                    LiveSpec(
                        identity[1],
                        identity[2],
                        width,
                        height,
                        identity[5],
                        identity[6],
                        identity[7],
                    )
                )
            else:
                session = old.pop(reused)
            self.sessions[index], self.identities[index] = session, identity
            self.started[index] = now
            if entry.get("preserve_live") and reused is not None:
                continue
            if layer.get("session_id") is not None:
                history = self.histories.setdefault(session, EntryHistory())
                if session in self.restore_resources:
                    self.leases[session], self.frames[session] = self.restore_resources[session]
                if session in self.leases:
                    self.restore_resources.setdefault(
                        session, (self.leases[session], self.frames[session])
                    )
                cue = history.prepare(
                    tuple(entry["index"]),
                    layer.get("enter_cue"),
                    entry.get("reason", "initial"),
                    now,
                )
                if cue:
                    self.cues[index] = cue
            elif entry.get("reason") in ("next", "auto_next", "skip_all", "replay") and layer.get(
                "enter_cue"
            ):
                self.cues[index] = layer["enter_cue"]
        for session in old.values():
            session.request_stop()
            self.stopping.append(session)
            self.histories.pop(session, None)
            self.frames.pop(session, None)
            self.leases.pop(session, None)
            self.restore_resources.pop(session, None)

    def _flush(self, session, history):
        if self.files_ready and session.state == "ready" and not session.stopping:
            outgoing, history.outgoing = history.outgoing, []
            for command in outgoing:
                session.send(command)

    def _fail(self, index, message):
        session = self.sessions[index]
        if self.active == index:
            self.active = None
        self.failed[index] = message
        self.cues.pop(index, None)
        saved = self.restore_resources.pop(session, None)
        if saved:
            self.leases[session], self.frames[session] = saved
            self.events.append(
                {"type": "restore_frame", "index": index, "lease": saved[0], "frame": saved[1]}
            )
        session.request_stop()
        history = self.histories.get(session)
        if history:
            history.degraded = message
            history.expected = None
            history.reserved = False
        self.events.append({"type": "error", "index": index, "error": message})

    def poll(self, now: float) -> list[dict]:
        """Najpierw przyjmij statusy, później kopiuj klatki bez automatycznego ACK."""
        for index, session in self.sessions.items():
            history = self.histories.get(session)
            for event in session.poll():
                if history:
                    correlated = (history.expected, history.pending_start)
                    history.accept(event)
                    if (
                        event.startswith("CHECKPOINT_ERROR ")
                        and history.degraded
                        and tuple(event.split()[1:3]) in correlated
                    ):
                        self._fail(index, history.degraded)
                    else:
                        history.finish()
                        if (
                            correlated[0] is not None
                            and history.expected is None
                            and not history.degraded
                        ):
                            self.restore_resources.pop(session, None)
                if event.startswith("ERROR"):
                    self._fail(index, event)
            if index in self.failed:
                continue
            if session in self.frame_deadlines and now >= self.frame_deadlines[session]:
                self._fail(index, "Timeout upload/ACK 2 s; wynik live nieznany")
                continue
            if (
                not self.started_group
                and now >= self.deadline
                and (session not in self.leases or (history and history.waiting))
            ):
                self._fail(index, "Timeout bariery 5 s; wynik live nieznany")
                continue
            if (
                session in self.start_deadlines
                and history
                and history.reserved
                and now >= self.start_deadlines[session]
            ):
                self._fail(index, "Timeout ACK/start 2 s; wynik live nieznany")
                continue
            if history:
                self._flush(session, history)
        for index, session in self.sessions.items():
            if index in self.failed:
                continue
            history = self.histories.get(session)
            frame = session.try_read_frame(acknowledge=False)
            if frame is not None:
                self.pending[session] = frame
            frame = self.pending.get(session)
            if frame is None:
                continue
            request = history.boundaries.get(frame.frame_id) if history and frame.boundary else None
            if history and frame.boundary and request is None:
                continue
            current_requests = {"0"}
            if history and history.expected:
                current_requests.add(history.expected[0])
            if history and history.pending_start:
                current_requests.add(history.pending_start[0])
            stale = bool(history and frame.boundary and request not in current_requests)
            if stale:
                session.send(f"frame_seen {frame.frame_id}")
                self.pending.pop(session, None)
                continue
            if frame.boundary:
                self.frame_deadlines.setdefault(session, now + 2)
            self.events.append(
                {
                    "type": "frame",
                    "index": index,
                    "frame": frame,
                    "entry_id": self.entry["entry_id"],
                    "session": session,
                    "generation": history.generation if history else id(session),
                    "request_id": request,
                }
            )
        for session in list(self.stopping):
            session.poll()
            frame = session.try_read_frame(acknowledge=False)
            if frame is not None and frame.boundary:
                session.send(f"frame_seen {frame.frame_id}")
            if not session.running:
                self.stopping.remove(session)
        events, self.events = self.events, []
        return events

    def accept_frame(self, frame, lease) -> None:
        """Przypisz gotową teksturę do snapshotu przed ACK i zwolnieniem bariery."""
        if frame["entry_id"] != self.entry["entry_id"]:
            return
        index = frame["index"]
        session = self.sessions.get(index)
        if session is not frame["session"] or lease is None or getattr(lease, "closed", False):
            return
        history = self.histories.get(session)
        if history and frame["generation"] != history.generation:
            return
        owned = frame["frame"]
        self.leases[session] = lease
        self.frames[session] = owned
        self.pending.pop(session, None)
        self.frame_deadlines.pop(session, None)
        self.events.append({"type": "assigned", "index": index, "entry_id": self.entry["entry_id"]})
        if owned.boundary:
            session.send(f"frame_seen {owned.frame_id}")
            if history and history.expected and frame["request_id"] == history.expected[0]:
                history.received.add(owned.frame_id)
                history.boundaries.pop(owned.frame_id, None)
        if history:
            history.finish()
            if not history.waiting:
                self.restore_resources.pop(session, None)

    @property
    def pinned_leases(self):
        """Obraz sprzed restore pozostaje żywy aż do wyniku operacji."""
        if self.closed:
            return []
        return [*self.leases.values(), *(saved[0] for saved in self.restore_resources.values())]

    @property
    def ready(self):
        """Sam READY nie wystarcza: każdy nieuszkodzony live ma zasób i granicę."""
        return self.files_ready and all(
            index in self.failed
            or (
                session in self.leases
                and not getattr(self.leases[session], "closed", False)
                and session.state == "ready"
                and not (self.histories.get(session) and self.histories[session].waiting)
            )
            for index, session in self.sessions.items()
        )

    def start_entries(self, now):
        """Wywołaj dopiero po wspólnym starcie plików; pauza zachowuje rezerwację."""
        if self.started_group or not self.ready or not self.entry.get("requested_playing"):
            return
        self.started_group = True
        for index, session in self.sessions.items():
            if index in self.failed:
                continue
            history = self.histories.get(session)
            if history and history.reserved and history.pending_start is None:
                checkpoint = history.stack[-1].checkpoint or history.reservation_checkpoint
                cue = self.cues.get(index)
                if cue and not history.degraded:
                    request = history.command("enter", checkpoint, cue)
                    history.stack[-1].cue_state = "sent"
                    history.stack[-1].cue_request = request
                else:
                    request = history.command("release", checkpoint)
                history.pending_start = request, checkpoint
                self.start_deadlines[session] = now + 2
                self._flush(session, history)
            elif index in self.cues:
                session.send(self.cues[index])
        self.cues.clear()

    def begin_shutdown(self) -> None:
        """Odłącz bieżący snapshot, pompuj procesy przed zwolnieniem tekstur w GL."""
        self.closing = True
        self.active = None
        for session in self.sessions.values():
            session.request_stop()
            self.stopping.append(session)
        self.sessions = {}

    @property
    def closed(self):
        """Zasoby GL można zwolnić dopiero po odebraniu wszystkich procesów."""
        return self.closing and not self.stopping

    def send(self, command: str, repeat: bool = False):
        """Wyślij cue/view tylko do gotowej, niezarezerwowanej aktywnej sesji."""
        session = self.sessions.get(self.active)
        if session is None or repeat or session.state != "ready" or session.stopping:
            return
        history = self.histories.get(session)
        if history and history.reserved:
            return
        if command.startswith("view ") and self.identities[self.active][-1] == "ce-cairo":
            return
        session.send(command)


def view(event: dict, container: tuple) -> dict:
    """Gesty D28 normalizują przesunięcie przez kontener, także na jego marginesie."""
    if event.get("engine") == "ce-cairo":
        return {}
    gesture = event.get("gesture", event.get("type"))
    if gesture == "double_click":
        return {"command": "view reset"}
    if gesture == "wheel":
        return {"command": f"view zoom {event['steps']:g}"}
    if gesture == "drag" and container[2] > 0 and container[3] > 0:
        dx, dy = event["delta"]
        mode = "pan" if event.get("shift") else "orbit"
        return {"command": f"view {mode} {dx / container[2]:.5f} {dy / container[3]:.5f}"}
    return {}
