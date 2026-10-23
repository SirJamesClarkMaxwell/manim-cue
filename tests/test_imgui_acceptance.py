"""Instrumentacja odbioru D48: rzeczywiste okno, kompozycja i swap, bez zaliczania READY."""

import json
import os
import time
from pathlib import Path

import pytest


@pytest.mark.gpu
@pytest.mark.parametrize("engine", ["manimgl", "ce-cairo"])
@pytest.mark.parametrize("prefetch_enabled", [False, True])
def test_d48_window_measurement(monkeypatch, tmp_path, engine, prefetch_enabled):
    """Claude uruchamia przy odblokowanym ekranie; 10+100 wejść w trzech seriach."""
    from manimcue.player import desktop
    from manimcue.player.app import App
    from manimcue.player.manifest import model_to_manifest
    from manimcue.slides.config import PresentationConfig

    psutil = pytest.importorskip("psutil")
    deck = Path(os.environ.get("MANIMCUE_D48_DECK", "slides/Demo.json"))
    manifest = model_to_manifest([PresentationConfig.from_file(deck)])
    presentation = manifest["presentations"][0]
    original = next(
        slide
        for slide in presentation["slides"]
        if any(
            layer["kind"] == "live" and layer.get("engine", "manimgl") == engine
            for layer in slide.get("layers", [])
        )
    )
    # Każdy next ma nową scenę, bez długiego enter_cue i bez przejęcia D39.
    slide = {
        **original,
        "loop": False,
        "auto_next": False,
        "layers": [
            {**layer, "session_id": None, "enter_cue": None}
            for layer in original.get("layers", [])
            if layer["kind"] != "live" or layer.get("engine", "manimgl") == engine
        ],
    }
    if os.environ.get("MANIMCUE_D48_FULL_LOAD") == "1":
        clip = next(
            layer
            for current in presentation["slides"]
            for layer in current.get("layers", [])
            if layer["kind"] == "video"
        )
        slide["layers"] = [
            *slide["layers"],
            *[{**clip, "loop": True, "rect": [0.02 + i * 0.32, 0.55, 0.3, 0.4]} for i in range(3)],
        ]
    presentation["slides"] = [slide.copy() for _ in range(24)]
    output = Path(os.environ.get("MANIMCUE_D48_OUTPUT", ".tmp/d48"))
    output.mkdir(parents=True, exist_ok=True)
    for series in range(3):
        records = []

        class MeasuredApp(App):
            measurements = records
            series_index = series

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.measure_pending = None
                self.measure_next_at = time.monotonic() + 1
                self.measure_started = time.monotonic()

            def tick(self, now, process_input=None):
                if now - self.measure_started > 600:
                    self.dispatch({"type": "quit"}, now)
                    raise TimeoutError("Próba D48 przekroczyła 600 s")
                if (
                    not self.state["preparing"]
                    and self.measure_pending is None
                    and now >= self.measure_next_at
                ):
                    if len(self.measurements) == 110:
                        self.dispatch({"type": "quit"}, now)
                    elif (
                        all(w.ready for w in self.live_pool.workers)
                        and len(self.live_pool.workers) == 2
                    ):
                        if self.state["index"][1] == 23:
                            self.dispatch({"type": "start_at", "index": [0, 0]}, now)
                            self.measure_next_at = now + 0.5
                        else:
                            hits, misses = self.live_pool.hits, self.live_pool.misses
                            prefetched = self.prefetch.hits if self.prefetch else 0
                            self.dispatch({"type": "next"}, now)
                            self.measure_pending = (
                                self.state["entry_id"],
                                now,
                                hits,
                                misses,
                                prefetched,
                            )
                self.thumbnail_indices = list(range(24))
                return super().tick(now, process_input)

            def after_render(self):
                super().after_render()
                if (
                    self.measure_pending
                    and not self.state["preparing"]
                    and all(not session._outgoing for session in self.live.sessions.values())
                ):
                    entry, accepted, hits, misses, prefetched = self.measure_pending
                    assert entry == self.state["entry_id"] and not self.live.failed
                    assert all(str(i) in self.stage_frames for i in self.live.sessions)
                    now = time.monotonic()
                    counts = self.live_pool.budget.snapshot()
                    rss = {
                        role: 0
                        for role in (
                            "scene",
                            "preview",
                            "prefetch",
                            "thumbnail",
                            "idle",
                            "retiring",
                        )
                    }
                    for pid, process in self.live_pool.budget.processes.items():
                        if process.exitcode is None:
                            try:
                                role = (
                                    "retiring"
                                    if pid in self.live_pool.budget.retiring
                                    else self.live_pool.budget.roles[pid]
                                )
                                rss[role] += psutil.Process(pid).memory_info().rss
                            except psutil.NoSuchProcess:
                                pass
                    self.measurements.append(
                        {
                            "event": "live_entry",
                            "time": now,
                            "accepted": accepted,
                            "elapsed_ms": (now - accepted) * 1000,
                            "engine": engine,
                            "series": self.series_index,
                            "warmup": len(self.measurements) < 10,
                            "prefetch_enabled": prefetch_enabled,
                            "pool_hit": self.live_pool.hits > hits,
                            "cold_fallback": self.live_pool.misses > misses,
                            "prefetch_hit": bool(self.prefetch and self.prefetch.hits > prefetched),
                            "process_counts": counts,
                            "rss_bytes": rss,
                            "vram_bytes": None,
                        }
                    )
                    assert counts["total"] <= counts["limit"]
                    self.measure_pending = None
                    self.measure_next_at = now + 0.5

        monkeypatch.setattr(desktop, "App", MeasuredApp)
        path = output / f"{engine}-prefetch-{int(prefetch_enabled)}-series-{series + 1}.jsonl"
        try:
            desktop.run_desktop(
                manifest, {"prefetch": prefetch_enabled, "hide_info_window": "never"}
            )
        finally:
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records), encoding="utf8"
            )
        assert len(records) == 110, f"Niepełny pomiar: {path}"


def test_d48_measure_excludes_warmup_and_cold(tmp_path):
    import importlib.util

    path = Path(__file__).parents[1] / "experiments/f10a_gate/measure.py"
    spec = importlib.util.spec_from_file_location("d48_measure", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    record = {
        "event": "live_entry",
        "time": 1,
        "engine": "ce-cairo",
        "series": 0,
        "warmup": False,
        "prefetch_enabled": False,
        "elapsed_ms": 100,
        "cold_fallback": False,
        "pool_hit": True,
        "prefetch_hit": False,
        "process_counts": {"total": 7},
        "rss_bytes": {"idle": 100},
        "vram_bytes": None,
    }
    trace = tmp_path / "trace.jsonl"
    rows = [record.copy() for _ in range(100)]
    rows.append({**record, "warmup": True, "elapsed_ms": 5000})
    trace.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf8")
    stats = next(iter(module.measure({"trace": trace})["live_entries"].values()))
    assert stats["count"] == 100 and stats["p95_ms"] == 100 and stats["passes_latency"]
    rows.append({**record, "cold_fallback": True, "elapsed_ms": 900})
    trace.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf8")
    stats = next(iter(module.measure({"trace": trace})["live_entries"].values()))
    assert stats["cold_ms"] == [900] and stats["p95_ms"] == 100
    assert not stats["passes_latency"] and not stats["vram_measured"]
