from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QListView, QSlider, QSizePolicy, QStyle, QStyledItemDelegate, QWidget

from logo_core import is_dialog_confirm_key, slider_position_from_value, slider_value_from_position
from preview import ui_font
from styles import SITE_STYLE, THEME, TITLE_FONT_FAMILY, make_font


class RoundedComboDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        bg_rect = option.rect.adjusted(7, 3, -7, -3)
        radius = 12

        if selected:
            gradient = QLinearGradient(bg_rect.left(), bg_rect.top(), bg_rect.right(), bg_rect.top())
            gradient.setColorAt(0.0, QColor("#0756c8"))
            gradient.setColorAt(0.62, QColor("#0587f2"))
            gradient.setColorAt(1.0, QColor("#00aeea"))
            painter.setBrush(gradient)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bg_rect, radius, radius)
        elif hovered:
            painter.setBrush(QColor("#0d5fcf"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bg_rect, radius, radius)

        font = QFont(option.font)
        font.setWeight(QFont.Bold if selected else QFont.Medium)
        painter.setFont(font)
        painter.setPen(QColor("#ffffff"))

        view = self.parent()
        alignment = Qt.AlignCenter if view and view.property("centerOptions") else (Qt.AlignVCenter | Qt.AlignLeft)
        text_rect = option.rect.adjusted(16, 0, -16, 0)
        painter.drawText(text_rect, alignment, str(index.data(Qt.DisplayRole)))
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width(), 42)


class MaterialComboBox(QComboBox):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.setObjectName("materialCombo")
        self.setProperty("open", False)
        self.setMinimumHeight(46)
        self.setCursor(Qt.PointingHandCursor)
        self.setEditable(False)
        self.setMaxVisibleItems(6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFont(make_font(12, bold=True))
        self.view().setFont(make_font(12, bold=True))
        self.view().setVerticalScrollMode(QListView.ScrollPerPixel)
        self.view().setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view().setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view().setSpacing(1)
        self.view().setItemDelegate(RoundedComboDelegate(self.view()))
        self.addItems(list(values))

    def refresh_style(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def wheelEvent(self, event):
        event.ignore()

    def hide_popup_scrollers(self, popup):
        for child in popup.findChildren(QWidget):
            if child.metaObject().className() == "QComboBoxPrivateScroller":
                child.hide()
                child.setFixedHeight(0)
                child.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def showPopup(self):
        self.setProperty("open", True)
        self.refresh_style()
        view = self.view()
        view.setFixedWidth(self.width())
        view.setMaximumHeight(252)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        super().showPopup()
        popup = view.window()
        popup.setFixedWidth(self.width())
        self.hide_popup_scrollers(popup)
        QTimer.singleShot(0, lambda popup=popup: self.hide_popup_scrollers(popup))
        QTimer.singleShot(120, lambda popup=popup: self.hide_popup_scrollers(popup))
        anchor = self.mapToGlobal(QPoint(0, self.height() + 4))
        final_geometry = popup.geometry()
        final_geometry = QRect(anchor.x(), anchor.y(), self.width(), min(final_geometry.height(), 252))
        popup.setGeometry(final_geometry)
        start_geometry = QRect(final_geometry.x(), final_geometry.y(), final_geometry.width(), 8)
        popup.setGeometry(start_geometry)
        popup.setWindowOpacity(0.0)
        fade = QPropertyAnimation(popup, b"windowOpacity", popup)
        fade.setDuration(130)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        grow = QPropertyAnimation(popup, b"geometry", popup)
        grow.setDuration(150)
        grow.setStartValue(start_geometry)
        grow.setEndValue(final_geometry)
        grow.setEasingCurve(QEasingCurve.OutCubic)
        popup._fade_animation = fade
        popup._grow_animation = grow
        fade.start()
        grow.start()

    def hidePopup(self):
        super().hidePopup()
        self.setProperty("open", False)
        self.refresh_style()


class FriendlySlider(QSlider):
    HANDLE_GRAB_WIDTH = 32

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setTracking(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.drag_offset = 0.0

    def usable_width(self):
        return max(1, self.width() - 1)

    def handle_center_x(self):
        return slider_position_from_value(
            self.value(),
            self.minimum(),
            self.maximum(),
            self.usable_width(),
            self.invertedAppearance(),
        )

    def is_on_handle(self, x):
        half_width = self.HANDLE_GRAB_WIDTH / 2
        return abs(float(x) - self.handle_center_x()) <= half_width

    def set_value_from_event(self, event, use_drag_offset=False):
        x = event.position().x()
        if use_drag_offset:
            x -= self.drag_offset
        value = slider_value_from_position(
            x,
            self.usable_width(),
            self.minimum(),
            self.maximum(),
            self.invertedAppearance(),
        )
        self.setValue(value)

    def mousePressEvent(self, event):
        if self.orientation() != Qt.Horizontal or self.width() <= 0:
            return super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            if self.property("wheelAdjust"):
                self.setFocus(Qt.MouseFocusReason)
            self.setSliderDown(True)
            if self.is_on_handle(event.position().x()):
                self.drag_offset = event.position().x() - self.handle_center_x()
            else:
                self.drag_offset = 0.0
                self.set_value_from_event(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.orientation() == Qt.Horizontal and self.isSliderDown() and event.buttons() & Qt.LeftButton:
            self.set_value_from_event(event, use_drag_offset=True)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.orientation() == Qt.Horizontal and event.button() == Qt.LeftButton:
            self.set_value_from_event(event, use_drag_offset=True)
            self.setSliderDown(False)
            self.drag_offset = 0.0
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self.property("wheelAdjust"):
            delta = event.angleDelta().y() or event.pixelDelta().y()
            if delta:
                step = self.singleStep() or 1
                self.setValue(self.value() + (step if delta > 0 else -step))
                event.accept()
                return
        event.ignore()


class ShortcutConfirmDialog(QDialog):
    def __init__(self, confirm_keys=None, parent=None):
        super().__init__(parent)
        self.confirm_keys = set(confirm_keys or ())

    def keyPressEvent(self, event):
        if is_dialog_confirm_key(event.key(), self.confirm_keys):
            self.accept()
            event.accept()
            return
        super().keyPressEvent(event)


class LiveHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0
        self.setFixedHeight(38)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(80)

    def tick(self):
        self.phase = (self.phase + 1) % 12
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setFont(make_font(17, family=TITLE_FONT_FAMILY))
        radius = 5 + (2 if self.phase < 6 else 0)
        painter.setBrush(QColor("#ff3158" if self.phase < 6 else "#94152b"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(8, 14 - radius // 2, radius * 2, radius * 2)
        painter.setPen(QColor(THEME["cyan"]))
        painter.drawText(30, 25, "មើលរូបផ្ទាល់")


class PreviewLabel(QLabel):
    clicked = Signal(str)
    hovered = Signal(str)
    left = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hitboxes = {}
        self.source_pixmap = QPixmap()
        self.display_rect = QRect()
        self.zoom_source_rect = QRect()
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self.is_panning = False
        self.last_pan_pos = QPointF()
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(640, 380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("previewLabel")

    def set_preview_pixmap(self, pixmap):
        self.source_pixmap = pixmap
        self.setText("")
        self.refresh_scaled_pixmap()

    def set_zoom_rect(self, rect):
        x, y, width, height = rect
        self.zoom_source_rect = QRect(int(x), int(y), int(width), int(height))

    def clear_preview(self, text):
        self.hitboxes = {}
        self.source_pixmap = QPixmap()
        self.display_rect = QRect()
        self.zoom_source_rect = QRect()
        self.reset_zoom()
        QLabel.setPixmap(self, QPixmap())
        self.setText(text)

    def reset_zoom(self):
        self.zoom_factor = 1.0
        self.pan_offset = QPointF(0, 0)
        self.is_panning = False
        self.last_pan_pos = QPointF()

    def is_zoomed(self):
        return self.zoom_factor > 1.01

    def clamp_pan(self, scaled_size):
        available = self.contentsRect().size()
        max_x = max(0.0, (scaled_size.width() - available.width()) / 2)
        max_y = max(0.0, (scaled_size.height() - available.height()) / 2)
        self.pan_offset.setX(max(-max_x, min(max_x, self.pan_offset.x())))
        self.pan_offset.setY(max(-max_y, min(max_y, self.pan_offset.y())))

    def refresh_scaled_pixmap(self):
        if self.source_pixmap.isNull():
            return
        available = self.contentsRect().size()
        zoom_source = self.source_pixmap
        if self.is_zoomed() and not self.zoom_source_rect.isNull():
            zoom_source = self.source_pixmap.copy(self.zoom_source_rect)
        fit = zoom_source.scaled(available, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        scaled_size = QSize(
            max(1, int(round(fit.width() * self.zoom_factor))),
            max(1, int(round(fit.height() * self.zoom_factor))),
        )
        if not self.is_zoomed():
            self.pan_offset = QPointF(0, 0)
        self.clamp_pan(scaled_size)
        scaled = zoom_source.scaled(scaled_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        canvas = QPixmap(available)
        canvas.fill(Qt.transparent)
        x = (available.width() - scaled.width()) // 2 + int(round(self.pan_offset.x()))
        y = (available.height() - scaled.height()) // 2 + int(round(self.pan_offset.y()))
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(x, y, scaled)
        painter.end()
        self.display_rect = QRect(x, y, scaled.width(), scaled.height())
        QLabel.setPixmap(self, canvas)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_scaled_pixmap()

    def event_position(self, event):
        if self.display_rect.isNull() or self.source_pixmap.isNull():
            return -1, -1
        local_x = event.position().x() - self.display_rect.x()
        local_y = event.position().y() - self.display_rect.y()
        if local_x < 0 or local_y < 0 or local_x > self.display_rect.width() or local_y > self.display_rect.height():
            return -1, -1
        scale_x = self.source_pixmap.width() / max(1, self.display_rect.width())
        scale_y = self.source_pixmap.height() / max(1, self.display_rect.height())
        return local_x * scale_x, local_y * scale_y

    def action_at(self, x, y):
        if self.is_zoomed():
            return ""
        for action, rect in self.hitboxes.items():
            x1, y1, x2, y2 = rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                return action
        return ""

    def mousePressEvent(self, event):
        action = self.action_at(*self.event_position(event))
        if action:
            self.clicked.emit(action)
            return
        if self.is_zoomed() and self.event_position(event) != (-1, -1):
            self.is_panning = True
            self.last_pan_pos = event.position()
            self.setCursor(QCursor(Qt.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        if self.is_panning:
            delta = event.position() - self.last_pan_pos
            self.pan_offset += delta
            self.last_pan_pos = event.position()
            self.refresh_scaled_pixmap()
            return
        action = self.action_at(*self.event_position(event))
        self.setCursor(QCursor(Qt.PointingHandCursor if action else Qt.ArrowCursor))
        self.hovered.emit(action)

    def mouseReleaseEvent(self, event):
        self.is_panning = False
        self.setCursor(QCursor(Qt.ArrowCursor))

    def wheelEvent(self, event):
        pixel_delta = event.pixelDelta()
        angle_delta = event.angleDelta()
        zoom_delta = pixel_delta.y() if not pixel_delta.isNull() else angle_delta.y()
        if zoom_delta == 0 and pixel_delta.x() == 0 and angle_delta.x() == 0:
            event.ignore()
            return
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if zoom_delta > 0 else 1 / 1.15
            self.zoom_factor = max(1.0, min(4.0, self.zoom_factor * factor))
            if not self.is_zoomed():
                self.pan_offset = QPointF(0, 0)
            self.refresh_scaled_pixmap()
            event.accept()
            return
        if self.is_zoomed():
            if not pixel_delta.isNull():
                pan_delta = QPointF(pixel_delta.x(), pixel_delta.y())
            else:
                pan_delta = QPointF(angle_delta.x() / 2, angle_delta.y() / 2)
                if event.modifiers() & Qt.ShiftModifier and angle_delta.x() == 0:
                    pan_delta = QPointF(angle_delta.y() / 2, 0)
            self.pan_offset += pan_delta
            self.refresh_scaled_pixmap()
            event.accept()
            return
        event.ignore()

    def leaveEvent(self, event):
        self.is_panning = False
        self.setCursor(QCursor(Qt.ArrowCursor))
        self.left.emit()


class DropOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropOverlay")
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(7, 17, 31, 178))
        card = QRect(int(self.width() * 0.08), int(self.height() * 0.31), int(self.width() * 0.84), int(self.height() * 0.38))
        painter.setPen(QPen(QColor(THEME["cyan"]), 2))
        painter.setBrush(QColor(13, 27, 47, 220))
        painter.drawRoundedRect(card, 28, 28)
        painter.setPen(QColor(THEME["cyan"]))
        painter.setFont(make_font(29, family=TITLE_FONT_FAMILY))
        painter.drawText(card.adjusted(0, 40, 0, -90), Qt.AlignCenter, "ទម្លាក់រូបភាពនៅទីនេះ")
        painter.setPen(QColor(THEME["text"]))
        painter.setFont(make_font(15, bold=True))
        painter.drawText(card.adjusted(0, 110, 0, -35), Qt.AlignCenter, "ទម្លាក់Folderរូបភាព ឬ រូបភាព ដើម្បីជ្រើសរើសរូបភាពសម្រាប់កែប្រែ")
