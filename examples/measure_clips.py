"""Pomiar F5/8: baza CE + 1/2/3 klipy, widoczne Info i ruchomy panel manimgl.

Mierzy odbiór w GUI, nie fizyczne odświeżenie monitora. Działa w oknie i z
QT_QPA_PLATFORM=offscreen. JSON na stdout lub --output, tabela na stderr.
Domyślnie zmiany oznaczają znaczniki czasu klatek.
--pixel-probe odczytuje pełny obraz i obciąża wątek GUI. Timer mierzy odstęp
między callbackami pomniejszony o zadane 1 ms, nie opóźnienie zegara monitora.
"""

import argparse
import contextlib
import faulthandler
import itertools
import json
import math
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

if __name__ == "__mp_main__":
    sys.stdout = sys.stderr

from measure_player import pump, video_bytes
from qtpy.QtCore import QCoreApplication, QEvent, Qt, QTimer, QUrl

from manimcue.slides.config import ClipLayer, Config, LiveLayer, PresentationConfig, SlideConfig
from manimcue.slides.present.player import Player
from manimcue.slides.qt_utils import qapp

FPS = 60


def distribution(values):
    """Percentyle najbliższej rangi; brak próbek pozostaje jawny."""
    ordered = sorted(values)
    return {
        key: ordered[min(len(ordered) - 1, math.ceil(len(ordered) * q) - 1)] if ordered else None
        for key, q in (("p50", 0.5), ("p95", 0.95), ("max", 1))
    }


def video_stamp(frame, pixel_probe=False):
    """Znacznik bez mapowania pamięci; CRC pełnego obrazu tylko na żądanie."""
    if not pixel_probe:
        return frame.startTime(), frame.endTime()
    pixels = video_bytes(frame)
    return zlib.crc32(pixels) if pixels is not None else None


def make_video(directory, name, resolution, base=False):
    """CE: czerwony znacznik na starcie, potem ruch i zielony znacznik."""
    from manim import GREEN, RED, Scene, Square, UpdateFromAlphaFunc, linear, tempconfig

    class Marker(Scene):
        def construct(self):
            marker = Square(side_length=1).set_fill(RED, 1).set_stroke(width=0)
            y = 2.7 if base else 0
            self.add(marker.move_to((-4, y, 0)))
            self.play(
                UpdateFromAlphaFunc(
                    marker,
                    lambda obj, alpha: obj.move_to((-4 + 8 * alpha, y, 0)).set_fill(
                        RED if alpha == 0 else GREEN, 1
                    ),
                ),
                run_time=2,
                rate_func=linear,
            )

    with tempconfig(
        {
            "pixel_width": resolution[0],
            "pixel_height": resolution[1],
            "frame_rate": FPS,
            "media_dir": str(directory / name),
            "output_file": name,
            "disable_caching": True,
            "verbosity": "ERROR",
            "progress_bar": "none",
        }
    ):
        scene = Marker()
        scene.render()
        return Path(scene.renderer.file_writer.movie_file_path)


def measure_separately(count, args, directory):
    """Osobny Player na wariant; nadzorca może zapisać także blokadę natywnego Qt."""
    output = directory / f"case-{count}.json"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--clips",
        str(count),
        "--seconds",
        str(args.seconds),
        "--warmup",
        str(args.warmup),
        "--resolution",
        "x".join(map(str, args.resolution)),
        "--output",
        str(output),
        "--pid-file",
        str(output.with_suffix(".pids.json")),
    ]
    for flag in ("no_live", "no_info", "pixel_probe"):
        if getattr(args, flag):
            command.append("--" + flag.replace("_", "-"))
    timeout = args.seconds + args.warmup + 90
    with subprocess.Popen(command, start_new_session=os.name != "nt") as process:
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Timer w GUI nie przerwie zablokowanego wywołania natywnego; odbierz też live.
            if os.name == "nt":
                # taskkill /T wymaga tu zabronionej enumeracji procesów; znamy własne PID-y.
                pids = json.loads(output.with_suffix(".pids.json").read_text(encoding="utf-8"))
                for pid in reversed(pids):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except (ProcessLookupError, PermissionError):
                        pass
                    except OSError as error:
                        # Windows zwraca 87, gdy zapisany proces live już się zakończył.
                        if getattr(error, "winerror", None) != 87:
                            raise
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return {"clips": count, "streams": {}, "errors": [f"Timeout procesu: {timeout} s"]}
    if code:
        return {"clips": count, "streams": {}, "errors": [f"Proces zakończony kodem {code}"]}
    return json.loads(output.read_text(encoding="utf-8"))["results"][0]


def measure(app, videos, count, args):
    """Sygnały sinków mierzą odbiór po filtrze przywracania starej klatki."""
    layers = [
        ClipLayer(file=videos[i + 1], loop=True, rect=(0.02 + i * 0.32, 0.3, 0.3, 0.3))
        for i in range(count)
    ]
    if not args.no_live:
        layers.append(
            LiveLayer(
                scene_file=Path(__file__).resolve().parents[1] / "tests/scenes/live_gl.py",
                scene_name="LiveGLLoopBoundary",
                rect=(0.36, 0.65, 0.28, 0.28),
                enter_cue="spin",
                fps=FPS,
            )
        )
    slide = SlideConfig(file=videos[0], rev_file=videos[0], loop=True, layers=layers)
    player = Player(
        Config(),
        [PresentationConfig(slides=[slide, slide], resolution=args.resolution)],
        aspect_ratio_mode=Qt.AspectRatioMode.KeepAspectRatio,
        hide_info_window=args.no_info,
    )
    if args.pid_file:
        args.pid_file.write_text(
            json.dumps([os.getpid(), *(s._process.pid for s in player.live.sessions.values())]),
            encoding="utf-8",
        )
    player.resize(*args.resolution)
    names = ["base", *(f"clip_{i + 1}" for i in range(count))]
    if not args.no_live:
        names.append("live")
    received = {name: [] for name in names}
    changed = {name: [] for name in names}
    previous = {}
    initial = {}
    first = {}
    errors = []
    started = None
    timer_times = []
    player.live.error.connect(errors.append)

    def observe(name, digest):
        now = time.perf_counter()
        initial.setdefault(name, digest)
        release = player.clips.released_at
        if release is not None and now >= release and digest != initial[name]:
            first.setdefault(name, now)
        if started is not None:
            received[name].append(now)
            if previous.get(name) != digest:
                changed[name].append(now)
        previous[name] = digest

    def on_video(name, sink, frame):
        if not frame.isValid() or sink.videoFrame() != frame:
            return
        # Zapisujemy tylko liczby, bez referencji do klatki dekodera.
        stamp = video_stamp(frame, args.pixel_probe)
        if stamp is not None:
            observe(name, stamp)

    sinks = [player.composition.video_item.videoSink()] + [
        player.composition.layer_items[i].videoSink() for i in range(count)
    ]
    for name, sink in zip(names, sinks, strict=False):
        sink.videoFrameChanged.connect(lambda frame, n=name, s=sink: on_video(n, s, frame))
    player.live.frame_received.connect(
        lambda i, frame, stamp: observe("live", zlib.crc32(frame.pixels))
    )
    timer = QTimer(player)
    timer.setTimerType(Qt.TimerType.PreciseTimer)
    timer.timeout.connect(lambda: timer_times.append(time.perf_counter()))
    try:
        player.show(app.screens())
        pump(app, lambda: player.clips.released_at is not None, timeout=40)
        print(f"N={count}: bariera zwolniona", file=sys.stderr, flush=True)
        if not args.no_live:
            pump(app, lambda: bool(player.live.last_frames) or bool(errors), timeout=40)
            if not errors:
                # Początkowy slajd nie wysyła enter_cue; pomiar uruchamia pętlę jawnie.
                player.live.sessions[count].send("spin")
        print(f"N={count}: rozgrzewka", file=sys.stderr, flush=True)
        deadline = time.perf_counter() + args.warmup
        pump(app, lambda: time.perf_counter() >= deadline, timeout=args.warmup + 10)
        info_visible = player.info.isVisible()
        started = time.perf_counter()
        cpu_start = time.process_time()
        timer_times.append(started)
        timer.start(1)
        print(f"N={count}: pomiar {args.seconds} s", file=sys.stderr, flush=True)
        pump(app, lambda: time.perf_counter() >= started + args.seconds, timeout=args.seconds + 30)
        ended = time.perf_counter()
        cpu = time.process_time() - cpu_start
        timer.stop()
        duration = ended - started
        streams = {}
        for name in names:
            times = changed[name]
            intervals = [1000 * (b - a) for a, b in itertools.pairwise(times)]
            streams[name] = {
                "source_fps": FPS,
                "received_frames": len(received[name]),
                "received_fps": len(received[name]) / duration,
                "changed_frames": len(times),
                "changed_fps": len(times) / duration,
                "changed_interval_ms": distribution(intervals),
                "estimated_lost_frames": max(0, round(duration * FPS) - len(times)),
                "longest_silence_ms": max(b - a for a, b in zip([started, *times], [*times, ended]))
                * 1000,
            }
        stamps = [first.get(name) for name in names if name != "live"]
        complete = all(stamp is not None for stamp in stamps)
        gaps = [1000 * (b - a) for a, b in itertools.pairwise(timer_times)]
        gaps.append(1000 * (ended - timer_times[-1]))
        return {
            "clips": count,
            "info_visible": info_visible,
            "duration_seconds": duration,
            "streams": streams,
            "first_changed_after_release_ms": {
                name: (first[name] - player.clips.released_at) * 1000 if name in first else None
                for name in names
                if name != "live"
            },
            "start_spread_ms": (max(stamps) - min(stamps)) * 1000 if complete else None,
            "qt_timer_gap_ms": distribution(gaps),
            "qt_timer_delay_ms": distribution([max(0, gap - 1) for gap in gaps]),
            "qt_timer_samples": len(gaps),
            "player_cpu_seconds": cpu,
            "player_cpu_percent_one_core": 100 * cpu / duration,
            "live_cpu_percent_one_core": None,
            "errors": [*errors, *player.clips.problems],
            "live_states": [session.state for session in player.live.sessions.values()],
        }
    finally:
        timer.stop()
        player.close()
        player.live.shutdown()
        player.media_player.setSource(QUrl())
        player.info.next_media_player.setSource(QUrl())
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clips", default="1,2,3")
    parser.add_argument("--resolution", default="1920x1080")
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--warmup", type=float, default=3)
    parser.add_argument("--no-live", action="store_true")
    parser.add_argument("--no-info", action="store_true")
    parser.add_argument("--pixel-probe", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pid-file", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        counts = [int(value) for value in args.clips.split(",")]
        args.resolution = tuple(int(value) for value in args.resolution.lower().split("x"))
        if not counts or any(n not in (1, 2, 3) for n in counts):
            raise ValueError
        if len(args.resolution) != 2 or any(n <= 0 or n % 2 for n in args.resolution):
            raise ValueError
        if not math.isfinite(args.seconds) or args.seconds <= 0:
            raise ValueError
        if not math.isfinite(args.warmup) or args.warmup < 0:
            raise ValueError
    except ValueError:
        parser.error("Wymagane: --clips 1,2,3; parzyste WxH; seconds > 0; warmup >= 0")
    began = time.perf_counter()
    if args.pid_file:
        args.pid_file.write_text(json.dumps([os.getpid()]), encoding="utf-8")
    result = {
        "metric": "Odbiór w GUI, nie fizyczne odświeżenie monitora",
        "platform": os.environ.get("QT_QPA_PLATFORM", "window"),
        "qt_ffmpeg_decoding_hw_device_types": os.environ.get("QT_FFMPEG_DECODING_HW_DEVICE_TYPES"),
        "host": platform.platform(),
        "resolution": args.resolution,
        "source_fps": FPS,
        "clock": "time.perf_counter",
        "change_detection": "CRC32" if args.pixel_probe else "startTime/endTime",
        "live_change_detection": "CRC32 frame.pixels",
        "pixel_probe": args.pixel_probe,
        "info": not args.no_info,
        "loss_estimate": "max(0, round(duration * source_fps) - changed_frames)",
        "warmup_seconds": args.warmup,
        "requested_seconds": args.seconds,
        "live": not args.no_live,
        "live_cpu_note": "Nie mierzono CPU procesu potomnego; process_time obejmuje tylko player",
        "results": [],
    }
    with contextlib.redirect_stdout(sys.stderr), tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        if len(counts) > 1:
            for count in counts:
                result["results"].append(measure_separately(count, args, directory))
        else:
            app = qapp()
            count = counts[0]
            videos = [make_video(directory, "base", args.resolution, base=True)]
            videos += [
                make_video(directory, f"clip_{i + 1}", args.resolution) for i in range(count)
            ]
            print(f"Pomiar N={count}, live={not args.no_live}", file=sys.stderr, flush=True)
            faulthandler.dump_traceback_later(args.seconds + args.warmup + 45)
            try:
                result["results"].append(measure(app, videos, count, args))
            finally:
                faulthandler.cancel_dump_traceback_later()
    result["elapsed_seconds"] = time.perf_counter() - began
    print("N  strumień   odbiór fps  zmiany fps  p95 ms  max ms  straty~", file=sys.stderr)
    for row in result["results"]:
        if not row["streams"]:
            print(f"{row['clips']}  BŁĄD: {row['errors']}", file=sys.stderr)
        for name, stream in row["streams"].items():
            intervals = stream["changed_interval_ms"]
            print(
                f"{row['clips']}  {name:9} {stream['received_fps']:10.2f} "
                f"{stream['changed_fps']:11.2f} {intervals['p95']!s:>7.7} "
                f"{intervals['max']!s:>7.7} {stream['estimated_lost_frames']:8}",
                file=sys.stderr,
            )
    print("N  start ms  Qt opóźnienie p95/max ms  CPU % (1 rdzeń)", file=sys.stderr)
    for row in result["results"]:
        if not row["streams"]:
            continue
        delay = row["qt_timer_delay_ms"]
        print(
            f"{row['clips']}  {row['start_spread_ms']!s:>8.7}  "
            f"{delay['p95']:.2f}/{delay['max']:.2f}  "
            f"{row['player_cpu_percent_one_core']:.1f}",
            file=sys.stderr,
        )
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
