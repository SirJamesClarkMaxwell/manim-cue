"""Testy atomowej publikacji, walidacji i własności pikseli bez GL."""

import multiprocessing as mp
import time
from multiprocessing.shared_memory import SharedMemory

import pytest

from manimcue.frame_buffer import HEADER, FrameBuffer, buffer_size


@pytest.fixture
def buffer():
    shm = SharedMemory(create=True, size=buffer_size(32, 16))
    lock = mp.get_context("spawn").Lock()
    frames = FrameBuffer(shm, lock, 32, 16)
    yield frames
    shm.close()
    shm.unlink()


def synthetic_writer(name, lock):
    shm = SharedMemory(name=name)
    frames = FrameBuffer(shm, lock, 32, 16)
    try:
        for fid in range(1, 2001):
            frames.publish(bytes([fid % 251]) * (32 * 16 * 4), fid)
            time.sleep(0.0001)
    finally:
        shm.close()


def die_with_lock(lock, ready):
    lock.acquire()
    ready.send(True)
    ready.close()
    time.sleep(60)


def test_no_torn_synthetic_frames(buffer):
    process = mp.get_context("spawn").Process(
        target=synthetic_writer, args=(buffer.shm.name, buffer.lock)
    )
    process.start()
    seen = []
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            frame = buffer.try_read()
            if frame:
                seen.append(frame.frame_id)
                assert frame.pixels == bytes([frame.frame_id % 251]) * (32 * 16 * 4)
            if process.exitcode is not None:
                break
            time.sleep(0.01)
        assert len(seen) >= 5
        assert seen == sorted(set(seen))
        process.join(1)
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        process.close()


def test_reader_owns_pixels(buffer):
    buffer.publish(b"\x12" * (32 * 16 * 4), 1, True)
    frame = buffer.try_read()
    buffer.publish(b"\x34" * (32 * 16 * 4), 2)
    assert frame.pixels == b"\x12" * (32 * 16 * 4)
    assert frame.boundary
    assert buffer.try_read().frame_id == 2
    assert buffer.try_read() is None


def test_orientation_and_pixel_bounds(buffer):
    buffer.publish(b"\x01" * (32 * 8 * 4) + b"\x02" * (32 * 8 * 4), 1)
    frame = buffer.try_read()
    assert frame.pixel(0, 0) == (2, 2, 2, 2)
    assert frame.pixel(31, 15) == (1, 1, 1, 1)
    with pytest.raises(IndexError):
        frame.pixel(32, 0)


def test_worker_dies_holding_lock(buffer, qtbot):
    reader, writer = mp.get_context("spawn").Pipe(False)
    process = mp.get_context("spawn").Process(target=die_with_lock, args=(buffer.lock, writer))
    process.start()
    assert reader.poll(5)
    assert reader.recv()
    process.kill()
    process.join(2)
    from PySide6.QtCore import QTimer

    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(buffer.try_read()))
    timer.start(1)
    qtbot.waitUntil(lambda: len(ticks) >= 10)
    timer.stop()
    assert ticks == [None] * len(ticks)
    process.close()
    reader.close()
    writer.close()


@pytest.mark.parametrize("offset", [0, 8, 12, 20, 28, 32, HEADER.size - 1])
def test_corrupt_header(buffer, offset):
    buffer.publish(b"\0" * (32 * 16 * 4), 1)
    buffer.shm.buf[offset] ^= 0x80
    with pytest.raises(ValueError, match="nagłówek"):
        buffer.try_read()


def test_empty_and_invalid_payload(buffer):
    assert buffer.try_read() is None
    with pytest.raises(ValueError):
        buffer.publish(b"bad", 1)
