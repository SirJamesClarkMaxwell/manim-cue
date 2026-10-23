"""Koszt grafu snapshotu CE i pamięć historii po 200 cue, bez renderowania."""

import json
import time
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from manim import RIGHT, Circle, Square, VGroup, tempconfig

from manimcue.live_scene_ce import LiveSceneCE, SnapshotAnimation


def main():
    result = {}
    with tempconfig({"renderer": "cairo", "format": "none", "disable_caching": True}):
        scene = LiveSceneCE()
        child = Square()
        left, right = VGroup(child), VGroup(child, Circle())
        scene.add(left, right)
        scene.live_bootstrap = SimpleNamespace(send=lambda _: None)
        snapshot_times, prepare_times, restore_times = [], [], []
        tracemalloc.start()
        memory = []
        for i in range(200):
            began = time.perf_counter()
            scene.save_state()
            snapshot_times.append(1000 * (time.perf_counter() - began))
            state = scene.undo_stack[-1]
            child.shift(0.01 * RIGHT)
            left.add(Square(0.1))
            began = time.perf_counter()
            animation = SnapshotAnimation(state)
            animation.begin()
            prepare_times.append(1000 * (time.perf_counter() - began))
            animation.finish()
            began = time.perf_counter()
            state.restore(scene)
            restore_times.append(1000 * (time.perf_counter() - began))
            assert left[0] is right[0] is child and len(left) == 1
            if i in (49, 99, 199):
                memory.append(
                    {
                        "cues": i + 1,
                        "current_bytes": tracemalloc.get_traced_memory()[0],
                        "history_entries": len(scene.undo_stack),
                    }
                )
        for name, values in [
            ("snapshot", snapshot_times),
            ("prepare", prepare_times),
            ("restore", restore_times),
        ]:
            result[name] = {
                "median_ms": float(np.median(values)),
                "p95_ms": float(np.percentile(values, 95)),
                "max_ms": max(values),
            }
        result["memory"] = memory
        result["peak_bytes"] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    Path("MEASUREMENT-7a-snapshot.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
