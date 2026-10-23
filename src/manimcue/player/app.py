"""Jednowątkowa koordynacja UI, bariery i mediów; bez zależności od okna GLFW."""

import json
import time

from manimcue.live_pool import LivePool, ProcessBudget, deck_resources

from .clock import media_time, new_clock, set_playing
from .controller import reduce
from .geometry import rect_at
from .info import preview_target, timer_elapsed, update_timer
from .live import LiveController
from .prefetch import Prefetch, live_spec
from .sources_av import Source, Thumbnails, close_pool, configure_budget, process_counts
from .stage import compose
from .state import initial_state, snapshot
from .textures import upload


class App:
    """Jedna iteracja najpierw obsługuje live/ACK, potem media round-robin."""

    def __init__(self, manifest, options, source_factory=Source, uploader=upload, live=None):
        self.manifest, self.options = manifest, options
        self.source_factory, self.uploader = source_factory, uploader
        self.live_pool = None
        if live is None and source_factory is Source:
            self.live_pool = LivePool(ProcessBudget())
            configure_budget(self.live_pool.budget)
        self.live = live if live is not None else LiveController(pool=self.live_pool)
        self.prefetch = (
            Prefetch(self.live_pool)
            if self.live_pool is not None and options.get("prefetch", True)
            else None
        )
        self.adopted = {}
        self.started_at = time.monotonic()
        self.state = initial_state(manifest, self.started_at)
        deck, slide = (
            options.get("start_at_scene_number", 0),
            options.get("start_at_slide_number", 0),
        )
        self.state["index"] = [deck, slide]
        self.state["resolution"] = list(
            manifest["presentations"][deck].get("resolution", manifest["resolution"])
        )
        self.state.update(
            {
                key: options[key]
                for key in (
                    "skip_all",
                    "exit_after_last_slide",
                    "next_terminates_loop",
                    "playback_rate",
                )
                if key in options
            }
        )
        self.state["requested_playing"] = not options.get("start_paused", False)
        self.sources, self.preview_sources = {}, {}
        self.frames, self.preview_frames = {}, {}
        self.retired_sources, self.retired_leases = [], []
        self.thumbnails = Thumbnails(self.uploader, lambda lease: self.retired_leases.append(lease))
        self.thumbnail_indices = []
        self.thumbnail_requests = []
        self.show_info = options.get("show_info", True)
        self.preview = None
        self.preview_started = set()
        self.preview_anchors = {}
        self.errors = []
        self.cursor = 0
        self.composition = []
        self.preview_composition = []
        # Wejście kompozycji, którą widać; w przygotowaniu wstrzymany obraz poprzedniego.
        self.stage, self.stage_frames, self.stage_time = None, {}, 0.0
        self.held = None
        self._prepare("initial", self.started_at)

    def _prefetch_target(self):
        deck, index = self.state["index"]
        slides = self.manifest["presentations"][deck]["slides"]
        if self.state["reverse"] or index + 1 >= len(slides):
            return None, None
        slide = slides[index + 1]
        resolution = self.state["resolution"]
        token = (
            id(self.manifest),
            deck,
            self.state["entry_id"],
            index + 1,
            json.dumps(
                [
                    slide,
                    resolution,
                    self.options.get("playback_rate", 1),
                    self.options.get("skip_all", False),
                ],
                sort_keys=True,
            ),
        )
        adjacent = []
        for i, layer in enumerate(slide.get("layers", [])):
            if layer["kind"] == "live" and layer.get("session_id"):
                for old_index, old in enumerate(self._slide().get("layers", [])):
                    session = self.live.sessions.get(old_index)
                    if (
                        old["kind"] == "live"
                        and session is not None
                        and session.state == "ready"
                        and not session.stopping
                        and layer["session_id"] == old.get("session_id")
                        and live_spec(layer, resolution) == live_spec(old, resolution)
                    ):
                        adjacent.append(str(i))
        rate = self.options.get("playback_rate", 1)
        skip = self.options.get("skip_all", False)
        target = {
            **slide,
            "resolution": resolution,
            "adjacent": adjacent,
            "rate": slide.get("rate", 1) * rate,
            "loop": bool(slide.get("loop")) and not skip,
            "layers": [
                {
                    **m,
                    "rate": m.get("rate", 1) * rate,
                    "loop": bool(m.get("loop") or slide.get("loop")) and not skip,
                }
                for m in slide.get("layers", [])
            ],
        }
        return token, target

    def _slide(self):
        deck, slide = self.state["index"]
        return self.manifest["presentations"][deck]["slides"][slide]

    def request_thumbnail(self, index: tuple, size: tuple) -> None:
        """Zamów wyłącznie statyczny normalny slajd bieżącego decku."""
        deck, slide = index
        presentation = self.manifest["presentations"][deck]
        self.thumbnail_requests.append(
            (
                index,
                {
                    "slide": presentation["slides"][slide],
                    "resolution": presentation.get("resolution", self.manifest["resolution"]),
                    "size": size,
                    "background": presentation.get("background", [0, 0, 0, 1]),
                },
            )
        )

    def _close_sources(self, sources):
        for source in sources.values():
            source.request_close()
            self.retired_sources.append(source)
        sources.clear()

    def _drop_frames(self, frames):
        for frame in frames.values():
            if frame.get("lease"):
                self.retired_leases.append(frame["lease"])
        frames.clear()

    def drop_all(self):
        """Przed zniszczeniem kontekstu GL: wszystkie tekstury, także wstrzymane."""
        if self.held:
            self._drop_frames(self.held["frames"])
            self.held = None
        self._drop_frames(self.frames)
        self._drop_frames(self.preview_frames)
        self.thumbnails.clear()

    def _held_ids(self):
        frames = self.held["frames"].values() if self.held else ()
        return {id(frame["lease"]) for frame in frames if frame.get("lease")}

    def _retire_unused(self, frames):
        kept = self._held_ids() | {
            id(frame["lease"]) for frame in self.frames.values() if frame.get("lease")
        }
        for frame in frames.values():
            if frame.get("lease") and id(frame["lease"]) not in kept:
                self.retired_leases.append(frame["lease"])

    def _new_source(self, key, media, sources, *, preview=False):
        if media["kind"] == "live":
            if not preview or not media.get("thumbnail"):
                return
            media = {"kind": "image", "file": media["thumbnail"]}
        prepared = self.adopted.pop(key, None) if not preview else None
        if prepared is not None and "spec" not in prepared:
            sources[key] = prepared["source"]
            return
        source = self.source_factory()
        source.role = "preview" if preview else "scene"
        source.prepare(self.state["entry_id"], media)
        sources[key] = source

    def _prepare(self, reason, now, preserve_live=False):
        self._close_sources(self.sources)
        old_frames, self.frames = self.frames, {}
        slide = self._slide()
        if self.live_pool is not None:
            limit, engines = deck_resources(
                self.manifest["presentations"][self.state["index"][0]]["slides"]
            )
            self.live_pool.budget.configure(limit)
            self.live_pool.configure(engines)
        media = dict(slide)
        if self.state["reverse"]:
            media["file"] = slide.get("rev_file", slide.get("file"))
            media["rate"] = slide.get("reverse_rate", 1)
        media["loop"] = slide.get("loop", False) and not self.options.get("skip_all")
        media["rate"] = media.get("rate", 1) * self.options.get("playback_rate", 1)
        self.state["clock"] = new_clock(now, media["rate"])
        self.motion_clock = new_clock(now)
        self._new_source("base", media, self.sources)
        for index, layer in enumerate(slide.get("layers", [])):
            media = {
                **layer,
                "rate": layer.get("rate", 1) * self.options.get("playback_rate", 1),
                "loop": bool(layer.get("loop") or slide.get("loop"))
                and not self.options.get("skip_all"),
            }
            if self.state["reverse"] and layer["kind"] in ("video", "gif"):
                if layer.get("end_thumbnail"):
                    media = {"kind": "image", "file": layer["end_thumbnail"]}
                else:
                    media.update(at_end=True, loop=False)
            self._new_source(str(index), media, self.sources)
        self.live.enter(
            {
                "entry_id": self.state["entry_id"],
                "index": self.state["index"],
                "resolution": self.state["resolution"],
                "slide": slide,
                "reason": reason,
                "requested_playing": self.state["requested_playing"],
                "now": now,
                "preserve_live": preserve_live,
            },
            **({"prefetched": self.adopted} if self.adopted else {}),
        )
        for index, session in self.live.sessions.items():
            lease = self.live.leases.get(session)
            old = next(
                (frame for frame in old_frames.values() if frame.get("lease") is lease), None
            )
            if lease is not None and old is None and session in self.live.frames:
                owned = self.live.frames[session]
                old = {
                    "texture": lease.texture,
                    "lease": lease,
                    "width": owned.width,
                    "height": owned.height,
                }
            if lease is not None and old is not None:
                self.frames[str(index)] = old
        if self.held is None and self.stage is not None:
            # Do gotowości wejścia scena i Info pokazują ostatni obraz poprzedniego slajdu,
            # nie szare placeholdery na czas startu dekoderów (kryterium 4: brak pustej klatki).
            self.held = {"stage": self.stage, "frames": old_frames, "time": self.stage_time}
        else:
            self._retire_unused(old_frames)
        self._prepare_preview()
        self.thumbnail_indices = []
        self.thumbnails.configure((id(self.manifest), self.state["index"][0]), [])
        self.prepare_deadline = now + 5

    def _prepare_preview(self):
        self.preview_composition = []
        self._close_sources(self.preview_sources)
        self._drop_frames(self.preview_frames)
        self.preview_started.clear()
        self.preview_anchors.clear()
        self.preview = (
            preview_target(self.manifest, self.state["index"]) if self.show_info else None
        )
        if self.preview:
            self._new_source(
                "base", {**self.preview, "loop": True}, self.preview_sources, preview=True
            )
            for index, layer in enumerate(self.preview.get("layers", [])):
                self._new_source(
                    str(index), {**layer, "loop": True}, self.preview_sources, preview=True
                )

    def set_info_visible(self, visible):
        """Ukryty podgląd nie ma dekoderów."""
        if visible != self.show_info:
            self.show_info = visible
            self._prepare_preview()
            if not visible:
                self.thumbnails.configure(self.thumbnails.revision, [])

    def dispatch(self, event, now):
        """Przyjmij akcję routera i wykonaj jawne efekty reducera."""
        if event["type"] in ("timer_pause", "timer_restart"):
            self.state["presenter_timer"] = update_timer(
                self.state["presenter_timer"], event["type"], now
            )
            return []
        if event["type"] == "notes_scale":
            self.state["notes_size"] = min(48, max(16, self.state["notes_size"] + event["delta"]))
            return []
        if event["type"] == "thumbnail_range":
            self.thumbnail_indices = event["indices"]
            return []
        old_index = self.state["index"][:]
        old_reverse = self.state["reverse"]
        target_token = self._prefetch_target()[0] if self.prefetch is not None else None
        self.state, effects = reduce(self.state, event, now)
        if self.prefetch is not None:
            entering = any(effect["type"] == "prepare" for effect in effects)
            if entering:
                normal = (
                    event["type"] in ("next", "eof", "iteration_end")
                    and not old_reverse
                    and not self.state["reverse"]
                    and self.state["index"] == [old_index[0], old_index[1] + 1]
                )
                self.adopted = (
                    self.prefetch.take(target_token, self.state["entry_id"]) or {} if normal else {}
                )
                if not normal:
                    self.prefetch.cancel("navigation")
            elif event["type"] in ("previous", "reverse", "replay", "quit", "close"):
                self.prefetch.cancel("navigation")
        if (
            event["type"] == "next"
            and self.state.get("loop_exit_requested")
            and "base" in self.sources
        ):
            self.sources["base"].request_loop_exit()
        for effect in effects:
            kind = effect["type"]
            if kind == "prepare":
                reason = event["type"]
                if reason in ("eof", "iteration_end"):
                    reason = "skip_all" if self.state.get("skip_all") else "auto_next"
                self._prepare(reason, now, effect.get("preserve_live", False))
            elif kind == "start":
                self.motion_clock = set_playing(self.motion_clock, True, now)
                for source in self.sources.values():
                    source.play(now)
                self.live.entry["requested_playing"] = True
                self.live.start_entries(now)
            elif kind == "resume":
                if not self.state["ended"]:
                    self.motion_clock = set_playing(self.motion_clock, True, now)
                    for source in self.sources.values():
                        source.play(now)
                    self.live.entry["requested_playing"] = True
                    self.live.start_entries(now)
            elif kind in ("pause", "stop_files"):
                self.motion_clock = set_playing(self.motion_clock, False, now)
                for source in self.sources.values():
                    source.pause()
            elif kind == "loop":
                pass
            elif kind == "begin_shutdown":
                self.live.begin_shutdown()
                if self.prefetch is not None:
                    self.prefetch.cancel("shutdown")
                if self.live_pool is not None:
                    self.live_pool.begin_shutdown()
                    close_pool()
                self._close_sources(self.sources)
                self._close_sources(self.preview_sources)
                self.thumbnails.clear()
        return effects

    def _accept_update(self, key, update, frames):
        if update.get("error") and update["error"] not in self.errors:
            self.errors.append(update["error"])
        if key in frames and update.get("error"):
            frames[key]["error"] = update["error"]
        if "rgba" not in update or update.get("frame_id") == frames.get(key, {}).get("frame_id"):
            return
        began = time.perf_counter()
        old = frames.get(key, {}).get("lease")
        # Ten sam rozmiar: podmiana treści w miejscu zamiast nowej tekstury na każdą klatkę.
        in_place = (
            hasattr(old, "update")
            and (getattr(old, "width", None), getattr(old, "height", None))
            == (update.get("width"), update.get("height"))
            and id(old) not in self._held_ids()
        )
        try:
            if in_place:
                old.update(update)
                lease = old
            else:
                lease = self.uploader(update)
        except Exception as error:  # noqa: BLE001 — granica adaptera GL zachowuje ostatni obraz
            self.errors.append(f"Upload {key}: {error}")
            return
        if old and not in_place:
            self.retired_leases.append(old)
        frames[key] = {**update, "texture": lease.texture, "lease": lease}
        frames[key]["upload_ms"] = (time.perf_counter() - began) * 1000

    def tick(self, now, process_input=None):
        """Budget mediów 4 ms; podgląd dostaje pozostały czas po głównych źródłach."""
        if self.live_pool is not None:
            self.live_pool.poll(now)
            process_counts()
        if self.state.get("message") and now >= self.state.get("message_until", 0):
            self.dispatch(
                {"type": "message_expired", "revision": self.state["message_revision"]}, now
            )
        for event in self.live.poll(now):
            if event["type"] == "navigate" and event["entry_id"] == self.state["entry_id"]:
                self.dispatch({"type": event["direction"]}, now)
                continue
            if event["type"] == "restore_frame":
                key = str(event["index"])
                old = self.frames.get(key, {}).get("lease")
                if old and old is not event["lease"]:
                    self.retired_leases.append(old)
                lease, owned = event["lease"], event["frame"]
                self.frames[key] = {
                    "texture": lease.texture,
                    "lease": lease,
                    "width": owned.width,
                    "height": owned.height,
                }
            if event["type"] == "frame":
                owned = event["frame"]
                try:
                    lease = self.uploader(
                        {"width": owned.width, "height": owned.height, "rgba": owned.pixels}
                    )
                except Exception as error:  # noqa: BLE001 — błąd GL odcina warstwę bez ACK
                    self.errors.append(str(error))
                    self.live._fail(event["index"], f"Upload live: {error}")
                    continue
                key = str(event["index"])
                old = self.frames.get(key, {}).get("lease")
                if old:
                    self.retired_leases.append(old)
                self.frames[key] = {
                    "texture": lease.texture,
                    "lease": lease,
                    "width": owned.width,
                    "height": owned.height,
                }
                self.live.accept_frame(event, lease)
        if process_input is not None:
            process_input()
        deadline = time.perf_counter() + 0.004
        keys = list(self.sources)
        if keys:
            start = self.cursor % len(keys)
            keys = keys[start:] + keys[:start]
            self.cursor += 1
        for key in keys:
            remaining = (deadline - time.perf_counter()) * 1000
            if remaining <= 0:
                break
            source = self.sources[key]
            update = source.poll(now, 0 if self.state["preparing"] else None, min(1, remaining))
            wrapped = (
                key == "base"
                and self._slide().get("loop")
                and update.get("pts", 0) < self.frames.get(key, {}).get("pts", 0)
                and not self.state["preparing"]
            )
            if wrapped:
                if self.state.get("loop_exit_requested"):
                    self.state["clock"]["position"] = update.get("duration") or media_time(
                        self.state["clock"], now
                    )
                    self.state["clock"]["anchor"] = now
                self.dispatch({"type": "iteration_end"}, now)
            if not self.state["ended"] or self.state["preparing"]:
                self._accept_update(key, update, self.frames)
            if (
                key == "base"
                and update["status"] == "eof"
                and (
                    self._slide()["kind"] != "image"
                    or self.state.get("skip_all")
                    or self._slide().get("auto_next")
                )
                and not self.state["preparing"]
                and not self.state["ended"]
            ):
                if update.get("duration") is not None:
                    self.state["clock"]["position"] = update["duration"]
                    self.state["clock"]["anchor"] = now
                self.dispatch({"type": "eof"}, now)
                break
        files_ready = all(
            key in self.frames or source.status == "error" for key, source in self.sources.items()
        )
        self.live.files_ready = files_ready
        if self.state["preparing"] and (self.live.ready or now >= self.prepare_deadline):
            if now >= self.prepare_deadline:
                self.errors.append("Timeout przygotowania 5 s")
            if hasattr(self.live, "release_prefetch"):
                self.live.release_prefetch()
            self.dispatch({"type": "ready"}, now)
        for key, source in self.preview_sources.items():
            remaining = (deadline - time.perf_counter()) * 1000
            if remaining <= 0:
                break
            update = source.poll(now, None, min(1, remaining))
            self._accept_update(key, update, self.preview_frames)
            if key in self.preview_frames and key not in self.preview_started:
                source.play(now)
                self.preview_started.add(key)
                self.preview_anchors[key] = now
        if self.prefetch is not None:
            if not self.state["preparing"] and not self.state.get("closing"):
                token, target = self._prefetch_target()
                if target is not None:
                    self.prefetch.prepare(token, target)
            self.prefetch.poll(now)
        active_time = media_time(self.motion_clock, now)
        for index in self.live.sessions:
            if str(index) in self.frames:
                self.frames[str(index)].update(
                    active=self.live.active == index, error=index in self.live.failed
                )
        if self.held and not self.state["preparing"]:
            held, self.held = self.held, None
            self._retire_unused(held["frames"])
        if self.held:
            self.stage, self.stage_frames = self.held["stage"], self.held["frames"]
            self.stage_time = self.held["time"]
        else:
            self.stage = {
                "resolution": self.state["resolution"],
                "slide": self._slide(),
                "aspect_ratio": self.options.get("aspect_ratio", "keep"),
                "reverse": self.state["reverse"],
            }
            self.stage_frames, self.stage_time = self.frames, active_time
        self.composition = compose(self.stage, self.stage_frames, self.stage_time)
        if self.preview:
            slide = {**self.preview, "layers": []}
            for index, layer in enumerate(self.preview.get("layers", [])):
                key = str(index)
                t = max(0, now - self.preview_anchors.get(key, now)) * layer.get("rate", 1)
                duration = self.preview_frames.get(key, {}).get("duration")
                if duration and layer["kind"] != "image":
                    t %= duration
                if layer["kind"] == "live":
                    t = 0
                slide["layers"].append({**layer, "rect": rect_at(layer, t), "keyframes": []})
            self.preview_composition = compose(
                {"resolution": self.preview["resolution"], "slide": slide}, self.preview_frames, 0
            )
        self.retired_sources = [
            source for source in self.retired_sources if not source.poll_closed(now)
        ]
        deck = self.state["index"][0]
        presentation = self.manifest["presentations"][deck]
        self.thumbnail_requests = []
        if self.show_info and not self.state.get("closing"):
            for index in self.thumbnail_indices:
                if 0 <= index < len(presentation["slides"]):
                    self.request_thumbnail((deck, index), (256, 144))
        requests = self.thumbnail_requests
        self.thumbnails.configure((id(self.manifest), deck), requests)
        self.thumbnails.poll_thumbnails(
            now, allow_start=bool(requests) and time.perf_counter() < deadline
        )
        return self.presenter_snapshot(now)

    def presenter_snapshot(self, now):
        """Info i S czytają tę samą kompozycję i trwałe diagnozy historii."""
        result = snapshot(self.state)
        result.update(
            notes=self._slide().get("notes", ""),
            elapsed=timer_elapsed(self.state["presenter_timer"], now),
            composition=self.composition,
            errors=list(self.errors)
            + (self.live_pool.errors if self.live_pool is not None else []),
            active_live=self.live.active,
            loop=self._slide().get("loop", False),
            thumbnails={
                key[1]: {
                    name: value[name]
                    for name in ("texture", "width", "height", "error")
                    if name in value
                }
                for key, value in self.thumbnails.cache.items()
            },
            process_counts=self.live_pool.budget.snapshot()
            if self.live_pool is not None
            else process_counts(self.thumbnails),
            live_pool={
                "hits": self.live_pool.hits,
                "misses": self.live_pool.misses,
                "errors": list(self.live_pool.errors),
            }
            if self.live_pool is not None
            else {},
            prefetch={
                "hits": self.prefetch.hits,
                "bytes": self.prefetch.bytes,
                "ready": sum(item["ready"] for item in self.prefetch.items.values()),
            }
            if self.prefetch is not None
            else {},
            thumbnail_bytes=self.thumbnails.bytes
            + (self.thumbnails.working_bytes if self.thumbnails.worker else 0),
            clips=[
                {
                    "index": key,
                    "status": "eof" if getattr(source, "eof", False) else source.status,
                    "file": source.media.get("file"),
                    "error": getattr(source, "error", None),
                }
                for key, source in self.sources.items()
                if key != "base"
            ],
            histories=[
                {
                    "status": history.status,
                    "degraded": history.degraded,
                    "cue_states": [entry.cue_state for entry in history.stack],
                }
                for history in self.live.histories.values()
            ],
        )
        return result

    def after_render(self):
        """Wywołaj po draw data obu viewportów w aktywnym kontekście GL."""
        leases, self.retired_leases = self.retired_leases, []
        pinned = {id(lease) for lease in self.live.pinned_leases} | self._held_ids()
        seen = set()
        for lease in leases:
            if id(lease) in seen:
                continue
            seen.add(id(lease))
            if id(lease) in pinned:
                self.retired_leases.append(lease)
            else:
                lease.close()

    @property
    def closed(self):
        """Dekodery i live muszą zakończyć się przed zniszczeniem kontekstu."""
        return (
            self.state.get("closing")
            and self.live.closed
            and (self.live_pool is None or self.live_pool.closed)
            and not process_counts()["idle"]
            and not process_counts()["retiring"]
            and (self.prefetch is None or not self.prefetch.items and not self.prefetch.retiring)
            and not self.retired_sources
            and self.thumbnails.worker is None
        )
