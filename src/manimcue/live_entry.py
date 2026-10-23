"""Historia zatwierdzonych wejść jednej generacji, bez Qt i Manima."""

from dataclasses import dataclass
from urllib.parse import quote, unquote
from uuid import uuid4


@dataclass
class Entry:
    key: object
    checkpoint: str | None
    cue: str | None
    valid: bool = True
    cue_state: str = "prepared"
    cue_request: str | None = None
    has_predecessor: bool = False


class EntryHistory:
    """Nawigacja i wysyłka mają osobne pozycje; stare wyniki nie zmieniają bieżącej."""

    def __init__(self):
        self.generation = "g" + uuid4().hex
        self.counter = 0
        self.request = 0
        self.stack = []
        self.outgoing = []
        self.expected = None
        self.boundaries = {}
        self.held = None
        self.received = set()
        self.completed = None
        self.started_restore = None
        self.reserved = False
        self.status = "nowa sesja, bez historii wcześniejszych wejść"
        self.degraded = None
        self.deadline = 0
        self.drops = []
        self.pending_start = None
        self.result_status = ""
        self.operation_valid = True
        self.reservation_checkpoint = None

    def command(self, operation, checkpoint, *args):
        self.request += 1
        if operation == "enter":
            args = (quote(args[0], safe=""),)
        self.outgoing.append(" ".join((operation, str(self.request), checkpoint, *args)))
        return str(self.request)

    def prepare(self, key, cue, reason, now):
        if reason == "start_at":
            checkpoints = {entry.checkpoint for entry in self.stack if entry.checkpoint}
            self.stack.clear()
            self.outgoing.clear()
            self.drops.clear()
            self.expected = self.pending_start = self.started_restore = None
            self.held = None
            self.boundaries.clear()
            for checkpoint in checkpoints:
                self.command("drop_checkpoint", checkpoint)
        cancelled = bool(self.stack and self.stack[-1].cue_state == "prepared" and self.reserved)
        if self.stack and self.stack[-1].cue_state == "prepared":
            self.stack[-1].cue_state = "unsent"
        self.completed = None
        self.pending_start = None
        self.received.clear()
        self.reserved = True
        self.deadline = now + 5
        if reason in ("previous", "reverse") and self.stack and self.stack[-1].has_predecessor:
            source = self.stack.pop()
            if not self.stack:
                self.stack.append(Entry(key, None, cue, source.valid))
            self.drops.append(source.checkpoint)
            operation, checkpoint = "restore", source.checkpoint
            self.operation_valid = source.valid
            self.status = f"przywracanie stanu pozostawionego na {key[1] + 1}"
            self.result_status = f"przywrócono stan pozostawiony na {key[1] + 1}"
            play_cue = None
        elif reason == "replay" and self.stack:
            operation, checkpoint = "restore", self.stack[-1].checkpoint
            self.operation_valid = self.stack[-1].valid
            self.status = f"replay: przywracanie początku {key[1] + 1}"
            self.result_status = f"przywrócono początek {key[1] + 1}"
            play_cue = cue
        elif reason in ("previous", "reverse") and self.stack:
            self.expected = None
            self.reserved = False
            self.degraded = "stan live nieprzywrócony: brak wcześniejszego wejścia"
            self.stack[:] = [Entry(key, None, cue, False)]
            return None
        else:
            self.counter += 1
            checkpoint = f"{self.generation}_e{self.counter}"
            self.operation_valid = self.degraded is None
            self.stack.append(
                Entry(key, checkpoint, cue, self.operation_valid, has_predecessor=bool(self.stack))
            )
            # Same identyfikatory nie zatrzymują grafów; tyle samo co limit workera.
            self.stack[:] = self.stack[-50:]
            operation = "checkpoint"
            self.status = "zapis stanu wejścia"
            self.result_status = "checkpoint gotowy" + (
                " · nowa sesja, bez historii wcześniejszych wejść" if len(self.stack) == 1 else ""
            )
            play_cue = cue if reason in ("next", "auto_next", "skip_all") else None
        if checkpoint is None:
            self.expected = None
            self.reserved = False
            self.degraded = "stan live nieprzywrócony: brak checkpointu tego wejścia"
            return None
        if operation == "checkpoint" or reason == "replay":
            self.stack[-1].cue_state = "prepared" if play_cue is not None else "skipped"
        if cancelled:
            self.status += " · wejście anulowane, cue niewysłane"
        request = self.command(operation, checkpoint)
        self.reservation_checkpoint = checkpoint
        self.expected = (request, checkpoint)
        return play_cue

    def accept(self, event):
        fields = event.split()
        if fields[0] in ("ENTRY_CUE_START", "ENTRY_CUE_DONE") and len(fields) == (
            4 if fields[0] == "ENTRY_CUE_START" else 6
        ):
            for entry in self.stack:
                if entry.checkpoint == fields[2] and entry.cue_request == fields[1]:
                    entry.cue_state = "started" if fields[0] == "ENTRY_CUE_START" else fields[4]
        if fields[0] == "BOUNDARY" and len(fields) == 3:
            self.boundaries[int(fields[2])] = fields[1]
        elif fields[0] in ("CHECKPOINT_READY", "RESTORE_DONE") and len(fields) == 4:
            if tuple(fields[1:3]) == self.expected:
                self.completed = int(fields[3])
        elif fields[0] == "RESTORE_START" and len(fields) == 3:
            if tuple(fields[1:3]) == self.expected:
                self.started_restore = fields[1]
        elif fields[0] in ("LOOP_WAIT", "CUE_INTERRUPTED") and len(fields) == 3:
            if tuple(fields[1:3]) == self.expected:
                self.status = (
                    "oczekiwanie na koniec powtórzenia live"
                    if fields[0] == "LOOP_WAIT"
                    else "cue przerwane i domknięte"
                )
        elif fields[0] == "CHECKPOINT_ERROR" and len(fields) == 4:
            if tuple(fields[1:3]) == self.expected:
                self.degraded = f"stan live nieprzywrócony: {fields[3]}"
                self.expected = None
                self.reserved = False
                self.completed = None
                for checkpoint in self.drops:
                    if checkpoint:
                        self.command("drop_checkpoint", checkpoint)
                self.drops.clear()
            elif tuple(fields[1:3]) == self.pending_start:
                self.degraded = f"stan live nieprzywrócony: cue niewysłane ({fields[3]})"
                self.stack[-1].cue_state = "error"
                request = self.command("release", self.stack[-1].checkpoint)
                self.pending_start = (request, self.stack[-1].checkpoint)
        elif fields[0] == "ENTRY_CUE_START" and len(fields) == 4:
            if tuple(fields[1:3]) == self.pending_start:
                self.reserved = False
                self.stack[-1].cue_state = "started"
                self.status = f"start cue {unquote(fields[3])}"
        elif fields[0] == "ENTRY_RELEASED" and len(fields) == 3:
            if tuple(fields[1:3]) == self.pending_start:
                self.reserved = False
        elif (
            fields[0] == "ENTRY_CUE_DONE"
            and len(fields) == 6
            and tuple(fields[1:3]) == self.pending_start
        ):
            self.stack[-1].cue_state = fields[4]
            self.status = (
                f"koniec cue {unquote(fields[3])}"
                if fields[4] == "completed"
                else f"cue {unquote(fields[3])} przerwane i domknięte"
            )

    @property
    def waiting(self):
        return self.expected is not None and (
            self.completed is None or self.completed not in self.received
        )

    def finish(self):
        if self.expected and not self.waiting:
            self.expected = None
            self.degraded = (
                None
                if self.operation_valid
                else "stan live nieprzywrócony: checkpoint po rozbieżności"
            )
            self.status = self.result_status
            for checkpoint in self.drops:
                if checkpoint:
                    self.command("drop_checkpoint", checkpoint)
            self.drops.clear()
