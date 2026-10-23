"""Odbiór źródeł izolowanych od UI."""

import time

import pytest
from PIL import Image

from manimcue.player.sources_av import Source


def wait_for(source, predicate, target=0):
    deadline = time.monotonic() + 8
    update = None
    while time.monotonic() < deadline:
        update = source.poll(time.monotonic(), target, 1)
        if predicate(update):
            return update
        time.sleep(0.01)
    raise AssertionError(update)


@pytest.fixture
def source():
    item = Source()
    yield item
    item.request_close()
    deadline = time.monotonic() + 5
    while not item.poll_closed(time.monotonic()) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert item.poll_closed(time.monotonic())


def test_image_reset_owned_rgba_and_eof(source, tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGBA", (20, 10), (10, 20, 30, 40)).save(path)
    source.prepare(10, {"kind": "image", "file": str(path)})
    update = wait_for(source, lambda u: "rgba" in u)
    assert update["rgba"] == bytes((10, 20, 30, 40)) * 200
    assert update["stride"] == 80 and update["entry_id"] == 10
    old = update["rgba"]
    source.reset(11)
    update = wait_for(source, lambda u: "rgba" in u)
    assert update["generation"] == 2 and update["entry_id"] == 11
    assert old == update["rgba"]
    update = wait_for(source, lambda u: u["status"] == "eof")
    assert update["rgba"] == old


def test_orphaned_decoder_exits_when_parent_pipe_closes(source, tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGBA", (4, 4), "red").save(path)
    source.prepare(1, {"kind": "image", "file": str(path)})
    wait_for(source, lambda u: u["status"] == "eof")
    process = source.process
    # Zamknięty potok udaje śmierć playera; bez terminate dekoder ma zakończyć się sam.
    source.connection.close()
    source.connection = None
    process.join(3)
    assert not process.is_alive()


def test_gif_variable_times(source, tmp_path):
    path = tmp_path / "animation.gif"
    frames = [Image.new("RGBA", (4, 4), color) for color in ["red", "green", "blue"]]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=[0, 100, 200])
    source.prepare(1, {"kind": "gif", "file": str(path)})
    first = wait_for(source, lambda u: "rgba" in u)
    assert first["pts"] == 0 and first["duration"] == pytest.approx(0.31)
    second = wait_for(source, lambda u: u.get("frame_id") == 1, target=0.02)
    assert second["pts"] == pytest.approx(0.01)
    last = wait_for(source, lambda u: u["status"] == "eof", target=1)
    assert last["pts"] == pytest.approx(0.11)
    source.prepare(2, {"kind": "gif", "file": str(path), "at_end": True})
    frozen = wait_for(source, lambda update: "rgba" in update)
    assert frozen["status"] == "eof" and frozen["pts"] == pytest.approx(0.11)


def test_invalid_file_error(source, tmp_path, monkeypatch):
    source.prepare(1, {"kind": "video", "file": str(tmp_path / "missing.mp4")})
    update = wait_for(source, lambda u: u["status"] == "error")
    assert update["error"] and "rgba" not in update
    import manimcue.player.sources_av as adapter

    monkeypatch.setattr(adapter, "run_decoder", vanished_memory_decoder)
    source.prepare(2, {"kind": "video", "file": "unused"})
    update = wait_for(source, lambda update: update["status"] == "error")
    assert "f10_missing_" in update["error"]


def test_cfr_pts_and_bounded_mailbox(source, tmp_path):
    import av
    import numpy as np

    path = tmp_path / "cfr.mp4"
    with av.open(str(path), "w") as output:
        stream = output.add_stream("mpeg4", rate=10)
        stream.width = stream.height = 16
        stream.pix_fmt = "yuv420p"
        for index in range(10):
            frame = av.VideoFrame.from_ndarray(
                np.full((16, 16, 3), index * 20, dtype=np.uint8), format="rgb24"
            )
            for packet in stream.encode(frame):
                output.mux(packet)
        for packet in stream.encode():
            output.mux(packet)
    source.prepare(1, {"kind": "video", "file": str(path)})
    wait_for(source, lambda u: "rgba" in u)
    # Windows zaokrągla mapowanie do granicy strony, nie powstaje trzeci slot.
    assert 64 + 2 * 16 * 16 * 4 <= source.memory.size <= 4096
    last = wait_for(source, lambda u: u["status"] == "eof", target=2)
    assert last["pts"] == pytest.approx(0.9)
    assert last["rgba"][0] > 150
    source.reset(2)
    wait_for(source, lambda update: "rgba" in update)
    source.play(time.monotonic())
    wait_for(source, lambda update: update.get("frame_id", 0) >= 2, target=None)
    source.pause()
    time.sleep(0.05)
    paused = source.poll(time.monotonic(), None, 1)
    time.sleep(0.2)
    assert source.poll(time.monotonic(), None, 1)["frame_id"] == paused["frame_id"]
    source.play(time.monotonic())
    resumed = wait_for(
        source, lambda update: update.get("frame_id", 0) > paused["frame_id"], target=None
    )
    assert resumed["pts"] >= paused["pts"]
    source.prepare(3, {"kind": "video", "file": str(path), "at_end": True})
    frozen = wait_for(source, lambda update: "rgba" in update)
    assert frozen["status"] == "eof" and frozen["pts"] == pytest.approx(0.9)
    assert frozen["rgba"][0] > 150


def test_stalled_decoder_poll_and_timeout(source, tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGBA", (4, 4)).save(path)
    source.prepare(1, {"kind": "image", "file": str(path)})
    source.started -= 6
    start = time.perf_counter()
    update = source.poll(time.monotonic(), None, 0)
    assert time.perf_counter() - start < 0.1
    assert update["status"] == "error" and "5 s" in update["error"]


def stalled_decoder(spec, connection):
    import struct
    from multiprocessing.shared_memory import SharedMemory

    from manimcue.player.decoder_worker import SLOT

    memory = SharedMemory(create=True, size=72)
    try:
        memory.buf[:] = bytes(memory.size)
        memory.buf[64:68] = bytes((1, 2, 3, 4))
        SLOT.pack_into(memory.buf, 0, 2, 0, 0)
        struct.pack_into("<d", memory.buf, 48, time.monotonic())
        connection.send(
            {"type": "memory", "name": memory.name, "width": 1, "height": 1, "duration": 60}
        )
        time.sleep(60)
    finally:
        memory.close()
        memory.unlink()


def test_ready_decoder_hang_keeps_frame_and_nonblocking_control(source, monkeypatch):
    import manimcue.player.sources_av as adapter

    monkeypatch.setattr(adapter, "run_decoder", stalled_decoder)
    source.prepare(42, {"kind": "video", "file": "unused"})
    ready = wait_for(source, lambda u: "rgba" in u)
    start = time.perf_counter()
    for index in range(10000):
        source.poll(time.monotonic(), index, 0)
        source.pause()
        source.play(time.monotonic())
    assert time.perf_counter() - start < 1
    error = source.poll(time.monotonic() + 3, None, 1)
    assert error["status"] == "error" and "2 s" in error["error"]
    assert error["rgba"] == ready["rgba"]


def test_gif_loop_uses_same_generation(source, tmp_path):
    path = tmp_path / "loop.gif"
    first = Image.new("RGBA", (2, 2), "red")
    first.save(path, save_all=True, append_images=[Image.new("RGBA", (2, 2), "blue")], duration=100)
    source.prepare(1, {"kind": "gif", "file": str(path), "loop": True})
    wait_for(source, lambda u: "rgba" in u)
    last = wait_for(source, lambda u: u.get("pts") == 0.1, target=0.15)
    wrapped = wait_for(source, lambda u: u.get("frame_id", 0) > last["frame_id"], target=0.21)
    assert wrapped["pts"] == 0 and wrapped["generation"] == 1
    source.request_loop_exit()
    ended = wait_for(source, lambda update: update["status"] == "eof", target=0.5)
    assert ended["pts"] == pytest.approx(0.1)
    assert ended["rgba"][:4] == bytes((0, 0, 255, 255))


@pytest.mark.parametrize("timestamps", [[None], [0, 0]])
def test_pts_preflight_rejects_before_first_image(monkeypatch, timestamps):
    import sys
    from types import SimpleNamespace

    from manimcue.player.decoder_worker import run_decoder

    class Connection:
        def __init__(self):
            self.messages = []

        def send(self, message):
            self.messages.append(message)

        def close(self):
            pass

    stream = SimpleNamespace(duration=1, time_base=1, width=1, height=1)
    container = SimpleNamespace(
        streams=SimpleNamespace(video=[stream]),
        close=lambda: None,
        demux=lambda stream: iter(
            SimpleNamespace(size=1, pts=pts, dts=index) for index, pts in enumerate(timestamps)
        ),
    )
    monkeypatch.setitem(sys.modules, "av", SimpleNamespace(open=lambda path: container))
    connection = Connection()
    run_decoder({"media": {"kind": "video", "file": "test"}, "control": [0] * 12}, connection)
    assert len(connection.messages) == 1
    assert connection.messages[0]["type"] == "error" and "PTS" in connection.messages[0]["error"]


def vanished_memory_decoder(spec, connection):
    from uuid import uuid4

    connection.send(
        {
            "type": "memory",
            "name": "f10_missing_" + uuid4().hex,
            "width": 1,
            "height": 1,
            "duration": 1,
        }
    )
    connection.close()
