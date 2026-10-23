"""Wejście PoC w przeglądarce: ten sam `stage.py` co na PC, źródła z `sources_web.py`.

Parametry z adresu strony: ?clips=3&warmup=3&seconds=20&info=1. Wynik idzie POST-em do /metrics.
Live w przeglądarce jest poza tym PoC (miejsce na panel zostaje); strumień klatek przez WebSocket
to następny krok.
"""

import json

import js
from imgui_bundle import hello_imgui
from pyodide.ffi import to_js
from sources_web import HtmlVideoSource
from stage import LIVE_RECT, NOTES, Layer, Slide, Stage, clip_rect, runner_params

query = js.URLSearchParams.new(js.location.search)


def param(name, default):
    value = query.get(name)
    return type(default)(value) if value is not None else default


clips = param("clips", 3)
show_info = param("info", 1) == 1
state = {}


def slide(with_live_placeholder):
    layers = [
        Layer(f"clip_{i + 1}", clip_rect(i), HtmlVideoSource(f"/media/{i + 1}.mp4"))
        for i in range(clips)
    ]
    if with_live_placeholder:
        layers.append(Layer("live", LIVE_RECT, None, border=True))
    return Slide(NOTES, HtmlVideoSource("/media/0.mp4"), layers)


def done(result):
    from sources_web import gl

    context = gl()
    debug = context.getExtension("WEBGL_debug_renderer_info")
    renderer = context.getParameter(debug.UNMASKED_RENDERER_WEBGL) if debug else None
    result.update(clips=clips, live=False, platform="web", webgl_renderer=str(renderer))
    result.update(user_agent=str(js.navigator.userAgent))
    body = json.dumps(result)
    options = to_js({"method": "POST", "body": body}, dict_converter=js.Object.fromEntries)
    js.fetch("/metrics", options)
    hello_imgui.get_runner_params().app_shall_exit = True


def post_init():
    preview = slide(False) if show_info else None
    state["stage"] = Stage(
        [slide(True)], preview, show_info, param("warmup", 3.0), param("seconds", 20.0), done
    )


def gui():
    state["stage"].gui()


def before_exit():
    stage = state.get("stage")
    if stage is not None:
        for source in stage.sources():
            source.close()


size = (js.window.innerWidth, js.window.innerHeight)
hello_imgui.run(
    runner_params(post_init, gui, before_exit, "manim-cue: PoC ImGui (web)", size, False)
)
