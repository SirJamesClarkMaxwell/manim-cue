"""Jeden spekulacyjny N+1 na PC; preview i historia nie uczestniczą."""

import time
from dataclasses import replace

from manimcue.live_session import LiveSession, LiveSpec

from .sources_av import Source


def live_spec(layer, resolution, *, prefetch=False):
    rect = layer.get("rect", [0, 0, 1, 1])
    return LiveSpec(
        layer["scene_file"],
        layer["scene_name"],
        max(1, round(resolution[0] * rect[2])),
        max(1, round(resolution[1] * rect[3])),
        layer.get("fps", 60),
        layer.get("background_opacity", 1),
        layer.get("engine", "manimgl"),
        prefetch,
    )


class Prefetch:
    """Własność przechodzi raz; anulowane procesy zajmują slot aż do exit."""

    max_bytes = 128 * 1024 * 1024

    def __init__(self, pool):
        self.pool = pool
        self.token = None
        self.items = {}
        self.retiring = []
        self.failed = None
        self.bytes = 0
        self.hits = 0
        self.pool.budget.reclaimers["prefetch"] = lambda: self.cancel("admission")

    def prepare(self, token: tuple, slide: dict) -> None:
        if token == self.token or token == self.failed:
            return
        self.cancel("replace")
        self.token = token
        self.deadline = time.monotonic() + 5
        resolution = slide["resolution"]
        for key, media in [
            ("base", slide),
            *((str(i), m) for i, m in enumerate(slide.get("layers", []))),
        ]:
            if media["kind"] == "live" and key in slide.get("adjacent", ()):
                continue
            size = resolution[0] * resolution[1] * 4
            spec = None
            if media["kind"] == "live":
                spec = live_spec(media, resolution, prefetch=True)
                size = spec.width * spec.height * 4
            charge = 8 * size + 4096
            if self.bytes + charge > self.max_bytes:
                continue
            self.bytes += charge
            source = LiveSession() if spec else Source()
            item = {"source": source, "ready": False, "charge": charge}
            self.items[key] = item
            try:
                if spec:
                    item["spec"] = replace(spec, prefetch=False)
                    source.start(spec, pool=self.pool)
                else:
                    source.role = "prefetch"
                    source.prepare(0, {**media, "max_frame_bytes": size}, hold_first=True)
            except (OSError, MemoryError, ValueError):
                self.failed = token
                self.cancel("allocation")
                break

    def poll(self, now: float) -> None:
        for item in list(self.retiring):
            source = item["source"]
            if "spec" in item:
                source.poll()
                closed = not source.running
            else:
                closed = source.poll_closed(now)
            if closed:
                self.retiring.remove(item)
                self.bytes -= item["charge"]
        for key, item in list(self.items.items()):
            source = item["source"]
            if "spec" in item:
                events = source.poll()
                if "PREFETCH_HELD" in events:
                    item["ready"] = True
                frame = source.try_read_frame(acknowledge=False)
                if frame is not None and frame.boundary:
                    source.send(f"frame_seen {frame.frame_id}")
                error = source.error or source.stopping or not source.running
            else:
                update = source.poll(now, None, 1)
                item["ready"] = source.held and "rgba" in update
                error = update.get("error") or (source.process is None and not source.waiting_slot)
            if error and "MemoryError:" in str(error):
                del self.items[key]
                if "spec" in item:
                    source.request_stop()
                else:
                    source.request_close()
                self.retiring.append(item)
                continue
            if error or (not item["ready"] and now >= self.deadline):
                self.failed = self.token
                self.cancel("error/timeout")
                break

    def take(self, token: tuple, entry_id: int) -> dict | None:
        if token != self.token or token == self.failed:
            self.cancel("miss")
            return None
        result = {key: item for key, item in self.items.items() if item["ready"]}
        for key, item in result.items():
            del self.items[key]
            self.bytes -= item["charge"]
            source = item["source"]
            self.pool.budget.assign(
                source._process.pid if "spec" in item else source.process.pid,
                "scene",
                source.request_stop if "spec" in item else source.request_close,
            )
            if "spec" not in item:
                item["source"].adopt(entry_id, time.monotonic(), True)
                item["source"].role = "scene"
        self.hits += bool(result)
        self.cancel("take")
        return result

    def cancel(self, reason: str) -> None:
        if reason == "admission" and self.token is not None:
            self.failed = self.token
        for key, item in list(self.items.items()):
            source = item["source"]
            if "spec" in item:
                source.request_stop()
            else:
                source.request_close()
            self.retiring.append(item)
            del self.items[key]
            if reason == "admission":
                return
        self.items = {}
        self.token = None
