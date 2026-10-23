"""Minimalny odbiornik Qt: python examples/live_receiver.py plik.py Klasa."""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel

from manimcue.live_session import LiveSession, LiveSpec


class Receiver(QLabel):
    """Obraz ma własne bajty; zamknięcie jest odroczone do odebrania procesu."""

    def __init__(self, spec):
        super().__init__("Przygotowanie sceny…")
        self.session = LiveSession()
        self.closing = False
        self.stopped = False
        self.resize(spec.width, spec.height)
        self.session.start(spec)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(4)

    def tick(self):
        events = self.session.poll()
        self.stopped = self.stopped or "STOPPED" in events
        frame = self.session.try_read_frame()
        if frame is not None:
            image = QImage(
                frame.pixels,
                frame.width,
                frame.height,
                frame.width * 4,
                QImage.Format.Format_RGBA8888,
            )
            self.setPixmap(QPixmap.fromImage(image.copy()))
        if self.session.error:
            self.setWindowTitle(self.session.error)
        elif events:
            self.setWindowTitle(events[-1])
        if self.closing and self.stopped:
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Right:
            self.session.send("next")
        elif event.key() == Qt.Key.Key_Left:
            self.session.send("back")
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.closing = True
        self.session.request_stop()
        if self.stopped:
            self.timer.stop()
            event.accept()
        else:
            event.ignore()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene_file")
    parser.add_argument("scene_name")
    parser.add_argument("--engine", choices=("manimgl", "ce-cairo"), default="manimgl")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    receiver = Receiver(LiveSpec(str(Path(args.scene_file).resolve()), args.scene_name, engine=args.engine))
    receiver.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
