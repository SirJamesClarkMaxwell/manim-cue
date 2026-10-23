"""Proces dekodowania; dwie klatki współdzielone, brak kolejki obrazów w pipe."""

import bisect
import math
import struct
import time
from multiprocessing.shared_memory import SharedMemory

# Slot: rewizja, frame_id, PTS i czas monotoniczny, od którego klatkę wolno pokazać.
SLOT = struct.Struct("<Qqdd")
PROGRESS = 2 * SLOT.size
HEADER = 96


def run_pooled(control, connection) -> None:
    """Proces puli: importy przed czekaniem, potem jedno źródło do końca życia."""
    try:
        import av  # noqa: F401 — import poza ścieżką wejścia na slajd
        from PIL import Image  # noqa: F401

        media = connection.recv()
    except (EOFError, OSError):
        connection.close()
        return
    run_decoder({"media": media, "control": control}, connection)


def run_decoder(spec: dict, connection) -> None:
    """Przygotuj obraz poza UI i publikuj najwyżej cztery klatki na iterację."""
    memory = None
    container = None
    try:
        from PIL import Image, ImageSequence

        media = spec["media"]
        control = spec["control"]
        kind = media["kind"]
        frames = None
        origin = None
        duration = 0
        if kind in ("image", "gif"):
            frames = []
            with Image.open(media["file"]) as image:
                total = 0
                for item in ImageSequence.Iterator(image):
                    began = time.perf_counter()
                    total += item.width * item.height * 4
                    if total > 256 * 1024 * 1024:
                        raise ValueError("GIF przekracza limit 256 MiB RGBA")
                    rgba = item.convert("RGBA")
                    frames.append((duration, rgba.tobytes()))
                    control[7] += time.perf_counter() - began
                    duration += max(0.01, item.info.get("duration", 0) / 1000)
                    width, height = rgba.size
                    if kind == "image":
                        break
            iterator = iter(frames)
        else:
            import av

            container = av.open(media["file"])
            stream = container.streams.video[0]
            if stream.duration is None or stream.time_base is None:
                raise ValueError("Brak wiarygodnego czasu wideo")
            duration = float(stream.duration * stream.time_base)
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("Niepoprawny czas wideo")
            width, height = stream.width, stream.height
            # Sonda wszystkich znaczników odbywa się przed pierwszym READY; B-frames
            # dopuszczają przestawione PTS pakietów, lecz nie duplikaty ani brak PTS.
            timestamps = set()
            previous_dts = None
            for packet in container.demux(stream):
                if not packet.size:
                    continue
                if packet.pts is None or packet.pts in timestamps:
                    raise ValueError("Brak lub powtórzone PTS pakietu wideo")
                timestamps.add(packet.pts)
                if packet.dts is not None:
                    if previous_dts is not None and packet.dts <= previous_dts:
                        raise ValueError("Niemonotoniczne DTS wideo")
                    previous_dts = packet.dts
            if not timestamps:
                raise ValueError("Wideo bez klatek")
            origin = min(timestamps) * float(stream.time_base)
            del timestamps
            seek_time = origin + (max(0, duration - 1) if media.get("at_end") else 0)
            container.seek(int(seek_time / float(stream.time_base)), stream=stream)
            iterator = iter(container.decode(stream))
        size = width * height * 4
        memory = SharedMemory(create=True, size=HEADER + 2 * size)
        memory.buf[:HEADER] = bytes(HEADER)
        descriptor = {
            "type": "memory",
            "name": memory.name,
            "width": width,
            "height": height,
            "duration": duration,
        }
        announced = not media.get("at_end", False)
        if announced:
            connection.send(descriptor)
        target, playing, anchor, position = 0.0, False, 0.0, 0.0
        pending = None
        first_pts = origin
        previous_pts = -1.0
        frame_id = 0
        eof = False
        exhausted = False
        loop_number = 0
        target_revision = -1
        exit_at = None
        period = 0.0
        while True:
            now = time.monotonic()
            struct.pack_into("<d", memory.buf, PROGRESS, now)
            if control[0]:
                return
            # Rodzic nic nie wysyła; poll() rzuca BrokenPipeError po jego śmierci, więc
            # osierocony dekoder kończy się zamiast działać w nieskończoność.
            connection.poll()
            rate = media.get("rate", 1)
            if target_revision != control[4]:
                target_revision = control[4]
                position = control[3]
                if playing:
                    anchor = now
            requested_playing = bool(control[1])
            if requested_playing != playing:
                if playing:
                    position += max(0, now - anchor) * rate
                else:
                    anchor = control[2]
                playing = requested_playing
            target = position + (max(0, now - anchor) * rate if playing else 0)
            if media.get("at_end"):
                target = duration
            if media.get("loop") and kind != "image" and duration > 0:
                if control[5] and exit_at is None:
                    exit_at = (loop_number + 1) * duration
                if exit_at is not None and target >= exit_at:
                    cycle = round(exit_at / duration) - 1
                    target = duration
                else:
                    cycle = int(target / duration)
                    target %= duration
                if cycle != loop_number:
                    began = time.perf_counter()
                    loop_number = cycle
                    if frames is not None:
                        iterator = iter(frames)
                    else:
                        container.seek(
                            int((first_pts or 0) / float(stream.time_base)), stream=stream
                        )
                        iterator = iter(container.decode(stream))
                    pending, previous_pts, eof, exhausted = None, -1, False, False
                    control[11] += time.perf_counter() - began
            if pending is not None and target - pending[0] > 0.25 and 0 < target < duration:
                began = time.perf_counter()
                if frames is not None:
                    index = max(0, bisect.bisect_right([pts for pts, _ in frames], target) - 1)
                    iterator = iter(frames[index:])
                else:
                    container.seek(
                        int((target + (first_pts or 0)) / float(stream.time_base)),
                        stream=stream,
                        backward=True,
                    )
                    iterator = iter(container.decode(stream))
                pending, previous_pts = None, -1
                control[8] += time.perf_counter() - began
            for _ in range(4):
                if eof or exhausted:
                    break
                if pending is None:
                    try:
                        began = time.perf_counter()
                        item = next(iterator)
                        control[6] += time.perf_counter() - began
                        control[9] += 1
                    except StopIteration:
                        exhausted = True
                        break
                    if frames is not None:
                        pts, pixels = item
                    else:
                        if item.pts is None or item.time_base is None:
                            raise ValueError("Brak PTS klatki")
                        absolute = float(item.pts * item.time_base)
                        if first_pts is None:
                            first_pts = absolute
                        pts = absolute - first_pts
                        if not math.isfinite(pts) or pts <= previous_pts:
                            raise ValueError("Niemonotoniczne PTS")
                        began = time.perf_counter()
                        pixels = item.to_ndarray(format="rgba").tobytes()
                        control[7] += time.perf_counter() - began
                    if previous_pts >= 0:
                        period = pts - previous_pts
                    previous_pts = pts
                    pending = pts, pixels
                pts, pixels = pending
                # Pół klatki wyprzedzenia: UI przy vsync bierze klatkę po show_at, więc opóźnienie
                # dekodowania na granicy ticku nie daje na zmianę dwóch klatek i żadnej. Mniej
                # niż okres, więc drugi slot nie nadpisuje klatki, której UI jeszcze potrzebuje.
                lead = 0.5 * period if playing else 0.0
                if pts > target + lead and frame_id:
                    break
                show_at = now + (pts - target) / rate if playing else now
                slot = frame_id % 2
                offset = slot * SLOT.size
                # Nieparzysta rewizja oznacza zapis w toku, parzysta gotowy obraz.
                revision = 2 * (frame_id + 1)
                SLOT.pack_into(memory.buf, offset, revision - 1, frame_id, pts, show_at)
                start = HEADER + slot * size
                memory.buf[start : start + size] = pixels
                SLOT.pack_into(memory.buf, offset, revision, frame_id, pts, show_at)
                frame_id += 1
                control[10] = frame_id
                pending = None
                if frames is not None and kind == "image":
                    eof = True
                    connection.send({"type": "eof"})
            if exhausted and target >= duration and not eof:
                eof = True
                if not announced:
                    connection.send(descriptor)
                    announced = True
                connection.send({"type": "eof"})
            time.sleep(0.002)
    except (EOFError, BrokenPipeError):
        pass
    except Exception as error:  # noqa: BLE001 — granica procesu raportuje każdy błąd dekodera
        try:
            connection.send({"type": "error", "error": f"{type(error).__name__}: {error}"})
        except (EOFError, BrokenPipeError):
            pass
    finally:
        if container is not None:
            container.close()
        if memory is not None:
            memory.close()
            memory.unlink()
        connection.close()
