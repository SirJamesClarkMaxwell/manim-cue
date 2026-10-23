"""Adapter live CE 0.22 Cairo 2D, bez okna i bez zmian w Manimie."""

import copy
import importlib.util
import sys
import time
import traceback
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path
from typing import ClassVar

import numpy as np
from manim import Animation, Mobject, Scene, tempconfig
from manim.renderer.cairo_renderer import CairoRenderer

from manimcue.frame_buffer import FrameBuffer
from manimcue.live_transport import LiveTransport


class LiveShutdown(BaseException):
    """Kooperacyjne zamknięcie przerywające także resztę callable."""


class LiveCairoRenderer(CairoRenderer):
    """Cała ścieżka play należy do live; writer i cache nie uczestniczą."""

    def play(self, scene, *args, **kwargs):
        self.skip_animations = False
        self.static_image = None
        scene.compile_animation_data(*args, **kwargs)
        scene.begin_animations()
        began = self.time
        elapsed = 0.0
        frozen = scene.is_current_animation_frozen_frame()
        if frozen and not scene.abort_cue:
            scene.live_publish(only_if_changed=True)
        for elapsed, _ in scene.live_times(scene.duration):
            self.time = began + elapsed
            if not frozen:
                updating = time.perf_counter()
                scene.update_to_time(elapsed)
                metric = scene.live_metrics.setdefault("update", [0.0, 0])
                metric[0] += time.perf_counter() - updating
                metric[1] += 1
                scene.live_publish()
            if scene.stop_condition is not None and scene.stop_condition():
                break
        else:
            # D10: animacje dochodzą do końca bez symulacji pominiętych updaterów.
            elapsed = scene.duration
        self.time = began + elapsed
        for animation in scene.animations:
            animation.finish()
            animation.clean_up_from_scene(scene)
        scene.update_mobjects(0)
        self.static_image = None
        self.num_plays += 1


class SceneSnapshot:
    """Jeden graf kopii, wspólne memo i jawne mapowanie do oryginałów."""

    def __init__(self, scene):
        self.scene_time = scene.time
        self.roots = list(scene.mobjects)
        self.foreground = list(scene.foreground_mobjects)
        self.originals = list(
            dict.fromkeys(
                node for root in self.roots + self.foreground for node in root.get_family()
            )
        )
        updater_memo = {
            id(updater): updater for node in self.originals for updater in node.updaters
        }
        memo = updater_memo.copy()
        self.copies = copy.deepcopy(self.originals, memo)
        self.memo = {id(clone): original for original, clone in zip(self.originals, self.copies)}
        self.memo.update(updater_memo)

    def restore(self, scene):
        memo = self.memo.copy()
        states = copy.deepcopy([clone.__dict__ for clone in self.copies], memo)
        for original, state in zip(self.originals, states):
            original.__dict__.clear()
            original.__dict__.update(state)
        scene.mobjects = self.roots.copy()
        scene.foreground_mobjects = self.foreground.copy()
        scene.renderer.time = self.scene_time


class SnapshotAnimation(Animation):
    """Każdy węzeł interpolowany raz, bez podwójnego ruchu wspólnego dziecka."""

    def __init__(self, snapshot):
        super().__init__(Mobject(), run_time=0.6, remover=True)
        updater_memo = {
            id(updater): updater for node in snapshot.originals for updater in node.updaters
        }
        starts = copy.deepcopy(snapshot.originals, updater_memo)
        self.pairs = [
            (original, start, target)
            for original, start, target in zip(snapshot.originals, starts, snapshot.copies)
            if original.points.shape == target.points.shape
        ]

    def interpolate_mobject(self, alpha):
        for original, start, target in self.pairs:
            original.interpolate(start, target, alpha)


class LiveSceneCE(LiveTransport, Scene):
    """Autor definiuje build_objects, PRESETS, SEQUENCE i LOOPS; construct należy do bazy."""

    PRESETS: ClassVar[dict] = {}
    SEQUENCE: ClassVar[list] = []
    LOOPS: ClassVar[set] = set()
    shutdown_exception = LiveShutdown

    def __init__(self, **kwargs):
        super().__init__(renderer=LiveCairoRenderer(), **kwargs)
        self.cursor = 0
        self.abort_cue = False
        self.undo_stack = []
        self.snapshot_metrics = []

    def construct(self):
        if not hasattr(self, "live_buffer"):
            raise RuntimeError("LiveSceneCE wymaga workera warstwy live engine='ce-cairo'")
        self.live_construct()

    def __deepcopy__(self, memo):
        """Targety CE zachowują odniesienie do żywej sceny; jej IPC nie jest kopiowalne."""
        memo[id(self)] = self
        return self

    def build_objects(self):
        """Miejsce tworzenia obiektów autora przed pierwszą klatką READY."""

    def next_section(self, name="unnamed", section_type=None, skip_animations=False):
        if skip_animations:
            raise ValueError("Live CE nie obsługuje next_section(skip_animations=True)")

    def save_state(self):
        began = time.perf_counter()
        self.undo_stack.append(SceneSnapshot(self))
        self.undo_stack[:] = self.undo_stack[-50:]
        self.snapshot_metrics.append({"snapshot_ms": 1000 * (time.perf_counter() - began)})
        self.snapshot_metrics[:] = self.snapshot_metrics[-50:]

    def rewind(self):
        if not self.undo_stack:
            return
        state = self.undo_stack.pop()
        began = time.perf_counter()
        animation = SnapshotAnimation(state)
        prepared = time.perf_counter()
        self.abort_cue = False
        self.play(animation)
        restoring = time.perf_counter()
        state.restore(self)
        self.snapshot_metrics[-1].update(
            prepare_ms=1000 * (prepared - began),
            restore_ms=1000 * (time.perf_counter() - restoring),
        )
        self.live_bootstrap.send({"snapshot_metrics": self.snapshot_metrics})

    def live_view(self, command):
        """D28 CE odroczone; komenda nie narusza cue ani bariery."""

    def live_publish(self, boundary=False, only_if_changed=False):
        began = time.monotonic()
        self.renderer.update_frame(self)
        rendered = time.monotonic()
        camera = self.camera
        pixels = camera.pixel_array
        target = self.live_buffer
        height, width = pixels.shape[:2]
        # Puste tło CE jest straight RGBA; D35 nie obiecuje normalizacji dowolnej treści.
        if (width, height) == (target.width, target.height):
            canvas = pixels
        else:
            background = camera.background[0, 0].tobytes()
            if getattr(self, "_live_background", None) != background:
                self._live_canvas = np.empty((target.height, target.width, 4), dtype=np.uint8)
                self._live_canvas[:] = camera.background[0, 0]
                self._live_background = background
            canvas = self._live_canvas
            x, y = (target.width - width) // 2, (target.height - height) // 2
            canvas[y : y + height, x : x + width] = pixels
        # Kopia ciągłych wierszy; tobytes na widoku o ujemnym stride iteruje po kanałach.
        payload = memoryview(canvas[::-1].copy(order="C")).cast("B")
        if only_if_changed and payload == getattr(self, "_live_last_pixels", None):
            return
        read = time.monotonic()
        self.live_frame_id += 1
        target.publish(payload, self.live_frame_id, boundary)
        self._live_last_pixels = payload
        if boundary:
            self.live_boundary_id = self.live_frame_id
        published = time.monotonic()
        for name, elapsed in (
            ("render", rendered - began),
            ("readback", read - rendered),
            ("publish", published - read),
        ):
            self.live_metrics[name][0] += elapsed
            self.live_metrics[name][1] += 1


def run_ce_worker(spec, shm_name, frame_lock, bootstrap_sender):
    """Worker posiada lifecycle i sprząta raz również po błędzie setup/build/cue."""
    shm = None
    scene = None
    error = None
    try:
        path = Path(spec.scene_file)
        sys.path.insert(0, str(path.parent))
        module_spec = importlib.util.spec_from_file_location("_manimcue_live_scene", path)
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_spec.name] = module
        module_spec.loader.exec_module(module)
        scene_type = getattr(module, spec.scene_name)
        if not issubclass(scene_type, LiveSceneCE):
            raise TypeError("Klasa sceny musi dziedziczyć po LiveSceneCE")
        if scene_type.construct is not LiveSceneCE.construct:
            raise TypeError("LiveSceneCE.construct należy do bazy; użyj build_objects")
        scale = min(spec.width / (128 / 9), spec.height / 8)
        settings = {
            "renderer": "cairo",
            "format": "none",
            "disable_caching": True,
            "preview": False,
            "live_preview": False,
            "enable_gui": False,
            "save_last_frame": False,
            "frame_rate": spec.fps,
            "pixel_width": max(1, round(128 / 9 * scale)),
            "pixel_height": max(1, round(8 * scale)),
            "frame_width": 128 / 9,
            "frame_height": 8,
            "background_opacity": float(spec.background_opacity),
            "from_animation_number": 0,
            "upto_animation_number": float("inf"),
        }
        with tempconfig(settings):
            shm = SharedMemory(name=shm_name)
            scene = scene_type()
            scene.live_buffer = FrameBuffer(shm, frame_lock, spec.width, spec.height)
            scene.live_bootstrap = bootstrap_sender
            try:
                scene.live_cue = "setup"
                scene.setup()
                scene.live_cue = "build_objects"
                scene.construct()
            except LiveShutdown:
                pass
            except BaseException as exc:
                error = exc
                raise
            finally:
                cleanup_error = None
                for finalize in (scene.tear_down, scene.renderer.file_writer.finish):
                    try:
                        finalize()
                    except Exception as exc:  # noqa: BLE001 — oba finalizery muszą się wykonać
                        if cleanup_error is None:
                            cleanup_error = exc
                if error is None and cleanup_error is not None:
                    raise cleanup_error
    except Exception as exc:  # noqa: BLE001 — granica procesu raportuje błędy autora
        cue = getattr(scene, "live_cue", "build_objects")
        bootstrap_sender.send(f"ERROR {spec.scene_name} / {cue}: {type(exc).__name__}: {exc}")
        traceback.print_exc()
    finally:
        if scene is not None and getattr(scene, "listener", None) is not None:
            scene.close_sockets()
        if shm is not None:
            shm.close()
        bootstrap_sender.close()
