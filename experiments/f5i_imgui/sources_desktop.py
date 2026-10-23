"""Źródła obrazu na PC: dekodowanie PyAV i klatki live z pamięci współdzielonej → tekstury OpenGL.

Wszystko wywoływane z wątku GUI (jedyny wątek kodu aplikacji); FFmpeg dekoduje we własnych wątkach.
"""

import time

import av
import numpy as np
from OpenGL import GL


class Texture:
    """Tekstura RGBA8 tworzona raz i nadpisywana `glTexSubImage2D` przy każdej nowej klatce."""

    def __init__(self, width, height):
        self.width, self.height = width, height
        self.id = int(GL.glGenTextures(1))
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.id)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            GL.GL_RGBA8,
            width,
            height,
            0,
            GL.GL_RGBA,
            GL.GL_UNSIGNED_BYTE,
            None,
        )

    def upload(self, rgba):
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.id)
        GL.glTexSubImage2D(
            GL.GL_TEXTURE_2D,
            0,
            0,
            0,
            self.width,
            self.height,
            GL.GL_RGBA,
            GL.GL_UNSIGNED_BYTE,
            rgba,
        )

    def close(self):
        GL.glDeleteTextures([self.id])


class VideoSource:
    """Klip CFR prowadzony wspólnym zegarem: klatka = floor(t · fps), pętla przez seek do początku.

    `size` to rozmiar konwersji i tekstury; mniejszy od filmu oznacza, że FFmpeg skaluje już przy
    konwersji do RGBA (ta sama sztuczka co „dekodowanie w rozmiarze prostokąta” dla Qt).
    """

    def __init__(self, path, size=None, loop=True):
        self.container = av.open(str(path))
        self.stream = self.container.streams.video[0]
        self.stream.thread_type = "AUTO"
        self.fps = float(self.stream.average_rate)
        duration = float(self.stream.duration * self.stream.time_base)
        self.frame_count = self.stream.frames or round(duration * self.fps)
        self.width, self.height = size or (self.stream.width, self.stream.height)
        self.loop = loop
        self.texture_obj = None
        self.decoder = self.container.decode(self.stream)
        self.loop_index = 0
        self.current = -1  # indeks wgranej klatki w obrębie pętli
        self.pending = None  # zdekodowana, jeszcze niepotrzebna klatka
        self.uploads = []
        self.decoded = 0

    @property
    def ready(self):
        return self.current >= 0

    @property
    def texture(self):
        if self.texture_obj is None or self.current < 0:
            return None
        return self.texture_obj.id, self.width, self.height

    def play(self):
        pass

    def pause(self):
        pass

    def next_frame(self):
        if self.pending is not None:
            frame, self.pending = self.pending, None
            return frame
        try:
            frame = next(self.decoder)
        except StopIteration:
            return None
        self.decoded += 1
        return frame

    def update(self, t):
        target = 0 if t is None else int(t * self.fps)
        loop_index, target = divmod(target, self.frame_count) if self.loop else (0, target)
        if loop_index != self.loop_index:
            self.container.seek(0, stream=self.stream)
            self.decoder = self.container.decode(self.stream)
            self.loop_index, self.current, self.pending = loop_index, -1, None
        if target <= self.current:
            return
        chosen = None
        while True:
            frame = self.next_frame()
            if frame is None:
                break
            index = round(frame.time * self.fps)
            if index > target:
                self.pending = frame
                break
            chosen, self.current = frame, index
        if chosen is None:
            return
        if self.texture_obj is None:
            self.texture_obj = Texture(self.width, self.height)
        rgba = chosen.to_ndarray(format="rgba", width=self.width, height=self.height)
        self.texture_obj.upload(np.ascontiguousarray(rgba))
        self.uploads.append(time.perf_counter())

    def extra_metrics(self):
        return {"decoded_total": self.decoded, "size": [self.width, self.height]}

    def close(self):
        if self.texture_obj is not None:
            self.texture_obj.close()
        self.container.close()


class LiveSource:
    """Proces live manim-cue bez zmian: `LiveSession` + pamięć współdzielona, klatki RGBA do tekstury."""

    def __init__(self, spec, cue=None):
        from manimcue.live_session import LiveSession

        self.session = LiveSession()
        self.session.start(spec)
        self.cue = cue
        self.texture_obj = None
        self.size = (spec.width, spec.height)
        self.uploads = []
        self.frame_ids = []

    @property
    def ready(self):
        return self.texture_obj is not None

    @property
    def texture(self):
        return None if self.texture_obj is None else (self.texture_obj.id, *self.size)

    def play(self):
        pass

    def pause(self):
        pass  # live działa dalej w pauzie (D17)

    def update(self, t):
        self.session.poll()
        frame = self.session.try_read_frame()
        if frame is None:
            return
        if self.texture_obj is None:
            self.size = (frame.width, frame.height)
            self.texture_obj = Texture(frame.width, frame.height)
            if self.cue:
                self.session.send(self.cue)
        pixels = np.frombuffer(frame.pixels, dtype=np.uint8).reshape(frame.height, frame.width, 4)
        self.texture_obj.upload(pixels)
        self.uploads.append(time.perf_counter())
        self.frame_ids.append(frame.frame_id)

    def extra_metrics(self):
        return {"state": self.session.state, "error": self.session.error}

    def close(self, timeout=5.0):
        self.session.request_stop()
        deadline = time.monotonic() + timeout
        while self.session.running and time.monotonic() < deadline:
            self.session.poll()
            time.sleep(0.01)
        if self.texture_obj is not None:
            self.texture_obj.close()
