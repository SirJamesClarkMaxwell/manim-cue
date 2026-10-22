"""Warstwy-klipy w playerze (F5, D29-D31): wspólny start, śledzenie bazy, ruch warstw.

Grupa slajdu to baza wideo i warstwy-klipy wideo. Wejście na slajd przygotowuje pierwszą klatkę
każdego playera (gra do pierwszej poprawnej klatki i staje), a gdy gotowe są wszystkie — jedno
wspólne `play()` (D31). Potem klipy śledzą stan bazy (`playbackStateChanged`), więc istniejące
ścieżki playera (`next`, koniec pętli, `skip_all`, `auto_next`) sterują całą grupą. Ruch warstw
(D30) liczy własny zegar aktywnego czasu slajdu, nie `position()` bazy.
"""

import time
from collections.abc import Callable
from pathlib import Path

from qtpy.QtCore import QElapsedTimer, QObject, Qt, QTimer, QUrl, Signal
from qtpy.QtMultimedia import QMediaPlayer, QVideoFrame

from manimcue.composition import SlideComposition
from manimcue.slides.config import ClipLayer, SlideConfig
from manimcue.slides.logger import logger

MOTION_MS = 16
"""Okres aktualizacji geometrii warstw w ruchu (~60 Hz)."""

PRIME_TIMEOUT_MS = 5000
"""Player bez pierwszej klatki po tym czasie wypada z grupy; reszta startuje."""

BASE = "base"


class ClipGroup(QObject):
    """Playery warstw-klipów bieżącego slajdu, bariera pierwszych klatek i zegar ruchu."""

    changed = Signal()

    def __init__(
        self,
        composition: SlideComposition,
        base: QMediaPlayer,
        restored: Callable[[QVideoFrame], bool] = lambda frame: False,
    ) -> None:
        """``restored`` rozpoznaje klatkę przywróconą przez `Player.frame_changed` (stara baza)."""
        super().__init__()
        self.composition = composition
        self.base = base
        self.restored = restored
        self.live = None
        self.connections: list = []
        self.problems: list[str] = []
        self.released_at: float | None = None
        self.layers: list = []
        self.players: dict[int, QMediaPlayer] = {}
        self.frames: dict[int, QVideoFrame] = {}
        self.entry = 0
        self.preparing = False
        self.pending: set = set()
        self.requested_playing = True
        self.static_base = False
        self.base_frame = None
        self.running = False
        self.elapsed_ms = 0
        self.clock = QElapsedTimer()
        self.motion = QTimer(self)
        self.motion.setTimerType(Qt.TimerType.PreciseTimer)
        self.motion.timeout.connect(self.move)
        base.playbackStateChanged.connect(self.follow_base)
        composition.video_item.videoSink().videoFrameChanged.connect(self.on_base_frame)

    @staticmethod
    def needed(slide: SlideConfig) -> bool:
        """Grupa tylko dla slajdów z klipem wideo albo ruchem; reszta idzie ścieżką upstreamu."""
        return any(
            layer.keyframes or (isinstance(layer, ClipLayer) and layer.is_video)
            for layer in slide.layers
        )

    @property
    def static_active(self) -> bool:
        """Grupa nad bazą statyczną (obraz): sama trzyma stan odtwarzania."""
        return bool(self.layers) and self.static_base

    def enter(self, slide: SlideConfig, base_video: bool, start_paused: bool, rate: float) -> bool:
        """Nowy slajd; True, gdy grupa przejmuje start bazy (przygotowanie pierwszej klatki)."""
        self.clear()
        if not self.needed(slide) and not (self.live and self.live.entry_cues):
            return False
        self.layers = slide.layers
        self.static_base = not base_video
        self.requested_playing = not start_paused
        self.preparing = True
        entry = self.entry
        for index, layer in enumerate(slide.layers):
            if not (isinstance(layer, ClipLayer) and layer.is_video):
                continue
            self.composition.show_placeholder(index)
            item = self.composition.layer_items[index]
            player = QMediaPlayer(self)
            # Sygnały przed setSource (runda 11, p. 6); entry odcina sygnały poprzedniego slajdu,
            # a clear() je rozłącza — element bywa zachowany między wejściami (runda 12, p. 8).
            on_frame = lambda frame, i=index, e=entry: self.on_frame(e, i, frame)
            item.videoSink().videoFrameChanged.connect(on_frame)
            self.connections.append((item.videoSink().videoFrameChanged, on_frame))
            player.errorOccurred.connect(
                lambda *_, i=index, e=entry: self.drop(e, i, "blad odtwarzania")
            )
            player.setVideoOutput(item)
            # Slajd zapętlony zapętla też klipy (każdy osobno — dryf zaakceptowany w D17).
            player.setLoops(-1 if layer.loop or slide.loop else 1)
            player.setPlaybackRate(layer.playback_rate * rate)
            player.setSource(QUrl.fromLocalFile(str(Path(layer.file).resolve())))
            player.play()
            self.players[index] = player
            self.pending.add(index)
        if base_video:
            self.pending.add(BASE)
        if self.live and self.live.waiting_for_entry():
            self.pending.add("live")
        QTimer.singleShot(PRIME_TIMEOUT_MS, lambda e=entry: self.prime_timeout(e))
        self.move()
        if not self.pending:
            self.start()
        return True

    def on_base_frame(self, frame: QVideoFrame) -> None:
        # Runda 12, p. 1: klatka przywrócona przez `frame_changed` albo spóźniona ze starego
        # źródła nie może zwolnić bariery — tylko nowa klatka dekodera po załadowaniu źródła.
        loading = self.base.mediaStatus() in (
            QMediaPlayer.MediaStatus.NoMedia,
            QMediaPlayer.MediaStatus.LoadingMedia,
        )
        if (
            self.preparing
            and BASE in self.pending
            and frame.isValid()
            and not loading
            and not self.restored(frame)
        ):
            self.base_frame = frame
            self.base.pause()
            self.pending.discard(BASE)
            self.maybe_start()
        elif self.preparing and self.base_frame is not None and frame != self.base_frame:
            # Pauza dekodera jest asynchroniczna; spóźniona klatka nie rusza obrazu bariery.
            self.composition.video_item.videoSink().setVideoFrame(self.base_frame)

    def on_frame(self, entry: int, index: int, frame: QVideoFrame) -> None:
        if entry != self.entry:
            return
        if frame.isValid():
            if self.preparing and index not in self.pending:
                if index in self.frames and frame != self.frames[index]:
                    self.composition.layer_items[index].videoSink().setVideoFrame(
                        self.frames[index]
                    )
                return
            self.composition.clear_placeholder(index)
            self.frames[index] = frame
            if self.preparing and index in self.pending:
                self.players[index].pause()
                self.pending.discard(index)
                self.maybe_start()
        elif index in self.frames:
            # Jak `Player.frame_changed`: koniec klipu „spłukuje” ostatnią klatkę na czarno.
            self.composition.layer_items[index].videoSink().setVideoFrame(self.frames[index])

    def drop(self, entry: int, index: int, reason: str) -> None:
        """Warstwa bez klatki wypada z grupy; jej miejsce zostaje puste, reszta gra.

        Treść logu bez polskich znaków — konsola Windows (cp1252) ich nie zapisze; tak samo
        jak logi `live_scene.py`.
        """
        if entry != self.entry or index not in self.players:
            return
        self.problems.append(f"klip {index + 1}: {reason}")
        self.changed.emit()
        logger.error(f"Warstwa {index + 1} ({self.layers[index].describe()}): {reason}")
        player = self.players.pop(index)
        player.stop()
        player.setVideoOutput(None)
        player.deleteLater()
        # Runda 12, p. 4: zamiast pustego elementu wideo — miniatura albo zastępnik.
        self.composition.freeze_layer(index)
        self.pending.discard(index)
        self.maybe_start()

    def prime_timeout(self, entry: int) -> None:
        if entry != self.entry or not self.preparing:
            return
        for index in [key for key in self.pending if key not in (BASE, "live")]:
            self.drop(entry, index, f"brak pierwszej klatki po {PRIME_TIMEOUT_MS} ms")
        if BASE in self.pending:
            self.problems.append("baza: timeout pierwszej klatki")
        if "live" in self.pending:
            self.problems.append("live: timeout, cue pominięte")
        if self.live:
            self.live.cancel_unready_entries()
        self.pending.clear()
        self.maybe_start()

    def maybe_start(self) -> None:
        if self.live and not self.live.waiting_for_entry():
            self.pending.discard("live")
        if self.preparing and not self.pending:
            self.start()

    def start(self) -> None:
        """Koniec przygotowania: wspólny start albo pauza (`start_paused`, pauza w trakcie)."""
        self.preparing = False
        self.released_at = time.perf_counter()
        if self.requested_playing:
            self.play_all()
        self.changed.emit()

    def play_all(self) -> None:
        if not self.static_base:
            self.base.play()
        for player in self.players.values():
            if player.mediaStatus() != QMediaPlayer.MediaStatus.EndOfMedia:
                player.play()
        self.run_clock(True)
        if self.live:
            self.live.start_entries()

    def pause_all(self) -> None:
        if not self.static_base:
            self.base.pause()
        for player in self.players.values():
            player.pause()
        self.run_clock(False)

    def follow_base(self, state: QMediaPlayer.PlaybackState) -> None:
        """Klipy idą za bazą: gra → grają (poza skończonymi), pauza i koniec → pauza."""
        if not self.layers or self.preparing or self.static_base:
            return
        if state == QMediaPlayer.PlaybackState.PlayingState:
            for player in self.players.values():
                if player.mediaStatus() != QMediaPlayer.MediaStatus.EndOfMedia:
                    player.play()
            self.run_clock(True)
            if self.live:
                self.live.start_entries()
        else:
            for player in self.players.values():
                player.pause()
            self.run_clock(False)

    def toggle(self) -> None:
        """`PLAY_PAUSE` nad bazą statyczną albo w trakcie przygotowania (żądany stan)."""
        if self.preparing:
            self.requested_playing = not self.requested_playing
            self.changed.emit()
        elif self.running:
            self.pause_all()
        else:
            self.play_all()

    def replay(self) -> None:
        """Replay: klipy od początku, zegar ruchu od zera i odtwarzanie — jak replay bazy.

        Baza wideo dostaje `setPosition(0)` i `play()` od playera, a klipy idą za nią; nad bazą
        statyczną grupę wznawia replay sam (ta sama semantyka, runda 12, p. 2). W trakcie
        przygotowania player replay pomija.
        """
        if not self.layers or self.preparing:
            return
        for player in self.players.values():
            player.setPosition(0)
            if self.running:
                player.play()
        self.elapsed_ms = 0
        self.clock.restart()
        if self.static_base and not self.running:
            self.play_all()
        self.move()

    def run_clock(self, running: bool) -> None:
        if running and not self.running:
            self.clock.restart()
            if any(layer.keyframes for layer in self.layers):
                self.motion.start(MOTION_MS)
        elif not running and self.running:
            self.elapsed_ms += self.clock.elapsed()
            self.motion.stop()
        self.running = running
        self.move()
        self.changed.emit()

    def seconds(self) -> float:
        """Aktywny czas slajdu: od wspólnego startu, bez pauz (D30)."""
        return (self.elapsed_ms + (self.clock.elapsed() if self.running else 0)) / 1000

    def move(self) -> None:
        t = self.seconds()
        for index, layer in enumerate(self.layers):
            if layer.keyframes:
                self.composition.set_layer_rect(index, layer.rect_at(t))

    def clear(self) -> None:
        """Wyjście ze slajdu: playery zatrzymane, sygnały starego wejścia odcięte."""
        self.problems = []
        self.entry += 1
        for signal, slot in self.connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass  # element już usunięty z kompozycji
        self.connections = []
        for player in self.players.values():
            player.stop()
            player.deleteLater()
        self.players = {}
        self.frames = {}
        self.base_frame = None
        self.layers = []
        self.preparing = False
        self.pending = set()
        self.motion.stop()
        self.running = False
        self.elapsed_ms = 0
