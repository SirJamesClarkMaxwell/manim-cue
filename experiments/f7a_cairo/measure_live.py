"""Pełny tor CE → SHM → Qt; trzy niezależne okna 30 s w zmienionej kolejności."""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import psutil
from qtpy.QtGui import QImage, QPixmap
from qtpy.QtWidgets import QApplication, QLabel

from manimcue.live_session import LiveSession, LiveSpec

ROOT = Path(__file__).resolve().parents[2]


def measure(app, width, height, scene_name="MeasurePanel"):
    session = LiveSession()
    began = time.monotonic()
    session.start(
        LiveSpec(
            str(ROOT / "tests/scenes/live_ce_extra.py"),
            scene_name,
            width,
            height,
            engine="ce-cairo",
        )
    )
    label = QLabel()
    result = {"width": width, "height": height}
    samples, copies, qt_times = [], [], []
    previous = None
    ready = None
    window = None
    first_id = None
    last_id = None
    sent = False
    end = None
    idle_cpu = None
    process = None
    latency = None

    def tick():
        nonlocal previous, ready, window, first_id, last_id, sent, end, idle_cpu, process, latency
        now = time.monotonic()
        events = session.poll()
        if session.error:
            result["error"] = session.error
            app.quit()
            return
        if "READY" in events:
            ready = now
            result["cold_start_s"] = now - began
            process = psutil.Process(session._process.pid)
            process.cpu_percent(None)
        before = time.perf_counter()
        frame = session.try_read_frame()
        copied = time.perf_counter()
        if frame is not None:
            image = QImage(frame.pixels, width, height, width * 4, QImage.Format.Format_RGBA8888)
            label.setPixmap(QPixmap.fromImage(image))
            received = time.monotonic()
            if sent and latency is None and not frame.boundary:
                latency = (received - end) * 1000
            if window is not None and received < window + 30:
                if first_id is None:
                    first_id = frame.frame_id
                last_id = frame.frame_id
                samples.append((received, frame.timestamp, frame.pixels != previous))
                copies.append((copied - before) * 1000)
                qt_times.append((time.perf_counter() - copied) * 1000)
            previous = frame.pixels
        if ready is not None and not sent and now - ready > 2:
            idle_cpu = process.cpu_percent(None)
            session.send("next")
            sent = True
            end = now
        if sent and window is None and now - end > 2:
            window = now
        if window is not None and now >= window + 30:
            duration = 30
            result.update(
                received=len(samples),
                different=sum(s[2] for s in samples),
                fps=sum(s[2] for s in samples) / duration,
                published_span=last_id - first_id + 1 if first_id else 0,
                idle_cpu_one_core_percent=idle_cpu,
                first_motion_latency_ms=latency,
                window_s=duration,
                copy_ms={
                    "median": float(np.median(copies)),
                    "p95": float(np.percentile(copies, 95)),
                },
                qt_ms={
                    "median": float(np.median(qt_times)),
                    "p95": float(np.percentile(qt_times, 95)),
                },
                receive_gap_max_ms=max(np.diff([s[0] for s in samples])) * 1000,
                gaps_over_25ms=int(sum(np.diff([s[0] for s in samples]) > 0.025)),
                timestamps=[[s[0] - window, s[1] - window, s[2]] for s in samples],
            )
            app.quit()

    try:
        # Jak w pomiarze F2: Python sleep ma na Windows precyzyjniejszy timer niż Qt offscreen.
        while "fps" not in result and "error" not in result:
            tick()
            app.processEvents()
            time.sleep(0.001)

        # Pomiar komend w ciepłej, statycznej sesji, po zamknięciu okna fps.
        latest_pixels = [previous]

        def drain_until(predicate, timeout=3):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                events = session.poll()
                frame = session.try_read_frame()
                if frame is not None:
                    latest_pixels[0] = frame.pixels
                if predicate(events, frame):
                    return frame
                app.processEvents()
                time.sleep(0.001)
            raise RuntimeError("Timeout sondy latencji")

        session.send("next")
        drain_until(lambda events, frame: "SEQUENCE_END" in events)
        latencies = []
        for _ in range(20):
            before_pixels = latest_pixels[0]
            before = time.monotonic()
            session.send("motion")
            drain_until(
                lambda events, frame, before_pixels=before_pixels: (
                    frame is not None and frame.pixels != before_pixels
                )
            )
            latencies.append((time.monotonic() - before) * 1000)
            session.send("next")
            drain_until(lambda events, frame: "SEQUENCE_END" in events)
        result["command_latency_ms"] = latencies
        result["command_latency_p95_ms"] = float(np.percentile(latencies, 95))
    finally:
        session.request_stop()
        deadline = time.monotonic() + 4
        while session.running and time.monotonic() < deadline:
            session.poll()
            time.sleep(0.002)
        result["worker_metrics"] = session._metrics
        label.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default="MeasurePanel")
    parser.add_argument("--output", type=Path, default=ROOT / "MEASUREMENT-7a.json")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    sizes = [(960, 540), (480, 270), (538, 648)]
    results = []
    target = args.output
    for run in range(3):
        for width, height in sizes[run:] + sizes[:run]:
            row = measure(app, width, height, args.scene)
            row["scene"] = args.scene
            row["run"] = run + 1
            results.append(row)
            target.write_text(json.dumps(results, indent=2), encoding="utf-8")
            print(
                {k: v for k, v in row.items() if k not in ("timestamps", "worker_metrics")},
                flush=True,
            )


if __name__ == "__main__":
    main()
