"""Narzędzia odbioru F10: zewnętrzny watchdog i analiza jawnego śladu JSONL.

Ślad dostarcza instrumentacja próby: time (monotonic), source, frame_id oraz
opcjonalnie decode_ms/conversion_ms/upload_ms/seek_ms i input_latency_ms.
Samo zakończenie komendy ani liczba ticków UI nie dowodzą wydajności obrazów.
"""

import argparse
import json
import math
import os
import statistics
import subprocess
import tempfile
import time
from itertools import pairwise
from pathlib import Path


def watchdog(command: list, timeout: float) -> dict:
    """Bez wątków: przerwij próbę przy braku heartbeat >2 s lub limicie czasu."""
    if not command or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Wymagana komenda i dodatni skończony timeout")
    heartbeat = os.environ.get("F10_HEARTBEAT")
    started = time.monotonic()
    reason = None
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr)
        while process.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed > timeout:
                reason = "timeout"
            elif heartbeat:
                path = Path(heartbeat)
                if path.exists() and time.time() - path.stat().st_mtime > 2:
                    reason = "heartbeat_stalled"
                elif not path.exists() and elapsed > 10:
                    reason = "heartbeat_missing"
            if reason:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
                else:
                    process.kill()
                if process.poll() is None:
                    process.kill()
                break
            time.sleep(0.01)
        process.wait(timeout=5)
        stderr.seek(0)
        return {
            "returncode": process.returncode,
            "reason": reason,
            "elapsed_s": time.monotonic() - started,
            "heartbeat_checked": bool(heartbeat),
            "stderr": stderr.read().decode("utf-8", errors="replace")[-3000:],
        }


def _percentile(values, quantile):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * quantile) - 1)] if ordered else None


def measure(options: dict) -> dict:
    """Analizuj nowe obrazy, osobno od swapów i ticków; nie zatwierdzaj odbioru."""
    result = {
        "status": "recorded",
        "engine": options.get("engine"),
        "clips": options.get("clips"),
        "streams": {},
        "acceptance": "pending Claude",
    }
    if options.get("command"):
        result["watchdog"] = watchdog(options["command"], options.get("timeout", 75))
    if not options.get("trace"):
        result["status"] = "missing_trace"
        result["missing"] = [
            "instrumentacja nowych obrazów i swapów",
            "CPU/sprzęt/Hz",
            "decode/conversion/upload/seek",
            "30 akcji wejścia",
        ]
        return result
    records = [
        json.loads(line)
        for line in Path(options["trace"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not records:
        raise ValueError("Pusty ślad pomiarowy")
    start = options.get(
        "start", min(record["time"] for record in records) + options.get("warmup", 5)
    )
    seconds = options.get("seconds", 60)
    if not math.isfinite(seconds) or seconds < 1:
        raise ValueError("Pomiar musi trwać co najmniej 1 s")
    window = [record for record in records if start <= record["time"] < start + seconds]
    for source in sorted({record["source"] for record in window if "source" in record}):
        frames = []
        seen = set()
        for record in sorted(window, key=lambda record: record["time"]):
            if record.get("source") != source or record.get("frame_id") is None:
                continue
            identity = record.get("generation"), record.get("entry_id"), record["frame_id"]
            if identity not in seen:
                seen.add(identity)
                frames.append(record)
        times = [record["time"] for record in frames]
        gaps = [(right - left) * 1000 for left, right in pairwise(times)]
        bins = [
            sum(start + index <= stamp < start + index + 1 for stamp in times)
            for index in range(int(seconds))
        ]
        stats = {
            "new_images": len(times),
            "median_fps_1s": statistics.median(bins),
            "p95_interval_ms": _percentile(gaps, 0.95),
            "max_silence_ms": max(
                [
                    *gaps,
                    ((times[0] if times else start + seconds) - start) * 1000,
                    (start + seconds - (times[-1] if times else start)) * 1000,
                ]
            ),
        }
        for field in ("decode_ms", "conversion_ms", "upload_ms", "seek_ms", "input_latency_ms"):
            values = [record[field] for record in frames if field in record]
            stats[field] = {"count": len(values), "p95": _percentile(values, 0.95)}
        result["streams"][source] = stats
    result["window"] = {"start": start, "seconds": seconds}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--heartbeat", type=Path)
    parser.add_argument("--timeout", type=float, default=75)
    parser.add_argument("--warmup", type=float, default=5)
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--engine", choices=["manimgl", "ce-cairo"])
    parser.add_argument("--clips", type=int, choices=[1, 2, 3])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.heartbeat:
        os.environ["F10_HEARTBEAT"] = str(args.heartbeat)
    options = vars(args)
    if options["command"][:1] == ["--"]:
        options["command"] = options["command"][1:]
    args.output.write_text(
        json.dumps(measure(options), indent=2, ensure_ascii=False), encoding="utf-8"
    )
