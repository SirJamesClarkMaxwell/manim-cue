"""Źródła obrazu w przeglądarce (Pyodide): `<video>` dekodowane przez przeglądarkę → tekstura WebGL2.

`texImage2D(..., video)` kopiuje klatkę na GPU bez przejścia przez Pythona; teksturę rejestruje most
`imgui_bundle.webgl`, więc `stage.py` rysuje ją tak samo jak teksturę OpenGL na PC.
"""

import time

import js
from imgui_bundle import webgl
from pyodide.ffi import create_proxy

_context = None


def gl():
    """Ten sam kontekst WebGL2, na którym rysuje ImGui (getContext zwraca istniejący)."""
    global _context
    if _context is None:
        _context = js.document.getElementById("canvas").getContext("webgl2")
    return _context


class HtmlVideoSource:
    """Wideo gra samo (zegar przeglądarki); wspólny start i pauza przez play()/pause() wszystkich naraz."""

    def __init__(self, url, loop=True):
        video = js.document.createElement("video")
        video.muted = True
        video.loop = loop
        video.playsInline = True
        video.preload = "auto"
        video.src = url
        js.document.getElementById("videos").appendChild(video)
        self.video = video
        self.loaded = False
        self.fresh = False
        self.texture_js = None
        self.texture_id = None
        self.uploads = []
        self.presented = []
        self._on_loaded = create_proxy(self.loaded_data)
        self._on_frame = create_proxy(self.frame_presented)
        video.addEventListener("loadeddata", self._on_loaded)
        video.requestVideoFrameCallback(self._on_frame)

    def loaded_data(self, event):
        self.loaded = self.fresh = True

    def frame_presented(self, now, metadata):
        self.fresh = True
        self.presented.append(time.perf_counter())
        self.video.requestVideoFrameCallback(self._on_frame)

    @property
    def ready(self):
        return bool(self.uploads)

    @property
    def texture(self):
        if self.texture_id is None or not self.uploads:
            return None
        return self.texture_id, self.video.videoWidth, self.video.videoHeight

    def play(self):
        self.video.play()

    def pause(self):
        self.video.pause()

    def update(self, t):
        if not self.loaded or not self.fresh:
            return
        context = gl()
        if self.texture_js is None:
            self.texture_js = context.createTexture()
            context.bindTexture(context.TEXTURE_2D, self.texture_js)
            for name, value in (
                ("TEXTURE_MIN_FILTER", "LINEAR"),
                ("TEXTURE_MAG_FILTER", "LINEAR"),
                ("TEXTURE_WRAP_S", "CLAMP_TO_EDGE"),
                ("TEXTURE_WRAP_T", "CLAMP_TO_EDGE"),
            ):
                context.texParameteri(
                    context.TEXTURE_2D, getattr(context, name), getattr(context, value)
                )
            self.texture_id = webgl.register_texture(self.texture_js)
        context.bindTexture(context.TEXTURE_2D, self.texture_js)
        context.texImage2D(
            context.TEXTURE_2D, 0, context.RGBA, context.RGBA, context.UNSIGNED_BYTE, self.video
        )
        self.fresh = False
        self.uploads.append(time.perf_counter())

    def extra_metrics(self):
        quality = self.video.getVideoPlaybackQuality()
        return {
            "presented_total": len(self.presented),
            "dropped_total": quality.droppedVideoFrames,
            "decoded_total": quality.totalVideoFrames,
        }

    def close(self):
        self.video.pause()
        if self.texture_id is not None:
            webgl.unregister_texture(self.texture_id)
            gl().deleteTexture(self.texture_js)
