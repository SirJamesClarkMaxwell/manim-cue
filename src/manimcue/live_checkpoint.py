"""Checkpoint grafu panelu; zasoby renderera pozostają własnością żywej sceny."""

import copy
import sys
import time
from enum import Enum
from types import FunctionType, MethodType, SimpleNamespace

import numpy as np


class UnsupportedSnapshot(ValueError):
    """Pole spoza jawnego korpusu nie może wejść do rachunku pamięci."""


class RestoreFailed(RuntimeError):
    """Po rozpoczęciu mutacji proces nie może wrócić do obsługi cue."""


def panel_nodes(scene):
    """Domknięcie grafu autora pomija przejściowe grupy renderera GL."""
    nodes, seen = [], set()
    render_groups = {id(group) for group in getattr(scene, "render_groups", [])}

    def visit(value):
        if id(value) in seen or id(value) in render_groups:
            return
        seen.add(id(value))
        if hasattr(value, "get_family") and hasattr(value, "submobjects"):
            nodes.append(value)
            for key, item in value.__dict__.items():
                if key not in ("shader_wrapper", "shader_wrappers"):
                    visit(item)
        elif type(value) is dict:
            for item in value.values():
                visit(item)
        elif type(value) in (list, tuple, set, frozenset):
            for item in value:
                visit(item)

    visit(list(scene.mobjects) + list(getattr(scene, "foreground_mobjects", [])))
    return nodes


def graph_bytes(value, seen=None, nodes=()):
    """Konserwatywny rachunek danych, bez uruchamiania kopiowania klas autora."""
    if seen is None:
        seen = set()
    if id(value) in seen or id(value) in nodes:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value) + 64
    if type(value) is np.ndarray:
        if value.dtype.hasobject:
            raise UnsupportedSnapshot("object array")
        return size + value.nbytes
    if type(value) in (dict, list, tuple, set, frozenset):
        values = list(value.items()) if type(value) is dict else value
        return size + sum(graph_bytes(item, seen, nodes) for item in values)
    if type(value) in (str, bytes, int, float, bool, complex, type(None), FunctionType, MethodType):
        return size
    if isinstance(value, (Enum, np.generic)):
        return size
    if type(value).__module__ == "scipy.spatial.transform._rotation":
        return size + 1024
    # Kolory CE mają własne kopiowanie wyłącznie tablicy RGBA.
    if type(value).__module__.startswith("manim.utils.color"):
        return size + 1024
    if type(value).__module__.startswith("manim.mobject."):
        return size + graph_bytes(value.__dict__, seen, nodes)
    raise UnsupportedSnapshot(type(value).__qualname__)


class PanelSnapshot:
    """Zachowuje oryginały, krawędzie, updatery i czas obu backendów."""

    def __init__(self, scene):
        self.roots = list(scene.mobjects)
        self.foreground = list(getattr(scene, "foreground_mobjects", []))
        self.originals = panel_nodes(scene)
        self.memo = {id(node): node for node in self.originals}
        self.memo.update(
            {id(updater): updater for node in self.originals for updater in node.updaters}
        )
        self.scene_time = scene.time
        self.num_plays = getattr(scene, "num_plays", 0)
        self.states = copy.deepcopy(self.state_data(scene), self.memo.copy())

    @staticmethod
    def state_data(scene):
        nodes = panel_nodes(scene)
        render_groups = {id(group) for group in getattr(scene, "render_groups", [])}
        return [
            {
                k: [parent for parent in v if id(parent) not in render_groups]
                if k == "parents"
                else v
                for k, v in node.__dict__.items()
                if k not in ("shader_wrapper", "shader_wrappers")
            }
            for node in nodes
        ]

    @classmethod
    def estimate(cls, scene):
        originals = panel_nodes(scene)
        if any(
            not type(node).__module__.startswith(
                ("manim.mobject.", "manimlib.mobject.", "manimlib.camera.camera_frame")
            )
            for node in originals
        ):
            raise UnsupportedSnapshot("custom mobject")
        nodes = {id(node) for node in originals}
        # Listy korzeni, memo, otoczka i do 50 referencji historii też zajmują pamięć.
        return graph_bytes(cls.state_data(scene), nodes=nodes) + 1024 + 512 * len(nodes)

    def restore(self, scene):
        states = copy.deepcopy(self.states, self.memo.copy())
        for node, state in zip(self.originals, states):
            node.__dict__.clear()
            node.__dict__.update(state)
            if hasattr(scene, "frame"):
                node.shader_wrapper = None
                node._data_has_changed = True
        scene.mobjects = self.roots.copy()
        if hasattr(scene, "foreground_mobjects"):
            scene.foreground_mobjects = self.foreground.copy()
        if hasattr(scene, "frame"):
            scene.time = self.scene_time
            scene.num_plays = self.num_plays
            scene.assemble_render_groups()
        else:
            scene.renderer.time = self.scene_time

    def animate(self, scene):
        began = time.perf_counter()
        if hasattr(scene, "frame"):
            from manimlib import Transform

            animations = []
            for node, state in zip(self.originals, self.states):
                if (
                    node in scene.get_mobject_family_members()
                    and not node.submobjects
                    and not state["submobjects"]
                    and node.data.dtype == state["data"].dtype
                    and node.data.shape == state["data"].shape
                ):
                    target = copy.copy(node)
                    target.__dict__ = copy.deepcopy(state, self.memo.copy())
                    target.shader_wrapper = None
                    target.family = [target]
                    target.parents = []
                    animations.append(Transform(node, target))
            if animations:
                prepared = time.perf_counter()
                scene.play(*animations, run_time=0.6)
            else:
                prepared = time.perf_counter()
        else:
            from manimcue.live_scene_ce import SnapshotAnimation

            targets = []
            for node, state in zip(self.originals, self.states):
                target = copy.copy(node)
                target.__dict__ = copy.deepcopy(state, self.memo.copy())
                targets.append(target)
            self.copies = targets
            prepared = time.perf_counter()
            try:
                scene.play(SnapshotAnimation(self))
            finally:
                del self.copies
        restoring = time.perf_counter()
        self.restore(scene)
        return {
            "prepare_ms": 1000 * (prepared - began),
            "restore_ms": 1000 * (time.perf_counter() - restoring),
        }


class CheckpointStore:
    """Ograniczona historia wejść z rezerwą przed utworzeniem kopii."""

    max_count = 50
    max_bytes = 256 * 1024 * 1024

    def __init__(self, scene):
        self.scene = scene
        self.entries = {}
        self.protected = None
        self.restoring = None

    def accounted_bytes(self):
        snapshots = list(self.scene.undo_stack) + list(getattr(self.scene, "redo_stack", []))
        for state, _, history in self.entries.values():
            snapshots.extend((state, *history))
        unique = {id(state): state for state in snapshots}
        originals = list(
            dict.fromkeys(node for state in unique.values() for node in state.originals)
        )
        retained = (
            PanelSnapshot.estimate(
                SimpleNamespace(
                    mobjects=originals,
                    foreground_mobjects=[],
                    render_groups=getattr(self.scene, "render_groups", []),
                )
            )
            if originals
            else 0
        )
        return sum(state.byte_size for state in unique.values()) + retained

    def reserve(self, target_size=0):
        size = max(PanelSnapshot.estimate(self.scene), target_size)
        while self.accounted_bytes() + 4 * size > self.max_bytes:
            victim = next(
                (key for key in self.entries if key not in (self.protected, self.restoring)), None
            )
            if victim is None:
                raise MemoryError("limit")
            del self.entries[victim]
            self.scene.live_status(f"CHECKPOINT_EVICTED {victim} limit")
        return size

    def capture(self):
        began = time.perf_counter()
        size = self.reserve()
        snapshot = PanelSnapshot(self.scene)
        snapshot.byte_size = size
        snapshot.snapshot_ms = 1000 * (time.perf_counter() - began)
        return snapshot

    def checkpoint(self, key):
        if key in self.entries:
            raise ValueError("invalid")
        snapshot = self.capture()
        while len(self.entries) >= self.max_count:
            victim = next((key for key in self.entries if key != self.protected), None)
            if victim is None:
                raise MemoryError("limit")
            del self.entries[victim]
            self.scene.live_status(f"CHECKPOINT_EVICTED {victim} limit")
        self.entries[key] = (snapshot, self.scene.cursor, tuple(self.scene.undo_stack))
        self.protected = key
        return {"snapshot_ms": snapshot.snapshot_ms}

    def restore(self, key):
        if key not in self.entries:
            raise KeyError("missing")
        snapshot, cursor, history = self.entries[key]
        self.restoring = key
        try:
            original_size = PanelSnapshot.estimate(
                SimpleNamespace(
                    mobjects=snapshot.originals,
                    foreground_mobjects=[],
                    render_groups=getattr(self.scene, "render_groups", []),
                )
            )
            self.reserve(max(snapshot.byte_size, original_size))
            self.scene.abort_cue = False
            try:
                metrics = snapshot.animate(self.scene)
                self.scene.cursor = cursor
                self.scene.undo_stack = list(history)
                if hasattr(self.scene, "redo_stack"):
                    self.scene.redo_stack = []
                return metrics
            except Exception as exc:
                raise RestoreFailed("restore_failed") from exc
        finally:
            self.restoring = None
