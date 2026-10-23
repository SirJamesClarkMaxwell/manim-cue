"""Bramka natywnych viewportów Windows; wynik nie zastępuje próby człowieka."""

import argparse
import ctypes as ct
import json
import os
import time
from pathlib import Path


def pointer(value):
    """Odczytaj adres z kapsuły nanobind, bez zgadywania kolejności okien."""
    if isinstance(value, int):
        return value
    if value is None:
        return 0
    get_name = ct.pythonapi.PyCapsule_GetName
    get_name.argtypes = [ct.py_object]
    get_name.restype = ct.c_char_p
    get_pointer = ct.pythonapi.PyCapsule_GetPointer
    get_pointer.argtypes = [ct.py_object, ct.c_char_p]
    get_pointer.restype = ct.c_void_p
    return get_pointer(value, get_name(value))


class Glfw:
    """Wąski dostęp do tej samej DLL, której używa hello_imgui."""

    def __init__(self):
        from imgui_bundle import hello_imgui  # noqa: F401

        self.dll = ct.CDLL(os.environ["PYGLFW_LIBRARY"])
        signatures = {
            "glfwInit": (ct.c_int, []),
            "glfwTerminate": (None, []),
            "glfwGetError": (ct.c_int, [ct.POINTER(ct.c_char_p)]),
            "glfwGetMonitors": (ct.POINTER(ct.c_void_p), [ct.POINTER(ct.c_int)]),
            "glfwGetMonitorName": (ct.c_char_p, [ct.c_void_p]),
            "glfwGetMonitorPos": (None, [ct.c_void_p, ct.c_void_p, ct.c_void_p]),
            "glfwGetVideoMode": (ct.POINTER(ct.c_int), [ct.c_void_p]),
            "glfwGetWindowPos": (None, [ct.c_void_p, ct.c_void_p, ct.c_void_p]),
            "glfwGetWindowSize": (None, [ct.c_void_p, ct.c_void_p, ct.c_void_p]),
            "glfwGetFramebufferSize": (None, [ct.c_void_p, ct.c_void_p, ct.c_void_p]),
            "glfwSetWindowPos": (None, [ct.c_void_p, ct.c_int, ct.c_int]),
            "glfwSetWindowSize": (None, [ct.c_void_p, ct.c_int, ct.c_int]),
            "glfwSetWindowAttrib": (None, [ct.c_void_p, ct.c_int, ct.c_int]),
            "glfwGetWindowAttrib": (ct.c_int, [ct.c_void_p, ct.c_int]),
            "glfwGetWindowMonitor": (ct.c_void_p, [ct.c_void_p]),
            "glfwGetWin32Window": (ct.c_void_p, [ct.c_void_p]),
            "glfwSetInputMode": (None, [ct.c_void_p, ct.c_int, ct.c_int]),
            "glfwGetInputMode": (ct.c_int, [ct.c_void_p, ct.c_int]),
            "glfwMakeContextCurrent": (None, [ct.c_void_p]),
            "glfwGetCurrentContext": (ct.c_void_p, []),
            "glfwSwapBuffers": (None, [ct.c_void_p]),
            "glfwSwapInterval": (None, [ct.c_int]),
        }
        for name, (result, args) in signatures.items():
            function = getattr(self.dll, name)
            function.restype, function.argtypes = result, args

    def pair(self, name, handle):
        x, y = ct.c_int(), ct.c_int()
        getattr(self.dll, name)(handle, ct.byref(x), ct.byref(y))
        return [x.value, y.value]

    def window(self, handle):
        return {
            "handle": handle,
            "native_handle": self.dll.glfwGetWin32Window(handle),
            "position": self.pair("glfwGetWindowPos", handle),
            "size": self.pair("glfwGetWindowSize", handle),
            "framebuffer": self.pair("glfwGetFramebufferSize", handle),
            "decorated": bool(self.dll.glfwGetWindowAttrib(handle, 0x20005)),
            "exclusive_monitor": self.dll.glfwGetWindowMonitor(handle),
            "cursor": self.dll.glfwGetInputMode(handle, 0x33001),
        }


def run_gate(main_monitor: int, info_monitor: int, output: Path) -> int:
    """Sprawdź dwa viewporty, fullscreen i kursor; zapisz także dokładny błąd."""
    result = {"status": "error", "monitors": [], "windows": {}, "swaps": {}}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    glfw = None
    started = time.monotonic()
    try:
        from imgui_bundle import hello_imgui, imgui

        glfw = Glfw()
        if not glfw.dll.glfwInit():
            description = ct.c_char_p()
            code = glfw.dll.glfwGetError(ct.byref(description))
            raise RuntimeError(f"glfwInit: {code}: {description.value!r}")
        count = ct.c_int()
        monitors = glfw.dll.glfwGetMonitors(ct.byref(count))
        for index in range(count.value):
            monitor = monitors[index]
            mode = glfw.dll.glfwGetVideoMode(monitor)
            result["monitors"].append(
                {
                    "name": glfw.dll.glfwGetMonitorName(monitor).decode("utf-8"),
                    "position": glfw.pair("glfwGetMonitorPos", monitor),
                    "size": [mode[0], mode[1]],
                    "hz": mode[5],
                }
            )
        for index in (main_monitor, info_monitor):
            if not 0 <= index < count.value:
                raise ValueError(f"monitor {index}; dostępne: {count.value}")

        params = hello_imgui.RunnerParams()
        params.platform_backend_type = hello_imgui.PlatformBackendType.glfw
        params.renderer_backend_type = hello_imgui.RendererBackendType.open_gl3
        params.ini_disable = True
        params.fps_idling.enable_idling = False
        params.fps_idling.vsync_to_monitor = True
        params.app_window_params.window_title = "manim-cue F10 main"
        params.app_window_params.window_geometry.size = (640, 360)
        params.imgui_window_params.enable_viewports = True
        params.imgui_window_params.default_imgui_window_type = (
            hello_imgui.DefaultImGuiWindowType.no_default_window
        )
        state = {"tick": 0, "viewports": {}, "swap_times": []}

        def setup():
            imgui.get_io().config_viewports_no_auto_merge = True
            imgui.get_io().config_viewports_no_decoration = False

        def gui():
            monitor = result["monitors"][info_monitor]
            if state["tick"] == 0:
                imgui.set_next_window_pos(
                    (monitor["position"][0] + 80, monitor["position"][1] + 80)
                )
                imgui.set_next_window_size((480, 300))
            imgui.begin("manim-cue F10 Info")
            imgui.text("Bramka F10: osobny natywny viewport")
            state["viewports"]["info"] = imgui.get_window_viewport().id_
            state["viewports"]["main"] = imgui.get_main_viewport().id_
            imgui.end()

        def after_swap():
            tick = state["tick"]
            state["swap_times"].append(time.perf_counter())
            handles = {
                name: pointer(imgui.find_viewport_by_id(viewport).platform_handle)
                for name, viewport in state["viewports"].items()
            }
            if 5 < tick <= 8:
                glfw.dll.glfwSetInputMode(handles["main"], 0x33001, 0x34002)
            if tick == 3:
                if not all(handles.values()) or handles["main"] == handles["info"]:
                    raise RuntimeError(f"Info nie ma osobnego viewportu: {handles}")
                result["viewport_ids"] = dict(state["viewports"])
                result["backend"] = hello_imgui.get_backend_description()
                for name, index in (("main", main_monitor), ("info", info_monitor)):
                    position = result["monitors"][index]["position"]
                    glfw.dll.glfwSetWindowPos(handles[name], position[0] + 80, position[1] + 80)
            if tick == 5:
                result["windows"]["before"] = {
                    name: glfw.window(handle) for name, handle in handles.items()
                }
                for name, index in (("main", main_monitor), ("info", info_monitor)):
                    monitor = result["monitors"][index]
                    glfw.dll.glfwSetWindowAttrib(handles[name], 0x20005, 0)
                    glfw.dll.glfwSetWindowPos(handles[name], *monitor["position"])
                    glfw.dll.glfwSetWindowSize(handles[name], *monitor["size"])
                glfw.dll.glfwSetInputMode(handles["main"], 0x33001, 0x34002)
            if tick == 8:
                result["windows"]["fullscreen"] = {
                    name: glfw.window(handle) for name, handle in handles.items()
                }
                for name, handle in handles.items():
                    before = result["windows"]["before"][name]
                    glfw.dll.glfwSetWindowAttrib(handle, 0x20005, int(before["decorated"]))
                    glfw.dll.glfwSetWindowPos(handle, *before["position"])
                    glfw.dll.glfwSetWindowSize(handle, *before["size"])
                glfw.dll.glfwSetInputMode(handles["main"], 0x33001, 0x34001)
            if tick == 11:
                result["windows"]["after"] = {
                    name: glfw.window(handle) for name, handle in handles.items()
                }
                # Osobno mierzymy prawdziwe wywołania swap, a nie liczbę iteracji UI.
                previous = glfw.dll.glfwGetCurrentContext()
                for name, handle in handles.items():
                    glfw.dll.glfwMakeContextCurrent(handle)
                    glfw.dll.glfwSwapInterval(1)
                    samples = []
                    for _ in range(3):
                        begin = time.perf_counter()
                        glfw.dll.glfwSwapBuffers(handle)
                        samples.append((time.perf_counter() - begin) * 1000)
                    result["swaps"][name] = {"duration_ms": samples, "interval_requested": 1}
                glfw.dll.glfwMakeContextCurrent(previous)
                result["status"] = "ok"
                params.app_shall_exit = True
            state["tick"] += 1

        params.callbacks.setup_imgui_config = setup
        params.callbacks.show_gui = gui
        params.callbacks.after_swap = after_swap
        hello_imgui.run(params)
    except Exception as error:  # noqa: BLE001 — bramka zapisuje także błędy wiązania natywnego.
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        if glfw is not None:
            glfw.dll.glfwTerminate()
        result["elapsed_seconds"] = time.monotonic() - started
        result["human_checks"] = ["DPI", "fokus/Info", "wygląd", "dwa monitory", "vsync"]
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-monitor", type=int, default=0)
    parser.add_argument("--info-monitor", type=int, default=0)
    parser.add_argument("--output", type=Path, default=Path(".tmp/MEASUREMENT-10a-windows.json"))
    args = parser.parse_args()
    raise SystemExit(run_gate(args.main_monitor, args.info_monitor, args.output))
