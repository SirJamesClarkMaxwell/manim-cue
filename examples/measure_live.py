"""Pomiar F2 na prawdziwym GL i odbiorniku Qt; wynik w JSON na stdout.

Uruchomienie: uv run python examples/measure_live.py --output live-measurement.json
Offscreen mierzy dostarczenie do Qt, nie fizyczne wyświetlenie na ekranie.
"""

import argparse
import ctypes
import json
import os
import statistics
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

from manimcue.live_session import LiveSession, LiveSpec

# `move` obraca kwadrat zamiast go przesuwać: przesunięcie 8 jednostek w 31 s to przy 960×540
# ~0,3 px na klatkę, więc kolejne klatki miały identyczne piksele i licznik „różnych klatek”
# mierzył prędkość ruchu, nie przepustowość. Obrót 15 pełnych obrotów w 31 s rusza narożniki
# o kilka pikseli na klatkę w obu rozdzielczościach.
SCENE = """
from manimlib import Rotate, Square, RIGHT, TAU, linear
from manimcue.live_scene import LiveScene
class Benchmark(LiveScene):
    LOOPS = set()
    SEQUENCE = []
    def build_objects(self):
        self.square = Square().set_fill("#FF0000", 1).set_stroke(width=0)
        self.add(self.square)
        self.red = True
    def warm(self):
        self.square.move_to(-4 * RIGHT)
        self.play(self.square.animate.shift(8 * RIGHT), run_time=3, rate_func=linear)
    def move(self):
        self.play(Rotate(self.square, 15 * TAU), run_time=31, rate_func=linear)
    def flip(self):
        self.red = not self.red
        self.square.set_fill("#FF0000" if self.red else "#00FF00", 1)
    PRESETS = {"warm": warm, "move": move, "flip": flip}
"""


def cpu_seconds(pid):
    """Czas CPU procesu z API Windows, w sekundach jednego rdzenia."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    times = [wintypes.FILETIME() for _ in range(4)]
    try:
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        return (
            sum((value.dwHighDateTime << 32) | value.dwLowDateTime for value in times[2:])
            / 10_000_000
        )
    finally:
        kernel.CloseHandle(handle)


class Measurement:
    def __init__(self, app, spec):
        self.app = app
        self.label = QLabel()
        self.label.resize(spec.width, spec.height)
        self.label.show()
        self.session = LiveSession()
        self.events = []
        self.frame = None
        self.distinct = 0
        self.received = 0
        self.copy_times = []
        self.delivery_times = []
        self.session.start(spec)

    def tick(self):
        self.events += self.session.poll()
        began = time.monotonic()
        frame = self.session.try_read_frame()
        copied = time.monotonic()
        if frame is not None:
            self.copy_times.append(copied - began)
            self.received += 1
            if self.frame is None or self.frame.pixels != frame.pixels:
                self.distinct += 1
            image = QImage(
                frame.pixels,
                frame.width,
                frame.height,
                frame.width * 4,
                QImage.Format.Format_RGBA8888,
            )
            self.label.setPixmap(QPixmap.fromImage(image.copy()))
            self.delivery_times.append(time.monotonic() - copied)
            self.frame = frame
        self.app.processEvents()
        if self.session.error:
            raise RuntimeError(self.session.error)

    def until(self, condition, timeout=40):
        deadline = time.monotonic() + timeout
        while not condition():
            self.tick()
            if time.monotonic() >= deadline:
                raise TimeoutError(self.events)
            time.sleep(0.001)

    def during(self, seconds):
        deadline = time.monotonic() + seconds
        self.until(lambda: time.monotonic() >= deadline, seconds + 5)

    def cue(self, name):
        self.events.clear()
        self.session.send(name)
        self.until(lambda: f"CUE_DONE {name}" in self.events)

    def stop(self):
        self.session.request_stop()
        deadline = time.monotonic() + 5
        while self.session._process is not None and time.monotonic() < deadline:
            self.session.poll()
            time.sleep(0.002)
        if self.session._process is not None:
            raise RuntimeError("Proces nie zakończył się")
        self.label.close()


def measure(app, scene_file, width, height):
    began = time.monotonic()
    receiver = Measurement(app, LiveSpec(scene_file, "Benchmark", width, height, 60))
    try:
        receiver.until(lambda: "READY" in receiver.events and receiver.frame is not None)
        cold_start = time.monotonic() - began
        receiver.cue("warm")
        receiver.during(0.1)
        baseline = {key: value.copy() for key, value in receiver.session._metrics.items()}
        receiver.events.clear()
        receiver.session.send("move")
        receiver.until(lambda: "CUE_START move" in receiver.events)
        receiver.distinct = 0
        receiver.received = 0
        receiver.copy_times.clear()
        receiver.delivery_times.clear()
        began = time.monotonic()
        receiver.during(30)
        elapsed = time.monotonic() - began
        fps = receiver.distinct / elapsed
        copy_ms = statistics.mean(receiver.copy_times) * 1000
        delivery_ms = statistics.mean(receiver.delivery_times) * 1000
        receiver.until(lambda: "CUE_DONE move" in receiver.events)
        receiver.during(0.05)
        stages = {}
        for name, (total, count) in receiver.session._metrics.items():
            old_total, old_count = baseline[name]
            stages[name + "_ms"] = (total - old_total) / (count - old_count) * 1000
        cpu_before = cpu_seconds(receiver.session._process.pid)
        began = time.monotonic()
        receiver.during(5)
        cpu_percent = (
            100
            * (cpu_seconds(receiver.session._process.pid) - cpu_before)
            / (time.monotonic() - began)
        )
        latencies = []
        for _ in range(40):
            previous = receiver.frame.pixels
            began = time.monotonic()
            receiver.session.send("flip")
            receiver.until(lambda previous=previous: receiver.frame.pixels != previous, 5)
            latencies.append((time.monotonic() - began) * 1000)
            receiver.during(0.01)
        p95 = statistics.quantiles(latencies, n=100, method="inclusive")[94]
        threshold = 60 if width == 960 else 30
        return {
            "resolution": f"{width}x{height}",
            "duration_s": elapsed,
            "distinct_received_fps": fps,
            "received_fps": receiver.received / elapsed,
            "fps_threshold": threshold,
            "fps_pass": fps >= threshold,
            "idle_cpu_core_percent": cpu_percent,
            "cpu_pass": cpu_percent < 5,
            "command_p95_ms": p95,
            "latency_pass": p95 < 100,
            "cold_start_s": cold_start,
            **stages,
            "receiver_copy_ms": copy_ms,
            "qt_delivery_ms": delivery_ms,
        }
    finally:
        receiver.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix="manimcue-measure-") as directory:
        scene_file = Path(directory) / "benchmark.py"
        scene_file.write_text(SCENE, encoding="utf-8")
        results = [measure(app, str(scene_file), w, h) for w, h in [(960, 540), (1920, 1080)]]
    report = {
        "platform": "Windows",
        "qt_platform": app.platformName(),
        "requested_fps": 60,
        "warmup_s": 3,
        "results": results,
    }
    output = json.dumps(report, indent=2)
    print(output)
    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
