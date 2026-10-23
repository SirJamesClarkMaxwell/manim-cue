"""Pula importów live i wspólna nieblokująca admisja procesów PC."""

import multiprocessing as mp
import time
from dataclasses import dataclass


class ProcessBudget:
    """Slot pozostaje zajęty aż do potwierdzonego exit procesu."""

    def __init__(self, limit=1):
        self.limit = limit
        self.target = limit
        self.processes = {}
        self.roles = {}
        self.stoppers = {}
        self.retiring = set()
        self.pending = 0
        self.reclaimers = {}

    def configure(self, limit):
        self.target = limit
        self.limit = max(self.limit, limit) if self.processes else limit

    def try_acquire(self, role: str) -> bool:
        if len(self.processes) + self.pending >= self.limit:
            priorities = {"scene": 0, "preview": 1, "prefetch": 2, "thumbnail": 3, "idle": 4}
            for name in sorted(self.reclaimers, key=lambda r: priorities[r], reverse=True):
                if priorities[name] > priorities[role]:
                    self.reclaimers[name]()
            for pid in sorted(
                self.stoppers, key=lambda pid: priorities[self.roles[pid]], reverse=True
            ):
                if priorities[self.roles[pid]] > priorities[role]:
                    self.stoppers[pid]()
            return False
        self.pending += 1
        return True

    def register(self, process, role="scene", stop=None):
        self.pending -= 1
        self.processes[process.pid] = process
        self.assign(process.pid, role, stop)

    def assign(self, pid, role, stop):
        self.roles[pid] = role
        if stop is not None:
            self.stoppers[pid] = stop

    def mark_retiring(self, pid):
        self.retiring.add(pid)

    def snapshot(self):
        counts = {
            role: 0 for role in ("scene", "preview", "prefetch", "thumbnail", "idle", "retiring")
        }
        for pid, process in self.processes.items():
            if process.exitcode is None:
                counts["retiring" if pid in self.retiring else self.roles[pid]] += 1
        return {**counts, "total": sum(counts.values()), "limit": self.limit}

    def abort(self):
        self.pending -= 1

    def release_after_exit(self, pid: int) -> None:
        process = self.processes.get(pid)
        if process is not None and process.exitcode is not None:
            del self.processes[pid]
            self.roles.pop(pid, None)
            self.stoppers.pop(pid, None)
            self.retiring.discard(pid)
        if len(self.processes) + self.pending <= self.target:
            self.limit = self.target


def deck_resources(slides):
    """Manifest PC: pułap D48 oraz silniki bez importowania backendów."""
    maximum = preview = 0
    engines = set()
    for slide in slides:
        media = [slide, *slide.get("layers", [])]
        maximum = max(
            maximum, sum(m.get("kind") in ("live", "video", "gif", "image") for m in media)
        )
        preview = max(
            preview,
            sum(
                m.get("kind") in ("video", "gif", "image") or bool(m.get("thumbnail"))
                for m in media
            ),
        )
        engines.update(m.get("engine", "manimgl") for m in media if m.get("kind") == "live")
    return 3 * maximum + preview + 5 + 2 * len(engines), engines


@dataclass
class WarmWorker:
    process: object
    control: object
    bootstrap: object
    frame_lock: object
    engine: str
    began: float
    ready: bool = False
    stopping: float | None = None
    failed: bool = False


def run_pooled_live(engine, frame_lock, control, bootstrap_sender):
    """Import bez sceny i GPU; kanały i SemLock pochodzą wyłącznie ze spawn."""
    import sys

    from manimcue.live_worker import run_worker

    sys.argv = [sys.argv[0]]
    try:
        if engine == "manimgl":
            import pyglet

            pyglet.options["shadow_window"] = False
            import manimlib  # noqa: F401
        else:
            import manimcue.live_scene_ce  # noqa: F401
        bootstrap_sender.send("POOL_READY")
        parent = mp.parent_process()
        while parent is None or parent.is_alive():
            if control.poll(0.25):
                request = control.recv()
                if request is not None:
                    spec, shm_name = request
                    run_worker(spec, shm_name, frame_lock, bootstrap_sender)
                break
    except (EOFError, BrokenPipeError, OSError):
        pass
    except Exception as error:  # noqa: BLE001 — diagnoza bootstrapu
        bootstrap_sender.send(f"POOL_ERROR {type(error).__name__}: {error}")
    finally:
        control.close()
        bootstrap_sender.close()


class LivePool:
    """Dwa jednorazowe sloty na silnik; najwyżej jeden import zapasu naraz."""

    def __init__(self, budget=None):
        self.budget = budget or ProcessBudget(64)
        self.engines = set()
        self.workers = []
        self.failures = {}
        self.errors = []
        self.closing = False
        self.hits = self.misses = 0
        self.budget.reclaimers["idle"] = self.retire_idle

    def configure(self, engines: set[str]) -> None:
        self.engines = set(engines)
        for worker in self.workers:
            if worker.engine not in engines:
                self._stop(worker)

    def _spawn(self, engine, role):
        if self.closing or not self.budget.try_acquire(role):
            return None
        control = child = bootstrap = sender = None
        try:
            ctx = mp.get_context("spawn")
            control, child = ctx.Pipe()
            bootstrap, sender = ctx.Pipe(duplex=False)
            lock = ctx.Lock()
            process = ctx.Process(target=run_pooled_live, args=(engine, lock, child, sender))
            process.start()
        except Exception:
            self.budget.abort()
            for connection in (control, bootstrap):
                if connection is not None:
                    connection.close()
            raise
        finally:
            for connection in (child, sender):
                if connection is not None:
                    connection.close()
        worker = WarmWorker(process, control, bootstrap, lock, engine, time.monotonic())
        self.budget.register(process, role, lambda: self._stop(worker))
        return worker

    def take(self, engine: str, role="scene") -> WarmWorker | None:
        for worker in self.workers:
            if (
                worker.engine == engine
                and worker.ready
                and worker.stopping is None
                and worker.process.exitcode is None
            ):
                self.workers.remove(worker)
                self.hits += 1
                return worker
        worker = self._spawn(engine, role)
        self.misses += worker is not None
        return worker

    def _stop(self, worker, *, failed=False):
        worker.failed |= failed
        if worker.stopping is None:
            worker.stopping = time.monotonic() + 2
            self.budget.mark_retiring(worker.process.pid)
            worker.control.close()

    def retire_idle(self):
        for worker in self.workers:
            self._stop(worker)

    def poll(self, now: float) -> None:
        for worker in list(self.workers):
            if worker.stopping is None:
                try:
                    while worker.bootstrap.poll(0):
                        message = worker.bootstrap.recv()
                        if message == "POOL_READY":
                            worker.ready = True
                        else:
                            self.errors.append(str(message))
                            self._stop(worker, failed=True)
                except (EOFError, OSError):
                    self._stop(worker, failed=True)
                if not worker.ready and now - worker.began > 5:
                    self.errors.append(f"Timeout importu {worker.engine}")
                    self._stop(worker, failed=True)
            if worker.stopping is not None and now >= worker.stopping and worker.process.is_alive():
                worker.process.kill()
            if worker.process.exitcode is not None:
                if not self.closing and worker.engine in self.engines and worker.failed:
                    self.failures[worker.engine] = self.failures.get(worker.engine, 0) + 1
                self.budget.release_after_exit(worker.process.pid)
                worker.process.join(0)
                worker.process.close()
                worker.control.close()
                worker.bootstrap.close()
                self.workers.remove(worker)
        if self.closing or any(not w.ready and w.stopping is None for w in self.workers):
            return
        for engine in sorted(self.engines):
            if self.failures.get(engine, 0) >= 2:
                continue
            if sum(w.engine == engine for w in self.workers) < 2:
                try:
                    worker = self._spawn(engine, "idle")
                except (OSError, MemoryError) as error:
                    self.errors.append(f"Start {engine}: {error}")
                    self.failures[engine] = self.failures.get(engine, 0) + 1
                    return
                if worker:
                    self.workers.append(worker)
                break

    def begin_shutdown(self) -> None:
        self.closing = True
        self.retire_idle()

    @property
    def closed(self):
        return self.closing and not self.workers
