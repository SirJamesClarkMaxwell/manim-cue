"""Wersjonowany bufor RGBA ze wspólną blokadą metadanych i pikseli."""

import math
import struct
import time
from dataclasses import dataclass

MAGIC = b"MCUEFRM1"
HEADER = struct.Struct("<8sIIIIIIIQdI")
VERSION = 1
RGBA8 = 1
BOTTOM_UP = 1


@dataclass(frozen=True)
class OwnedFrame:
    """Kopia obrazu niezależna od czasu życia pamięci współdzielonej."""

    frame_id: int
    width: int
    height: int
    timestamp: float
    boundary: bool
    pixels: bytes

    def pixel(self, x: int, y: int) -> tuple[int, int, int, int]:
        if not 0 <= x < self.width or not 0 <= y < self.height:
            raise IndexError((x, y))
        offset = 4 * (y * self.width + x)
        return tuple(self.pixels[offset : offset + 4])


def buffer_size(width: int, height: int) -> int:
    if width <= 0 or height <= 0:
        raise ValueError("Niepoprawne wymiary klatki")
    return HEADER.size + width * height * 4


class FrameBuffer:
    """Jeden pisarz i czytelnik; czytelnik nigdy nie czeka na blokadę."""

    def __init__(self, shm, lock, width: int, height: int):
        self.shm = shm
        self.lock = lock
        self.width = width
        self.height = height
        self.last_id = 0
        if shm.size < buffer_size(width, height):
            raise ValueError("Niepoprawny rozmiar pamięci")

    def publish(self, pixels: bytes, frame_id: int, boundary: bool = False) -> None:
        size = self.width * self.height * 4
        if len(pixels) != size or frame_id <= 0:
            raise ValueError("Niepoprawna klatka")
        with self.lock:
            self.shm.buf[HEADER.size : HEADER.size + size] = pixels
            HEADER.pack_into(
                self.shm.buf,
                0,
                MAGIC,
                VERSION,
                self.width,
                self.height,
                self.width * 4,
                size,
                RGBA8,
                BOTTOM_UP,
                frame_id,
                time.monotonic(),
                int(boundary),
            )

    def try_read(self) -> OwnedFrame | None:
        if not self.lock.acquire(False):
            return None
        try:
            values = HEADER.unpack_from(self.shm.buf)
            magic, version, width, height, stride, size, fmt, orientation, fid, stamp, flag = values
            if magic == b"\0" * 8:
                if any(self.shm.buf[: HEADER.size]):
                    raise ValueError("Uszkodzony nagłówek klatki")
                return None
            if (
                (magic, version, width, height, stride, size, fmt, orientation)
                != (
                    MAGIC,
                    VERSION,
                    self.width,
                    self.height,
                    self.width * 4,
                    self.width * self.height * 4,
                    RGBA8,
                    BOTTOM_UP,
                )
                or fid < 1
                or flag not in (0, 1)
                or not math.isfinite(stamp)
                or stamp <= 0
            ):
                raise ValueError("Uszkodzony nagłówek klatki")
            if fid == self.last_id:
                return None
            pixels = bytes(self.shm.buf[HEADER.size : HEADER.size + size])
        finally:
            self.lock.release()
        self.last_id = fid
        # Odwrócenie poza blokadą: API odbiornika używa lewego górnego rogu.
        pixels = b"".join(pixels[y * stride : (y + 1) * stride] for y in range(height - 1, -1, -1))
        return OwnedFrame(fid, width, height, stamp, bool(flag), pixels)
