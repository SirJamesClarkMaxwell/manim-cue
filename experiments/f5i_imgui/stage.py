"""Wspólny kod PoC ImGui: ten sam plik działa na PC (GLFW + OpenGL) i w przeglądarce (Pyodide + WebGL).

Nie importuje niczego zależnego od platformy. Źródła obrazu (wideo, live) dostarcza warstwa platformy;
tu jest tylko układ, wspólny zegar (D17: wspólny start i pauza), rysowanie i metryki.

Źródło to dowolny obiekt z polami i metodami:
    texture -> (tex_id, width, height) | None   ostatnia wgrana klatka
    ready -> bool                                pierwsza klatka gotowa
    update(t: float | None) -> None              t = czas wspólnego zegara albo None przed startem
    play() / pause() -> None                     przeglądarka steruje <video>; PC ignoruje
    uploads: list[float]                         czasy wgrania nowych klatek (perf_counter)
    close() -> None
"""

import itertools
import statistics
import time
from dataclasses import dataclass, field

from imgui_bundle import hello_imgui, imgui

FRAME_ASPECT = 16 / 9
LIVE_RECT = (0.36, 0.55, 0.28, 0.28)
NOTES = "PoC ImGui: baza, klipy i live; spacja pauzuje, strzałki zmieniają slajd."


def clip_rect(index):
    """Klipy obok siebie w górnej części kadru (te same prostokąty na PC i w przeglądarce)."""
    return (0.03 + index * 0.32, 0.08, 0.30, 0.30)


def runner_params(post_init, show_gui, before_exit, title, size, viewports, vsync=True):
    """Wspólne ustawienia hello_imgui; w Pyodide `hello_imgui.run` jest podmieniane na pętlę requestAnimationFrame."""
    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = title
    params.app_window_params.window_geometry.size = size
    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.no_default_window
    )
    params.imgui_window_params.enable_viewports = (
        viewports  # Info da się wyciągnąć na drugi monitor (tylko PC)
    )
    params.fps_idling.enable_idling = False
    params.ini_disable = True  # bez pliku ustawień w katalogu roboczym
    params.fps_idling.vsync_to_monitor = vsync
    params.callbacks.post_init = post_init
    params.callbacks.show_gui = show_gui
    params.callbacks.before_exit = before_exit
    return params


def fit(aspect, x, y, w, h):
    """Największy prostokąt o proporcjach `aspect` wyśrodkowany w (x, y, w, h); pasy po bokach albo u góry."""
    if w <= 0 or h <= 0:
        return x, y, 0.0, 0.0
    if w / h > aspect:
        fw, fh = h * aspect, h
    else:
        fw, fh = w, w / aspect
    return x + (w - fw) / 2, y + (h - fh) / 2, fw, fh


def layer_box(frame, rect):
    """Prostokąt warstwy w pikselach okna; `rect` jak `Rect` manim-cue: (x, y, w, h) w ułamkach kadru od lewej góry."""
    fx, fy, fw, fh = frame
    rx, ry, rw, rh = rect
    return fx + rx * fw, fy + ry * fh, rw * fw, rh * fh


def percentile(values, q):
    """Najbliższa ranga, jak w raportach F5."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q / 100 * len(ordered) + 0.5) - 1))]


def interval_stats(times, start, end):
    """Klatki/s i interwały [ms] dla zdarzeń z okna pomiarowego."""
    window = [t for t in times if start <= t <= end]
    gaps = [(b - a) * 1000 for a, b in itertools.pairwise(window)]
    return {
        "count": len(window),
        "fps": round(len(window) / (end - start), 2) if end > start else None,
        "p50_ms": round(statistics.median(gaps), 2) if gaps else None,
        "p95_ms": round(percentile(gaps, 95), 2) if gaps else None,
        "max_ms": round(max(gaps), 2) if gaps else None,
    }


@dataclass
class Layer:
    name: str
    rect: tuple[float, float, float, float]
    source: object | None
    aspect: float = FRAME_ASPECT
    border: bool = False


@dataclass
class Slide:
    notes: str
    base: object | None
    layers: list[Layer] = field(default_factory=list)


class Stage:
    """Slajdy, wspólny zegar i GUI; jedna instancja na aplikację, wywoływana z jednego wątku."""

    def __init__(
        self, slides, preview=None, show_info=True, warmup=3.0, seconds=20.0, on_done=None
    ):
        self.slides = slides
        self.preview = (
            preview  # osobne źródła podglądu następnego slajdu (osobne dekodery, jak w Qt)
        )
        self.show_info = show_info
        self.warmup = warmup
        self.seconds = seconds
        self.on_done = on_done
        self.index = 0
        self.started_at = None  # perf_counter startu wspólnego zegara
        self.paused_at = None
        self.paused_total = 0.0
        self.render_times = []
        self.cpu_start = None
        self.wall_start = None
        self.result = None

    # --- zegar D17 ---------------------------------------------------------------------------
    def sources(self):
        slide = self.slides[self.index]
        found = [slide.base] + [layer.source for layer in slide.layers]
        if self.show_info and self.preview is not None:
            found += [self.preview.base] + [layer.source for layer in self.preview.layers]
        return [source for source in found if source is not None]

    def clock(self, now):
        if self.started_at is None:
            return None
        reference = self.paused_at if self.paused_at is not None else now
        return reference - self.started_at - self.paused_total

    def toggle_pause(self, now):
        if self.started_at is None:
            return
        if self.paused_at is None:
            self.paused_at = now
            for source in self.sources():
                source.pause()
        else:
            self.paused_total += now - self.paused_at
            self.paused_at = None
            for source in self.sources():
                source.play()

    # --- rysowanie ---------------------------------------------------------------------------
    def draw_slide(self, draw_list, slide, x, y, w, h):
        frame = fit(FRAME_ASPECT, x, y, w, h)
        fx, fy, fw, fh = frame
        draw_list.add_rect_filled(imgui.ImVec2(fx, fy), imgui.ImVec2(fx + fw, fy + fh), 0xFF000000)
        self.draw_source(draw_list, slide.base, frame, FRAME_ASPECT)
        for layer in slide.layers:
            box = layer_box(frame, layer.rect)
            self.draw_source(draw_list, layer.source, box, layer.aspect)
            if layer.border:
                bx, by, bw, bh = box
                draw_list.add_rect(
                    imgui.ImVec2(bx, by),
                    imgui.ImVec2(bx + bw, by + bh),
                    0xFF00C8FF,
                    rounding=0,
                    thickness=3,
                )

    @staticmethod
    def draw_source(draw_list, source, box, aspect):
        texture = source.texture if source is not None else None
        if texture is None:
            bx, by, bw, bh = box
            draw_list.add_rect(imgui.ImVec2(bx, by), imgui.ImVec2(bx + bw, by + bh), 0xFF555555)
            return
        tex_id, _, _ = texture
        ix, iy, iw, ih = fit(aspect, *box)
        draw_list.add_image(
            imgui.ImTextureRef(tex_id), imgui.ImVec2(ix, iy), imgui.ImVec2(ix + iw, iy + ih)
        )

    def gui(self):
        now = time.perf_counter()
        self.render_times.append(now)
        if self.started_at is None and all(source.ready for source in self.sources()):
            self.started_at = now
            for source in self.sources():
                source.play()
        t = self.clock(now)
        for source in self.sources():
            source.update(t)
        self.handle_keys(now)

        viewport = imgui.get_main_viewport()
        imgui.set_next_window_pos(viewport.work_pos)
        imgui.set_next_window_size(viewport.work_size)
        flags = (
            imgui.WindowFlags_.no_decoration
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_saved_settings
            | imgui.WindowFlags_.no_bring_to_front_on_focus
            | imgui.WindowFlags_.no_background
        )
        imgui.begin("stage", None, flags)
        pos, size = viewport.work_pos, viewport.work_size
        self.draw_slide(
            imgui.get_window_draw_list(), self.slides[self.index], pos.x, pos.y, size.x, size.y
        )
        imgui.end()

        if self.show_info:
            imgui.set_next_window_size(imgui.ImVec2(520, 640), imgui.Cond_.first_use_ever)
            imgui.begin("Info")
            slide = self.slides[self.index]
            imgui.text_wrapped(slide.notes)
            imgui.text(
                f"slajd {self.index + 1}/{len(self.slides)}  zegar {t if t is not None else 0:.2f} s"
            )
            imgui.text(f"render {hello_imgui.frame_rate():.1f} kl./s")
            avail = imgui.get_content_region_avail()
            height = avail.x * 9 / 16
            draw_list = imgui.get_window_draw_list()
            imgui.text("bieżący")
            cursor = imgui.get_cursor_screen_pos()
            self.draw_slide(draw_list, slide, cursor.x, cursor.y, avail.x, height)
            imgui.dummy(imgui.ImVec2(avail.x, height))
            imgui.text("następny")
            cursor = imgui.get_cursor_screen_pos()
            if self.preview is not None:
                self.draw_slide(draw_list, self.preview, cursor.x, cursor.y, avail.x, height)
            imgui.dummy(imgui.ImVec2(avail.x, height))
            imgui.end()

        self.measure(now)

    def handle_keys(self, now):
        if imgui.is_key_pressed(imgui.Key.space, False):
            self.toggle_pause(now)
        if imgui.is_key_pressed(imgui.Key.right_arrow, False) and self.index + 1 < len(self.slides):
            self.index += 1
        if imgui.is_key_pressed(imgui.Key.left_arrow, False) and self.index > 0:
            self.index -= 1

    # --- pomiar ------------------------------------------------------------------------------
    def measure(self, now):
        if self.started_at is None or self.result is not None or self.seconds <= 0:
            return
        elapsed = now - self.started_at
        if self.cpu_start is None and elapsed >= self.warmup:
            self.cpu_start = time.process_time()
            self.wall_start = now
        if self.wall_start is not None and now - self.wall_start >= self.seconds:
            self.result = self.summary(self.wall_start, now)
            if self.on_done is not None:
                self.on_done(self.result)

    def summary(self, start, end):
        streams = {}
        slide = self.slides[self.index]
        named = [("base", slide.base)] + [(layer.name, layer.source) for layer in slide.layers]
        if self.show_info and self.preview is not None:
            named += [("preview_base", self.preview.base)]
            named += [(f"preview_{layer.name}", layer.source) for layer in self.preview.layers]
        for name, source in named:
            if source is not None:
                streams[name] = interval_stats(source.uploads, start, end)
                extra = getattr(source, "extra_metrics", None)
                if extra is not None:
                    streams[name].update(extra())
        return {
            "window_s": round(end - start, 3),
            "render": interval_stats(self.render_times, start, end),
            "cpu_percent_one_core": round(
                (time.process_time() - self.cpu_start) / (end - start) * 100, 1
            ),
            "streams": streams,
            "info": self.show_info,
        }
