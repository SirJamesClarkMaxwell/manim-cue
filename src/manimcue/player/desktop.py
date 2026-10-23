"""Uruchomienie natywnego playera GLFW/OpenGL3 w jednym wątku aplikacji."""

import ctypes as ct
import math
import os
import time
import warnings

from .app import App
from .clock import media_time
from .geometry import fit
from .info import render_info, state_text
from .input import route
from .keys import bindings
from .live import view
from .stage import compose, draw


def screen_options(options: dict, count: int) -> dict:
    """Rozstrzygnij ekrany i widoczność Info przed utworzeniem okien."""
    if count < 1:
        raise ValueError("Brak monitorów GLFW")
    main = options.get("screen_number")
    main = 0 if main is None else main
    info = options.get("info_window_screen_number")
    hide = options.get("hide_info_window")
    show = hide == "never" or (hide is None and count > 1)
    for index in (main, info if show else None):
        if index is not None and not 0 <= index < count:
            raise ValueError(f"Invalid screen number {index}; allowed 0..{count - 1}")
    if not show and info is not None:
        warnings.warn("Ignoring --info-window-screen because Info is hidden", stacklevel=2)
        info = None
    if info is None:
        info = (main + 1) % count
    return {**options, "screen_number": main, "info_window_screen_number": info, "show_info": show}


def start_options(manifest: dict, options: dict) -> dict:
    """Sprawdź indeksy przed uruchomieniem okien i procesów dekodowania."""
    decks = manifest["presentations"]
    deck = options.get("start_at_scene_number", 0)
    slide = options.get("start_at_slide_number", 0)
    if deck < 0:
        deck += len(decks)
    if not 0 <= deck < len(decks):
        raise ValueError("Niepoprawny indeks prezentacji")
    if slide < 0:
        slide += len(decks[deck]["slides"])
    if not 0 <= slide < len(decks[deck]["slides"]):
        raise ValueError("Niepoprawny indeks slajdu")
    return {**options, "start_at_scene_number": deck, "start_at_slide_number": slide}


def _pointer(value):
    if isinstance(value, int):
        return value
    if value is None:
        return 0
    name = ct.pythonapi.PyCapsule_GetName
    name.argtypes, name.restype = [ct.py_object], ct.c_char_p
    pointer = ct.pythonapi.PyCapsule_GetPointer
    pointer.argtypes, pointer.restype = [ct.py_object, ct.c_char_p], ct.c_void_p
    return pointer(value, name(value))


class Windows:
    """Sterowanie per-window tą samą GLFW DLL, której używa hello_imgui."""

    def __init__(self):
        self.dll = ct.CDLL(os.environ["PYGLFW_LIBRARY"])
        for name, result, args in [
            ("glfwGetMonitors", ct.POINTER(ct.c_void_p), [ct.POINTER(ct.c_int)]),
            ("glfwGetMonitorPos", None, [ct.c_void_p, ct.c_void_p, ct.c_void_p]),
            ("glfwGetVideoMode", ct.POINTER(ct.c_int), [ct.c_void_p]),
            ("glfwGetWindowPos", None, [ct.c_void_p, ct.c_void_p, ct.c_void_p]),
            ("glfwGetWindowSize", None, [ct.c_void_p, ct.c_void_p, ct.c_void_p]),
            ("glfwSetWindowPos", None, [ct.c_void_p, ct.c_int, ct.c_int]),
            ("glfwSetWindowSize", None, [ct.c_void_p, ct.c_int, ct.c_int]),
            ("glfwSetWindowAttrib", None, [ct.c_void_p, ct.c_int, ct.c_int]),
            ("glfwSetInputMode", None, [ct.c_void_p, ct.c_int, ct.c_int]),
            ("glfwSetWindowShouldClose", None, [ct.c_void_p, ct.c_int]),
            ("glfwSetWindowCloseCallback", ct.c_void_p, [ct.c_void_p, ct.c_void_p]),
        ]:
            function = getattr(self.dll, name)
            function.restype, function.argtypes = result, args
        self.handles, self.saved = {}, {}
        self.fullscreen, self.hide_mouse = False, False
        self.close_requested = False
        self.callback = ct.CFUNCTYPE(None, ct.c_void_p)(self._close)
        count = ct.c_int()
        pointers = self.dll.glfwGetMonitors(ct.byref(count))
        self.monitors = []
        for index in range(count.value):
            x, y = ct.c_int(), ct.c_int()
            self.dll.glfwGetMonitorPos(pointers[index], ct.byref(x), ct.byref(y))
            mode = self.dll.glfwGetVideoMode(pointers[index])
            self.monitors.append((x.value, y.value, mode[0], mode[1]))

    def _close(self, handle):
        self.dll.glfwSetWindowShouldClose(handle, 0)
        self.close_requested = True

    def attach(self, name, handle, monitor):
        if handle and name not in self.handles:
            self.handles[name] = handle
            self.dll.glfwSetWindowCloseCallback(handle, self.callback)
            x, y, _, _ = self.monitors[monitor]
            self.dll.glfwSetWindowPos(handle, x + 60, y + 60)

    def toggle_fullscreen(self, options):
        for name, handle in self.handles.items():
            if not self.fullscreen:
                x, y, w, h = ct.c_int(), ct.c_int(), ct.c_int(), ct.c_int()
                self.dll.glfwGetWindowPos(handle, ct.byref(x), ct.byref(y))
                self.dll.glfwGetWindowSize(handle, ct.byref(w), ct.byref(h))
                self.saved[name] = x.value, y.value, w.value, h.value
                monitor = (
                    options["screen_number"]
                    if name == "main"
                    else options["info_window_screen_number"]
                )
                geometry = self.monitors[monitor]
            else:
                geometry = self.saved[name]
            self.dll.glfwSetWindowAttrib(handle, 0x20005, int(self.fullscreen))
            self.dll.glfwSetWindowPos(handle, *geometry[:2])
            self.dll.glfwSetWindowSize(handle, *geometry[2:])
        self.fullscreen = not self.fullscreen

    def toggle_mouse(self):
        self.hide_mouse = not self.hide_mouse
        self.dll.glfwSetInputMode(
            self.handles["main"], 0x33001, 0x34002 if self.hide_mouse else 0x34001
        )


def warn_audio(manifest):
    """D44: jedno ostrzeżenie na materiał ze ścieżką audio, także powtarzany."""
    import av

    seen = set()
    for presentation in manifest["presentations"]:
        for slide in presentation["slides"]:
            for media in [slide, *slide.get("layers", [])]:
                path = media.get("file")
                if media["kind"] != "video" or path in seen:
                    continue
                seen.add(path)
                with av.open(path) as container:
                    if container.streams.audio:
                        warnings.warn(f"ImGui PC: audio nie jest odtwarzane: {path}", stacklevel=2)


def run_desktop(manifest: dict, options: dict) -> int:
    """Uruchom dwa viewporty z trwałymi teksturami i wspólnym shutdown."""
    from imgui_bundle import hello_imgui, imgui, immapp

    options = start_options(manifest, options)
    rate = options.get("playback_rate", 1)
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError("playback_rate musi być skończone i dodatnie")
    keymap = bindings(options.get("config", {}))
    warn_audio(manifest)
    params = hello_imgui.RunnerParams()
    params.platform_backend_type = hello_imgui.PlatformBackendType.glfw
    params.renderer_backend_type = hello_imgui.RendererBackendType.open_gl3
    params.ini_disable = True
    params.fps_idling.enable_idling = False
    params.fps_idling.vsync_to_monitor = True
    params.app_window_params.window_title = "manim-cue"
    params.app_window_params.window_geometry.size = (960, 540)
    params.imgui_window_params.enable_viewports = True
    params.imgui_window_params.default_imgui_window_type = (
        hello_imgui.DefaultImGuiWindowType.no_default_window
    )
    runtime = {}

    def setup():
        io = imgui.get_io()
        io.config_viewports_no_auto_merge = True
        io.config_viewports_no_decoration = False

    def post_init():
        windows = Windows()
        selected = screen_options(options, len(windows.monitors))
        app = App(manifest, selected)
        runtime.update(windows=windows, options=selected, app=app, overlay=False, first=True)

    def action(effect, now):
        app, windows = runtime["app"], runtime["windows"]
        kind = effect["type"]
        if kind == "full_screen":
            windows.toggle_fullscreen(runtime["options"])
        elif kind == "hide_mouse":
            windows.toggle_mouse()
        elif kind == "presenter_state":
            runtime["overlay"] = not runtime["overlay"]
        elif kind == "release_focus":
            app.live.active = None
        elif kind == "focus_live":
            index = int(effect["index"])
            if index in app.live.sessions and index not in app.live.failed:
                app.live.active = index
        elif kind == "cue":
            app.live.send(effect["direction"])
        elif kind == "view":
            command = next(
                (
                    command
                    for command in runtime.get("commands", [])
                    if command.get("source") == str(app.live.active)
                ),
                None,
            )
            if command:
                converted = view(effect, command["container"])
                if converted:
                    app.live.send(converted["command"])
        else:
            app.dispatch(effect, now)

    def gui():
        app, windows = runtime["app"], runtime["windows"]
        now = time.monotonic()
        io = imgui.get_io()

        def process_input():
            io = imgui.get_io()
            if windows.close_requested and not app.state.get("closing"):
                app.dispatch({"type": "quit"}, now)
            input_state = {
                "bindings": keymap,
                "active_live": app.live.active,
                "reserved": any(history.reserved for history in app.live.histories.values()),
                "editing_text": io.want_text_input,
            }
            if io.app_focus_lost:
                app.live.active = None
            queued, runtime["pending_input"] = runtime.get("pending_input", []), []
            for effect in queued:
                if effect.get("entry_id") == app.state["entry_id"]:
                    action(effect, now)
            for key in dict.fromkeys(key for key, _ in keymap):
                input_state["active_live"] = app.live.active
                input_state["reserved"] = any(
                    history.reserved for history in app.live.histories.values()
                )
                if imgui.is_key_pressed(getattr(imgui.Key, key), True):
                    actual = [
                        name
                        for name, enabled in [
                            ("shift", io.key_shift),
                            ("ctrl", io.key_ctrl),
                            ("alt", io.key_alt),
                            ("super", io.key_super),
                        ]
                        if enabled
                    ]
                    for effect in route(
                        {
                            "type": "key",
                            "key": key,
                            "modifiers": actual,
                            "repeat": not imgui.is_key_pressed(getattr(imgui.Key, key), False),
                        },
                        input_state,
                    ):
                        action(effect, now)
            if imgui.is_key_pressed(imgui.Key.escape, False):
                for effect in route({"type": "key", "key": "escape"}, input_state):
                    action(effect, now)
            input_state["active_live"] = app.live.active
            runtime["input_state"] = input_state

        state = app.tick(now, process_input)
        input_state = runtime["input_state"]
        viewport = imgui.get_main_viewport()
        windows.attach(
            "main", _pointer(viewport.platform_handle), runtime["options"]["screen_number"]
        )
        imgui.set_next_window_pos(viewport.work_pos)
        imgui.set_next_window_size(viewport.work_size)
        # Bez tego no_auto_merge daje scenie osobne okno systemowe nad pustym głównym.
        imgui.set_next_window_viewport(viewport.id_)
        # Scena bez ramki i zaokrągleń ImGui, jak kadr w playerze Qt.
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_rounding, 0.0)
        imgui.begin(
            "stage",
            None,
            imgui.WindowFlags_.no_decoration
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_saved_settings,
        )
        imgui.pop_style_var(2)
        main_box = (
            viewport.work_pos.x,
            viewport.work_pos.y,
            viewport.work_size.x,
            viewport.work_size.y,
        )
        commands = compose(
            {
                "resolution": app.state["resolution"],
                "slide": app._slide(),
                "viewport": main_box,
                "aspect_ratio": options.get("aspect_ratio", "keep"),
                "reverse": app.state["reverse"],
            },
            app.frames,
            media_time(app.motion_clock, now),
        )
        runtime["commands"] = commands
        draw(commands, imgui.get_window_draw_list())
        if state.get("message"):
            imgui.text_wrapped(state["message"])
        if runtime["overlay"]:
            imgui.text_wrapped(state_text(state))
        if imgui.is_window_hovered():
            input_state.update(
                commands=commands, live_indices=[str(index) for index in app.live.sessions]
            )
            if imgui.is_mouse_clicked(0):
                point = io.mouse_pos
                for effect in route({"type": "click", "point": (point.x, point.y)}, input_state):
                    runtime.setdefault("pending_input", []).append(
                        {**effect, "entry_id": app.state["entry_id"]}
                    )
            for event in [{"type": "wheel", "steps": io.mouse_wheel}] if io.mouse_wheel else []:
                for effect in route(event, input_state):
                    runtime.setdefault("pending_input", []).append(
                        {**effect, "entry_id": app.state["entry_id"]}
                    )
            if imgui.is_mouse_dragging(0):
                for effect in route(
                    {
                        "type": "drag",
                        "delta": (io.mouse_delta.x, io.mouse_delta.y),
                        "shift": io.key_shift,
                    },
                    input_state,
                ):
                    runtime.setdefault("pending_input", []).append(
                        {**effect, "entry_id": app.state["entry_id"]}
                    )
            if imgui.is_mouse_double_clicked(0):
                for effect in route({"type": "double_click"}, input_state):
                    runtime.setdefault("pending_input", []).append(
                        {**effect, "entry_id": app.state["entry_id"]}
                    )
        imgui.end()
        if app.show_info:
            if runtime["first"]:
                x, y, _, _ = windows.monitors[runtime["options"]["info_window_screen_number"]]
                imgui.set_next_window_pos((x + 100, y + 100))
                imgui.set_next_window_size((600, 800))
            _, opened = imgui.begin("Info", True)
            runtime["info_viewport"] = imgui.get_window_viewport().id_
            if not opened:
                app.dispatch({"type": "quit"}, now)

            def render(commands):
                if not commands:
                    return
                position = imgui.get_cursor_screen_pos()
                available = imgui.get_content_region_avail().x
                _, _, width, height = commands[0]["box"]
                box = fit(
                    width / height, (position.x, position.y, available, available * height / width)
                )
                scaled = []
                for command in commands:
                    item = dict(command)
                    for field in ("box", "clip", "container"):
                        if field in item:
                            x, y, w, h = item[field]
                            item[field] = (
                                box[0] + x / width * box[2],
                                box[1] + y / height * box[3],
                                w / width * box[2],
                                h / height * box[3],
                            )
                    if "width" in item:
                        item["width"] *= box[2] / width
                    scaled.append(item)
                draw(scaled, imgui.get_window_draw_list())
                imgui.dummy((box[2], box[3]))

            render_info(state, {"composition": app.preview_composition, "render": render})
            imgui.end()
        if app.closed:
            app._drop_frames(app.frames)
            app._drop_frames(app.preview_frames)
            params.app_shall_exit = True
        runtime["first"] = False

    def after_swap():
        app, windows = runtime["app"], runtime["windows"]
        viewport_id = runtime.get("info_viewport")
        if viewport_id:
            viewport = imgui.find_viewport_by_id(viewport_id)
            windows.attach(
                "info",
                _pointer(viewport.platform_handle),
                runtime["options"]["info_window_screen_number"],
            )
        if not runtime.get("configured") and (not app.show_info or "info" in windows.handles):
            if options.get("full_screen"):
                windows.toggle_fullscreen(runtime["options"])
            if options.get("hide_mouse"):
                windows.toggle_mouse()
            runtime["configured"] = True
        app.after_render()

    params.callbacks.setup_imgui_config = setup
    params.callbacks.post_init = post_init
    params.callbacks.show_gui = gui
    params.callbacks.after_swap = after_swap
    # Notatki w Info używają imgui_md; samo hello_imgui.run go nie inicjalizuje.
    immapp.run(params, immapp.AddOnsParams(with_markdown=True))
    return 0
