"""Kompozycja slajdu w Qt (F3, D25): jedna `QGraphicsScene` na slajd, wiele widoków.

Okno główne i bieżący widok Info to dwa `SlideView` tej samej `SlideComposition`, więc Info
pokazuje ten sam obraz z konstrukcji. Podgląd następnego slajdu ma własną kompozycję.
"""

from pathlib import Path

from qtpy.QtCore import QPointF, QRectF, QSizeF, Qt, Signal
from qtpy.QtGui import QColor, QImage, QPainter, QPixmap, QTransform
from qtpy.QtMultimediaWidgets import QGraphicsVideoItem
from qtpy.QtWidgets import QFrame, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from manimcue.slides.config import LiveLayer

PLACEHOLDER = QColor(40, 40, 40)
"""Wypełnienie warstwy live bez miniatury (np. JSON sprzed renderu miniatur)."""


class SlideComposition(QGraphicsScene):
    """Kadr slajdu w pikselach prezentacji: wideo albo obraz bazowy, nad nim warstwy live."""

    def __init__(
        self,
        resolution: tuple[int, int],
        aspect_ratio_mode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio,
    ) -> None:
        width, height = resolution
        super().__init__(0, 0, width, height)
        self.aspect_ratio_mode = aspect_ratio_mode
        self.video_item = QGraphicsVideoItem()
        self.video_item.setSize(QSizeF(width, height))
        self.video_item.setAspectRatioMode(aspect_ratio_mode)
        self.addItem(self.video_item)
        self.image_item = QGraphicsPixmapItem()
        self.image_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.image_item.hide()
        self.addItem(self.image_item)
        self.layer_items: list[QGraphicsPixmapItem] = []
        self.layer_rects: list[QRectF] = []
        self.layers: list[LiveLayer] | None = None

    def set_resolution(self, resolution: tuple[int, int]) -> None:
        """Kadr innej prezentacji (`present A B` z różnymi rozdzielczościami)."""
        width, height = resolution
        if self.sceneRect() != QRectF(0, 0, width, height):
            self.setSceneRect(0, 0, width, height)
            self.video_item.setSize(QSizeF(width, height))

    def show_video(self) -> None:
        self.image_item.hide()
        self.video_item.show()

    def show_image(self, file: Path) -> None:
        """Obraz bazowy dopasowany do kadru, wyśrodkowany."""
        rect = self.sceneRect()
        pixmap = QPixmap(str(file)).scaled(
            rect.size().toSize(),
            self.aspect_ratio_mode,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_item.setPixmap(pixmap)
        self.image_item.setPos(
            (rect.width() - pixmap.width()) / 2, (rect.height() - pixmap.height()) / 2
        )
        self.video_item.hide()
        self.image_item.show()

    def set_layers(self, layers: list[LiveLayer]) -> None:
        """Warstwy live w ich prostokątach, z miniaturą; kolejność listy to z-order.

        Ta sama lista (replay, reverse, pętla slajdu) zostaje: przebudowa wstawiłaby miniaturę
        nad obraz live, a scena w bezczynności nie publikuje nowej klatki (F4).
        """
        if layers is self.layers:
            return
        self.layers = layers
        for item in self.layer_items:
            self.removeItem(item)
        self.layer_items = []
        self.layer_rects = []
        for z, layer in enumerate(layers, start=1):
            rect = self.layer_rect(layer)
            self.layer_rects.append(rect)
            if layer.thumbnail is not None:
                pixmap = QPixmap(str(layer.thumbnail))
            else:
                pixmap = QPixmap(rect.size().toSize())
                pixmap.fill(PLACEHOLDER)
            item = QGraphicsPixmapItem()
            item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            self.set_layer_pixmap(item, pixmap, rect)
            item.setZValue(z)
            self.addItem(item)
            self.layer_items.append(item)

    def set_layer_image(self, index: int, image: QImage) -> None:
        """Nowy obraz warstwy w jej prostokącie (miniatura → klatki live w F4).

        Prostokąt z `set_layers`, nie z obrysu elementu: obrys po transformacji (F5) nie jest
        pierwotnym prostokątem (runda 9, p. 10). Wywołujący trzyma bajty obrazu do powrotu.
        """
        self.set_layer_pixmap(
            self.layer_items[index], QPixmap.fromImage(image), self.layer_rects[index]
        )

    def layer_rect(self, layer: LiveLayer) -> QRectF:
        """Prostokąt warstwy we współrzędnych sceny (piksele prezentacji)."""
        scene = self.sceneRect()
        x, y, w, h = layer.rect
        return QRectF(x * scene.width(), y * scene.height(), w * scene.width(), h * scene.height())

    @staticmethod
    def set_layer_pixmap(item: QGraphicsPixmapItem, pixmap: QPixmap, rect: QRectF) -> None:
        """Pixmapa rozciągnięta na prostokąt warstwy — miniatura i (od F4) klatki live."""
        item.setPixmap(pixmap)
        item.setPos(rect.topLeft())
        if pixmap.width() and pixmap.height():
            item.setTransform(
                QTransform.fromScale(rect.width() / pixmap.width(), rect.height() / pixmap.height())
            )


class SlideView(QGraphicsView):
    """Widok kompozycji dopasowany do rozmiaru, czarne pasy poza kadrem."""

    layer_clicked = Signal(int)
    """Klik w widoku: indeks warstwy live pod kursorem albo -1 poza warstwami (F4)."""
    layer_double_clicked = Signal(int)
    pointer_dragged = Signal(QPointF, bool)
    """Przeciąganie lewym przyciskiem: punkt we współrzędnych sceny i czy wciśnięty Shift (D28)."""
    pointer_released = Signal()
    wheel_turned = Signal(float)
    """Obrót kółka w ząbkach (120 jednostek Qt = 1), dodatni od użytkownika."""

    def __init__(
        self,
        composition: SlideComposition,
        aspect_ratio_mode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio,
    ) -> None:
        super().__init__(composition)
        self.aspect_ratio_mode = aspect_ratio_mode
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor("black"))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # Bez fokusu: QAbstractScrollArea zjadłby strzałki na przewijanie, a klawisze
        # mają trafiać do okna (Player.keyPressEvent, Info.keyPressEvent).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def layer_at(self, point) -> int:
        """Indeks warstwy live pod punktem viewportu albo -1.

        items(), nie itemAt(): obwódka aktywnej warstwy leży wyżej i przesłoniłaby warstwę.
        """
        layer_items = self.scene().layer_items
        for item in self.items(point):
            for index, layer_item in enumerate(layer_items):
                if layer_item is item:
                    return index
        return -1

    def mousePressEvent(self, event) -> None:
        self.layer_clicked.emit(self.layer_at(event.position().toPoint()))
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.layer_double_clicked.emit(self.layer_at(event.position().toPoint()))
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self.pointer_dragged.emit(self.mapToScene(event.position().toPoint()), shift)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.pointer_released.emit()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        # Bez przewijania widoku: kadr zawsze mieści się w oknie (fitInView).
        self.wheel_turned.emit(event.angleDelta().y() / 120)
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), self.aspect_ratio_mode)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.fitInView(self.sceneRect(), self.aspect_ratio_mode)
