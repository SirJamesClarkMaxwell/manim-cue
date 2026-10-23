"""Reproduktor F5/8 w samym Qt: bez manim-cue, sondy i zachowywania klatek.

Argumenty: N katalog_z_plikami_0.mp4_do_N.mp4. Uruchamiaj z nadzorca procesu:
QTimer nie przerwie natywnego oczekiwania w sterowniku GPU.
"""

import json
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QSizeF, Qt, QTimer, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)


def main():
    count = int(sys.argv[1])
    media = Path(sys.argv[2]).resolve()
    app = QApplication([])
    players, items, scenes, views = [], [], [], []
    counts = {}
    main_window = QWidget()
    main_window.resize(1920, 1080)
    main_layout = QVBoxLayout(main_window)
    info = QWidget()
    info_layout = QHBoxLayout(info)
    for group in range(2):
        scene = QGraphicsScene()
        scene.setSceneRect(0, 0, 1920, 1080)
        scenes.append(scene)
        view = QGraphicsView(scene)
        views.append(view)
        view.setMinimumSize(360, 240)
        (main_layout if group == 0 else info_layout).addWidget(view)
        if group == 0:
            second = QGraphicsView(scene)
            second.setFixedSize(720, 480)
            views.append(second)
            info_layout.addWidget(second)
        for index in range(count + 1):
            item = QGraphicsVideoItem()
            scene.addItem(item)
            item.setSize(QSizeF(1920, 1080) if index == 0 else QSizeF(576, 324))
            if index:
                item.setPos(38 + (index - 1) * 614, 324)
            item.setZValue(index)
            items.append(item)
            player = QMediaPlayer()
            player.setVideoOutput(item)
            player.setLoops(-1)
            player.setSource(QUrl.fromLocalFile(str(media / f"{index}.mp4")))
            key = f"{group}-{index}"
            counts[key] = 0

            def frame_changed(frame, key=key):
                counts[key] += 1

            item.videoSink().videoFrameChanged.connect(frame_changed)
            players.append(player)
    main_window.show()
    info.show()
    for view in views:
        view.fitInView(view.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
    for player in players:
        player.play()
    started = time.perf_counter()
    QTimer.singleShot(10000, app.quit)
    app.exec()
    print(
        json.dumps(
            {
                "clips": count,
                "duration": time.perf_counter() - started,
                "counts": counts,
                "hw": os.environ.get("QT_FFMPEG_DECODING_HW_DEVICE_TYPES"),
            }
        ),
        flush=True,
    )
    for player in players:
        player.stop()
        player.setSource(QUrl())


if __name__ == "__main__":
    main()
