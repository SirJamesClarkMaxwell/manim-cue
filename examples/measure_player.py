"""Pomiar D33: GUI w oknie lub QT_QPA_PLATFORM=offscreen; JSON na stdout.

uv run --frozen python examples/measure_player.py --trials 10 --mode both
Mierzy odbiór zmienionych pikseli przez GUI, nie fizyczne odświeżenie monitora.
"""

import argparse
import contextlib
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Spawn wykonuje moduł główny ponownie; logi workera również muszą ominąć JSON na stdout.
if __name__ == "__mp_main__":
    sys.stdout = sys.stderr

from qtpy.QtCore import QCoreApplication, QEvent, Qt, QUrl

from manimcue.slides.config import ClipLayer, Config, LiveLayer, PresentationConfig, SlideConfig
from manimcue.slides.present.player import Player
from manimcue.slides.qt_utils import qapp

RESOLUTION = (640, 360)


def make_marker(path, size):
    """Dwie niezależne sceny CE ze zmianą znacznika od drugiej klatki filmu."""
    from manim import GREEN, RED, Scene, Square, UpdateFromAlphaFunc, tempconfig

    class BaseMarker(Scene):
        def construct(self):
            marker = Square().set_fill(RED, 1).set_stroke(width=0)
            marker.move_to((-4.7, 0, 0))
            self.add(marker)
            self.play(
                UpdateFromAlphaFunc(
                    marker, lambda obj, alpha: obj.set_fill(RED if alpha == 0 else GREEN, 1)
                ),
                run_time=1,
            )

    class ClipMarker(Scene):
        def construct(self):
            marker = Square().set_fill(RED, 1).set_stroke(width=0)
            self.add(marker)
            self.play(
                UpdateFromAlphaFunc(
                    marker, lambda obj, alpha: obj.set_fill(RED if alpha == 0 else GREEN, 1)
                ),
                run_time=1,
            )

    with tempconfig(
        {
            "pixel_width": size[0],
            "pixel_height": size[1],
            "frame_rate": 60,
            "media_dir": str(path.parent / "ce"),
            "output_file": path.stem,
            "disable_caching": True,
            "verbosity": "ERROR",
            "progress_bar": "none",
        }
    ):
        scene = BaseMarker() if path.stem == "base" else ClipMarker()
        scene.render()
        return Path(scene.renderer.file_writer.movie_file_path)


def pump(app, until, timeout=30):
    deadline = time.perf_counter() + timeout
    while not until():
        if time.perf_counter() > deadline:
            raise TimeoutError("Brak zdarzeń pomiaru w ciągu 30 s")
        app.processEvents()
        time.sleep(0.001)


def video_bytes(frame):
    image = frame.toImage()
    return bytes(image.constBits()) if not image.isNull() else None


def measure(app, directory, trials, persistent):
    base = make_marker(directory / "base.mp4", RESOLUTION)
    clip = make_marker(directory / "clip.mp4", (160, 90))
    layer = LiveLayer(
        scene_file=Path(__file__).with_name("live_three.py").resolve(),
        scene_name="ThreePanel",
        rect=(0.36, 0.15, 0.28, 0.6),
        session_id="benchmark" if persistent else None,
        enter_cue="flip",
    )
    layers = [layer, ClipLayer(file=clip, rect=(0.69, 0.15, 0.28, 0.6))]
    slides = [SlideConfig(file=base, rev_file=base, layers=layers) for _ in range(trials + 1)]
    began = time.perf_counter()
    player = Player(
        Config(),
        [PresentationConfig(slides=slides, resolution=RESOLUTION)],
        aspect_ratio_mode=Qt.AspectRatioMode.KeepAspectRatio,
    )
    player.resize(*RESOLUTION)
    super(Player, player).show()
    rows = []
    current = {}
    baselines = {}
    cold_events = {"process_requested": began}
    manual = {}
    manual_before = None

    def observe_ready():
        if 0 in player.live.sessions and player.live.sessions[0].state == "ready":
            cold_events.setdefault("ready_gui", time.perf_counter())

    player.live.changed.connect(observe_ready)

    def on_video(name, frame):
        if not current or not frame.isValid():
            return
        if name == "base" and player.clips.base_frame is None:
            return
        sink = (
            player.composition.video_item.videoSink()
            if name == "base"
            else player.composition.layer_items[1].videoSink()
        )
        if sink.videoFrame() != frame:
            return
        pixels = video_bytes(frame)
        if name not in baselines:
            baselines[name] = pixels
        elif pixels != baselines[name]:
            current.setdefault(name + "_changed_gui", time.perf_counter())

    def on_live(index, frame, received):
        cold_events.setdefault("first_frame_gui", received)
        if manual and frame.pixels != manual_before:
            manual.setdefault("changed_gui", received)
            manual.setdefault("changed_publication", frame.timestamp)
        if not current:
            return
        current.setdefault("live_publication_received", received)
        if "live" not in baselines:
            baselines["live"] = frame.pixels
        elif frame.pixels != baselines["live"] and "cue_sent" in current:
            current.setdefault("live_changed_gui", received)
            current.setdefault("live_changed_publication", frame.timestamp)

    player.live.frame_received.connect(on_live)
    player.live.cue_sent.connect(lambda i, cue, stamp: current.setdefault("cue_sent", stamp))
    player.composition.video_item.videoSink().videoFrameChanged.connect(
        lambda frame: on_video("base", frame)
    )
    try:
        pump(
            app,
            lambda: (
                player.live.sessions[0].state == "ready"
                and bool(player.live.last_frames)
                and not player.clips.preparing
            ),
        )
        cold = cold_events["ready_gui"] - began
        for _ in range(trials):
            session = player.live.sessions[0]
            pump(app, lambda: player.media_player.position() > 80)
            current = {"transition_requested": time.perf_counter()}
            baselines = {"live": player.live.last_frames[session].pixels} if persistent else {}
            old_pid = session._process.pid
            player.next()
            player.composition.layer_items[1].videoSink().videoFrameChanged.connect(
                lambda frame: on_video("clip", frame)
            )
            pump(
                app,
                lambda row=current: all(
                    name in row
                    for name in (
                        "base_changed_gui",
                        "clip_changed_gui",
                        "live_changed_gui",
                        "cue_sent",
                    )
                ),
            )
            current["barrier_released"] = player.clips.released_at
            current["pid_before"] = old_pid
            current["pid_after"] = player.live.sessions[0]._process.pid
            changed = [current[name + "_changed_gui"] for name in ("base", "clip", "live")]
            current["spread_ms"] = 1000 * (max(changed) - min(changed))
            current["latency_ms"] = {
                name: 1000 * (current[name + "_changed_gui"] - current["transition_requested"])
                for name in ("base", "clip", "live")
            }
            rows.append(current)
            current = {}
            # Koniec cue oddziela przejścia od dopuszczonego w D33 przerwania animacji.
            stop = time.perf_counter() + 0.5
            pump(app, lambda deadline=stop: time.perf_counter() >= deadline)
        session = player.live.sessions[0]
        manual_before = player.live.last_frames[session].pixels
        manual = {"cue_requested": time.perf_counter()}
        session.send("flip")
        manual["cue_sent"] = time.perf_counter()
        pump(app, lambda: "changed_gui" in manual)
        return {
            "mode": "session_id" if persistent else "restart",
            "cold_ready_seconds": cold,
            "cold_start": cold_events,
            "manual_cue": manual,
            "trials": rows,
            "spread_ms_median": statistics.median(row["spread_ms"] for row in rows),
            "spread_ms_max": max(row["spread_ms"] for row in rows),
        }
    finally:
        player.close()
        player.live.shutdown()
        player.media_player.setSource(QUrl())
        player.info.next_media_player.setSource(QUrl())
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--mode", choices=("both", "restart", "session_id"), default="both")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.trials < 10:
        parser.error("Pomiar wymaga co najmniej 10 prób")
    app = qapp()
    result = {
        "clock": "time.perf_counter",
        "platform": os.environ.get("QT_QPA_PLATFORM", "window"),
        "metric": "changed pixels received in GUI",
        "results": [],
    }
    # Biblioteki mogą pisać komunikaty; stdout skryptu zawiera wyłącznie JSON.
    with contextlib.redirect_stdout(sys.stderr), tempfile.TemporaryDirectory() as tmp:
        for mode in ("restart", "session_id") if args.mode == "both" else (args.mode,):
            result["results"].append(measure(app, Path(tmp), args.trials, mode == "session_id"))
    encoded = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
