"""Kompozycja slajdu w Qt (F3, D25): jedna `QGraphicsScene` na slajd, wiele widoków.

Okno główne i bieżący widok Info to dwa `SlideView` tej samej `SlideComposition`, więc Info
pokazuje ten sam obraz z konstrukcji. Podgląd następnego slajdu ma własną kompozycję.
"""

import math
from pathlib import Path

from qtpy.QtCore import QPointF, QRectF, QSizeF, Qt, Signal
from qtpy.QtGui import QColor, QImage, QPainter, QPixmap, QTransform
from qtpy.QtMultimediaWidgets import QGraphicsVideoItem
from qtpy.QtWidgets import QApplication, QFrame, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from manimcue.slides.config import ClipLayer, Layer, LiveLayer, Rect

PLACEHOLDER = QColor(40, 40, 40)
"""Wypełnienie warstwy bez miniatury (np. JSON sprzed renderu miniatur)."""


class SlideComposition(QGraphicsScene):
    """Kadr slajdu w pikselach prezentacji: wideo albo obraz bazowy, nad nim warstwy."""

    layer_moved = Signal(int)
    """Nowy prostokąt warstwy (ruch, D30) — np. dla obwódki aktywnej warstwy live."""

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
        self.layer_items: list[QGraphicsPixmapItem | QGraphicsVideoItem] = []
        self.layer_rects: list[QRectF] = []
        self.placeholders: dict[int, QGraphicsPixmapItem] = {}
        self.layers: list[Layer] | None = None
        self.mode: tuple[bool, bool] = (False, False)

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

    def set_layers(self, layers: list[Layer], video: bool = False, at_end: bool = False) -> None:
        """Warstwy w ich prostokątach; kolejność listy to z-order dla wszystkich rodzajów.

        ``video`` — klipy wideo jako `QGraphicsVideoItem` dla playerów grupy (okno główne);
        bez niego, w podglądzie, klip to jego miniatura. ``at_end`` — reverse (F5): klipy
        pokazują ostatnią klatkę, a wszystkie warstwy stoją w prostokącie końcowym.
        Ten sam układ (replay, pętla) zostaje: przebudowa wstawiłaby miniaturę nad obraz live,
        a scena w bezczynności nie publikuje nowej klatki (F4); przy zmianie trybu tego samego
        slajdu obraz live przechodzi do nowego elementu.
        """
        mode = (video, at_end)
        if layers is self.layers and mode == self.mode:
            return
        kept = {}
        if layers is self.layers:
            kept = {
                index: item.pixmap()
                for index, (layer, item) in enumerate(zip(layers, self.layer_items, strict=True))
                if isinstance(layer, LiveLayer)
            }
        self.layers, self.mode = layers, mode
        for item in self.layer_items:
            self.removeItem(item)
        for placeholder in self.placeholders.values():
            self.removeItem(placeholder)
        self.placeholders = {}
        self.layer_items = []
        self.layer_rects = []
        for index, layer in enumerate(layers):
            rect = self.scene_rect(layer.rect_at(math.inf if at_end else 0))
            if isinstance(layer, ClipLayer) and layer.is_video and video and not at_end:
                item = QGraphicsVideoItem()
                item.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
                item.setPos(rect.topLeft())
                item.setSize(rect.size())
            else:
                item = QGraphicsPixmapItem()
                item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
                pixmap = kept[index] if index in kept else self.layer_pixmap(layer, rect, at_end)
                self.set_layer_pixmap(item, pixmap, rect, isinstance(layer, ClipLayer))
            item.setZValue(index + 1)
            self.addItem(item)
            self.layer_items.append(item)
            self.layer_rects.append(rect)
            if isinstance(item, QGraphicsVideoItem):
                self.show_placeholder(index)

    @staticmethod
    def layer_pixmap(layer: Layer, rect: QRectF, at_end: bool) -> QPixmap:
        """Obraz warstwy bez procesu i playera: miniatura (live, klip), plik (obraz)."""
        if isinstance(layer, ClipLayer):
            source = layer.end_thumbnail if at_end else layer.thumbnail
            source = source or (None if layer.is_video else layer.file)
        else:
            source = layer.thumbnail
        if source is not None:
            return QPixmap(str(source))
        pixmap = QPixmap(rect.size().toSize())
        pixmap.fill(PLACEHOLDER)
        return pixmap

    def set_layer_image(self, index: int, image: QImage) -> None:
        """Nowy obraz warstwy w jej prostokącie (miniatura → klatki live w F4).

        Prostokąt z `set_layers`/`set_layer_rect`, nie z obrysu elementu: obrys po
        transformacji nie jest pierwotnym prostokątem (runda 9, p. 10). Wywołujący trzyma bajty
        obrazu do powrotu.
        """
        self.set_layer_pixmap(
            self.layer_items[index], QPixmap.fromImage(image), self.layer_rects[index]
        )

    def freeze_layer(self, index: int) -> None:
        """Warstwa-klip bez playera (awaria): miniatura albo zastępnik w miejsce elementu wideo."""
        old = self.layer_items[index]
        rect = self.layer_rects[index]
        item = QGraphicsPixmapItem()
        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.clear_placeholder(index)
        self.set_layer_pixmap(item, self.layer_pixmap(self.layers[index], rect, False), rect, True)
        item.setZValue(old.zValue())
        self.removeItem(old)
        self.addItem(item)
        self.layer_items[index] = item

    def set_layer_rect(self, index: int, rect: Rect) -> None:
        """Ruch warstwy (F5, D30): nowy prostokąt bez zmiany obrazu ani z-order."""
        scene_rect = self.scene_rect(rect)
        self.layer_rects[index] = scene_rect
        item = self.layer_items[index]
        if isinstance(item, QGraphicsVideoItem):
            item.setPos(scene_rect.topLeft())
            item.setSize(scene_rect.size())
        else:
            self.set_layer_pixmap(
                item, item.pixmap(), scene_rect, isinstance(self.layers[index], ClipLayer)
            )
        if index in self.placeholders:
            placeholder = self.placeholders[index]
            self.set_layer_pixmap(placeholder, placeholder.pixmap(), scene_rect, True)
        self.layer_moved.emit(index)

    def scene_rect(self, rect: Rect) -> QRectF:
        """Prostokąt w ułamkach kadru → współrzędne sceny (piksele prezentacji)."""
        scene = self.sceneRect()
        x, y, w, h = rect
        return QRectF(x * scene.width(), y * scene.height(), w * scene.width(), h * scene.height())

    def show_placeholder(self, index: int) -> None:
        """Zastępnik nowego wejścia, również przy zachowaniu elementu wideo."""
        if index in self.placeholders:
            return
        rect = self.layer_rects[index]
        item = QGraphicsPixmapItem()
        item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.set_layer_pixmap(item, self.layer_pixmap(self.layers[index], rect, False), rect, True)
        item.setZValue(index + 1.5)
        self.addItem(item)
        self.placeholders[index] = item

    def clear_placeholder(self, index: int) -> None:
        """Pierwsza nowa klatka zastępuje miniaturę, ale nie zmienia bariery."""
        if item := self.placeholders.pop(index, None):
            self.removeItem(item)

    @staticmethod
    def set_layer_pixmap(
        item: QGraphicsPixmapItem, pixmap: QPixmap, rect: QRectF, keep_aspect: bool = False
    ) -> None:
        """Dopasowanie klipu z marginesami albo klatki live do pełnego kontenera."""
        item.setPixmap(pixmap)
        item.setPos(rect.topLeft())
        if pixmap.width() and pixmap.height():
            sx, sy = rect.width() / pixmap.width(), rect.height() / pixmap.height()
            if keep_aspect:
                sx = sy = min(sx, sy)
            item.setTransform(QTransform.fromScale(sx, sy))
            item.setPos(
                rect.x() + (rect.width() - pixmap.width() * sx) / 2,
                rect.y() + (rect.height() - pixmap.height() * sy) / 2,
            )


class SlideView(QGraphicsView):
    """Widok kompozycji dopasowany do rozmiaru, czarne pasy poza kadrem."""

    layer_clicked = Signal(int)
    """Klik w widoku: indeks warstwy live pod kursorem albo -1 poza warstwami (F4)."""
    layer_double_clicked = Signal(int)
    pointer_dragged = Signal(QPointF, bool, str, bool)
    """Punkt sceny, Shift, przycisk i Alt; capture kończy się na release (D47)."""
    pointer_released = Signal()
    wheel_turned = Signal(float, int)
    """Obrót kółka w ząbkach (120 jednostek Qt = 1), dodatni od użytkownika."""

    def __init__(
        self,
        composition: SlideComposition,
        aspect_ratio_mode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio,
    ) -> None:
        super().__init__(composition)
        self.aspect_ratio_mode = aspect_ratio_mode
        self.pointer_button = None
        # Sygnały zamiast filtra zdarzeń całej aplikacji: filtr wołał Pythona dla każdego
        # zdarzenia każdego żyjącego widoku i dławił ścieżkę GUI (test_gui_path_keeps_up...).
        app = QApplication.instance()
        app.applicationStateChanged.connect(self._application_state_changed)
        app.focusWindowChanged.connect(self._focus_window_changed)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor("black"))
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # Bez fokusu: QAbstractScrollArea zjadłby strzałki na przewijanie, a klawisze
        # mają trafiać do okna (Player.keyPressEvent, Info.keyPressEvent).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _application_state_changed(self, state) -> None:
        if state != Qt.ApplicationState.ApplicationActive:
            self._cancel_capture()

    def _focus_window_changed(self, window) -> None:
        # Fokus na własnym oknie (np. klik po Info) nie przerywa gestu, który właśnie startuje.
        if window is None or window is not self.window().windowHandle():
            self._cancel_capture()

    def _cancel_capture(self) -> None:
        """Utrata aktywności lub fokusu kończy capture bez nowego press (D47)."""
        if self.pointer_button is not None:
            self.pointer_button = None
            self.pointer_released.emit()

    def layer_at(self, point) -> int:
        """Najwyższy kontener pod punktem; margines klipu blokuje klik do live poniżej."""
        scene_point = self.mapToScene(point)
        for index in reversed(range(len(self.scene().layer_rects))):
            if self.scene().layer_rects[index].contains(scene_point):
                return index
        return -1

    def mousePressEvent(self, event) -> None:
        buttons = {
            Qt.MouseButton.LeftButton: "left",
            Qt.MouseButton.MiddleButton: "middle",
            Qt.MouseButton.RightButton: "right",
        }
        self.pointer_button = (
            buttons.get(event.button()) if event.buttons() == event.button() else None
        )
        if self.pointer_button:
            self.layer_clicked.emit(self.layer_at(event.position().toPoint()))
            self.pointer_dragged.emit(
                self.mapToScene(event.position().toPoint()),
                bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier),
                self.pointer_button,
                bool(event.modifiers() & Qt.KeyboardModifier.AltModifier),
            )
        else:
            self.pointer_released.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            self.layer_double_clicked.emit(self.layer_at(event.position().toPoint()))
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        buttons = {
            "left": Qt.MouseButton.LeftButton,
            "middle": Qt.MouseButton.MiddleButton,
            "right": Qt.MouseButton.RightButton,
        }
        if self.pointer_button and event.buttons() == buttons[self.pointer_button]:
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            self.pointer_dragged.emit(
                self.mapToScene(event.position().toPoint()), shift, self.pointer_button, alt
            )
        elif self.pointer_button:
            self.pointer_button = None
            self.pointer_released.emit()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.pointer_button = None
        self.pointer_released.emit()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        # Bez przewijania widoku: kadr zawsze mieści się w oknie (fitInView).
        point = event.position().toPoint()
        if self.layer_at(point) >= 0:
            self.wheel_turned.emit(
                event.angleDelta().y() / 120
                if event.angleDelta().y()
                else event.pixelDelta().y() / 40,
                self.layer_at(point),
            )
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), self.aspect_ratio_mode)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.fitInView(self.sceneRect(), self.aspect_ratio_mode)
