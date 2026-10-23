"""Target spawn; import backendu następuje dopiero po oczyszczeniu argv."""

import importlib.util
import sys
import traceback
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path


def run_worker(spec, shm_name, frame_lock, bootstrap_sender) -> None:
    sys.argv = [sys.argv[0]]
    if spec.engine == "ce-cairo":
        from manimcue.live_scene_ce import run_ce_worker

        return run_ce_worker(spec, shm_name, frame_lock, bootstrap_sender)
    shm = None
    scene = None
    try:
        from manimlib.constants import FRAME_HEIGHT, FRAME_WIDTH

        from manimcue.frame_buffer import FrameBuffer
        from manimcue.live_scene import LiveScene

        path = Path(spec.scene_file)
        sys.path.insert(0, str(path.parent))
        module_spec = importlib.util.spec_from_file_location("_manimcue_live_scene", path)
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_spec.name] = module
        module_spec.loader.exec_module(module)
        scene_type = getattr(module, spec.scene_name)
        if not issubclass(scene_type, LiveScene):
            raise TypeError("Klasa sceny musi dziedziczyć po LiveScene")
        shm = SharedMemory(name=shm_name)
        scale = min(spec.width / FRAME_WIDTH, spec.height / FRAME_HEIGHT)
        render_size = (round(FRAME_WIDTH * scale), round(FRAME_HEIGHT * scale))
        scene = scene_type(
            window=None,
            skip_animations=False,
            presenter_mode=False,
            camera_config={
                "resolution": render_size,
                "frame_config": {"frame_shape": (FRAME_WIDTH, FRAME_HEIGHT)},
                "fps": spec.fps,
                "background_opacity": spec.background_opacity,
            },
            file_writer_config={
                "write_to_movie": False,
                "save_last_frame": False,
                "subdivide_output": False,
            },
        )
        scene.live_buffer = FrameBuffer(shm, frame_lock, spec.width, spec.height)
        scene.live_bootstrap = bootstrap_sender
        scene.run()
    except Exception as exc:  # noqa: BLE001 — nadzorca raportuje wyjątki kodu sceny
        cue = getattr(scene, "live_cue", "build_objects")
        message = f"ERROR {spec.scene_name} / {cue}: {type(exc).__name__}: {exc}"
        bootstrap_sender.send(message)
        traceback.print_exc()
    finally:
        if scene is not None:
            scene.close_sockets()
            scene.file_writer.finish()
            scene.camera.ctx.release()
        if shm is not None:
            shm.close()
        bootstrap_sender.close()
