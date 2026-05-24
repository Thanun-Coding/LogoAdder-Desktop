from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QListView, QSlider, QSizePolicy, QStyle, QStyledItemDelegate, QWidget

from logo_core import crop_settings_from_box, is_dialog_confirm_key, slider_position_from_value, slider_value_from_position
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
    cropChangeStarted = Signal()
    cropChanged = Signal(dict)

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
        self.crop_edit_enabled = False
        self.crop_image_rect = QRect()
        self.crop_rect = QRect()
        self.crop_drag_action = ""
        self.crop_drag_start_pos = QPointF()
        self.crop_drag_start_rect = QRect()
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

    def set_crop_editor(self, enabled, image_rect=None, crop=None):
        self.crop_edit_enabled = bool(enabled)
        if image_rect:
            x, y, width, height = image_rect
            self.crop_image_rect = QRect(int(x), int(y), int(width), int(height))
        else:
            self.crop_image_rect = QRect()
        self.crop_rect = self.crop_rect_from_settings(crop or {}) if self.crop_edit_enabled else QRect()
        self.crop_drag_action = ""
        self.refresh_scaled_pixmap()

    def crop_rect_from_settings(self, crop):
        if self.crop_image_rect.isNull():
            return QRect()
        left_pct = int(crop.get("left", 0))
        top_pct = int(crop.get("top", 0))
        right_pct = int(crop.get("right", 0))
        bottom_pct = int(crop.get("bottom", 0))
        x = self.crop_image_rect.x() + round(self.crop_image_rect.width() * left_pct / 100)
        y = self.crop_image_rect.y() + round(self.crop_image_rect.height() * top_pct / 100)
        right = self.crop_image_rect.right() + 1 - round(self.crop_image_rect.width() * right_pct / 100)
        bottom = self.crop_image_rect.bottom() + 1 - round(self.crop_image_rect.height() * bottom_pct / 100)
        return self.clamped_crop_rect(QRect(x, y, max(1, right - x), max(1, bottom - y)))

    def crop_settings_from_rect(self, rect):
        if self.crop_image_rect.isNull():
            return {"left": 0, "top": 0, "right": 0, "bottom": 0}
        return crop_settings_from_box(
            (self.crop_image_rect.width(), self.crop_image_rect.height()),
            (
                rect.x() - self.crop_image_rect.x(),
                rect.y() - self.crop_image_rect.y(),
                rect.x() + rect.width() - self.crop_image_rect.x(),
                rect.y() + rect.height() - self.crop_image_rect.y(),
            ),
        )

    def clear_preview(self, text):
        self.hitboxes = {}
        self.source_pixmap = QPixmap()
        self.display_rect = QRect()
        self.zoom_source_rect = QRect()
        self.set_crop_editor(False)
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
        self.display_rect = QRect(x, y, scaled.width(), scaled.height())
        self.draw_crop_overlay(painter)
        painter.end()
        QLabel.setPixmap(self, canvas)

    def source_to_display_rect(self, source_rect):
        if self.display_rect.isNull() or self.source_pixmap.isNull() or source_rect.isNull():
            return QRect()
        sx = self.display_rect.width() / max(1, self.source_pixmap.width())
        sy = self.display_rect.height() / max(1, self.source_pixmap.height())
        return QRect(
            self.display_rect.x() + round(source_rect.x() * sx),
            self.display_rect.y() + round(source_rect.y() * sy),
            max(1, round(source_rect.width() * sx)),
            max(1, round(source_rect.height() * sy)),
        )

    def draw_crop_overlay(self, painter):
        if not self.crop_edit_enabled or self.is_zoomed() or self.crop_image_rect.isNull() or self.crop_rect.isNull():
            return
        image_rect = self.source_to_display_rect(self.crop_image_rect)
        crop_rect = self.source_to_display_rect(self.crop_rect)
        if image_rect.isNull() or crop_rect.isNull():
            return
        painter.save()
        overlay = QColor(0, 0, 0, 125)
        painter.fillRect(QRect(image_rect.left(), image_rect.top(), image_rect.width(), max(0, crop_rect.top() - image_rect.top())), overlay)
        painter.fillRect(QRect(image_rect.left(), crop_rect.bottom() + 1, image_rect.width(), max(0, image_rect.bottom() - crop_rect.bottom())), overlay)
        painter.fillRect(QRect(image_rect.left(), crop_rect.top(), max(0, crop_rect.left() - image_rect.left()), crop_rect.height()), overlay)
        painter.fillRect(QRect(crop_rect.right() + 1, crop_rect.top(), max(0, image_rect.right() - crop_rect.right()), crop_rect.height()), overlay)
        painter.setPen(QPen(QColor("#47dcff"), 2))
        painter.drawRect(crop_rect)
        painter.setBrush(QColor("#47dcff"))
        painter.setPen(QPen(QColor("#06152d"), 1))
        for handle in self.crop_handle_rects(crop_rect).values():
            painter.drawRect(handle)
        painter.restore()

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

    def display_point_to_source(self, point):
        if self.display_rect.isNull() or self.source_pixmap.isNull():
            return QPointF(-1, -1)
        if self.crop_edit_enabled and not self.crop_image_rect.isNull():
            crop_display_rect = self.source_to_display_rect(self.crop_image_rect)
            if not crop_display_rect.isNull():
                local_x = point.x() - crop_display_rect.x()
                local_y = point.y() - crop_display_rect.y()
                scale_x = self.crop_image_rect.width() / max(1, crop_display_rect.width())
                scale_y = self.crop_image_rect.height() / max(1, crop_display_rect.height())
                return QPointF(self.crop_image_rect.x() + (local_x * scale_x), self.crop_image_rect.y() + (local_y * scale_y))
        local_x = point.x() - self.display_rect.x()
        local_y = point.y() - self.display_rect.y()
        scale_x = self.source_pixmap.width() / max(1, self.display_rect.width())
        scale_y = self.source_pixmap.height() / max(1, self.display_rect.height())
        return QPointF(local_x * scale_x, local_y * scale_y)

    def crop_handle_rects(self, display_crop_rect):
        size = 14
        half = size // 2
        cx = display_crop_rect.center().x()
        cy = display_crop_rect.center().y()
        left = display_crop_rect.left()
        right = display_crop_rect.right()
        top = display_crop_rect.top()
        bottom = display_crop_rect.bottom()
        return {
            "top_left": QRect(left - half, top - half, size, size),
            "top": QRect(cx - half, top - half, size, size),
            "top_right": QRect(right - half, top - half, size, size),
            "right": QRect(right - half, cy - half, size, size),
            "bottom_right": QRect(right - half, bottom - half, size, size),
            "bottom": QRect(cx - half, bottom - half, size, size),
            "bottom_left": QRect(left - half, bottom - half, size, size),
            "left": QRect(left - half, cy - half, size, size),
        }

    def crop_action_at(self, point):
        if not self.crop_edit_enabled or self.is_zoomed() or self.crop_rect.isNull():
            return ""
        display_crop = self.source_to_display_rect(self.crop_rect)
        if display_crop.isNull():
            return ""
        for action, rect in self.crop_handle_rects(display_crop).items():
            if rect.contains(point.toPoint()):
                return action
        hit = 8
        point_i = point.toPoint()
        expanded = display_crop.adjusted(-hit, -hit, hit, hit)
        if expanded.contains(point_i):
            near_left = abs(point.x() - display_crop.left()) <= hit
            near_right = abs(point.x() - display_crop.right()) <= hit
            near_top = abs(point.y() - display_crop.top()) <= hit
            near_bottom = abs(point.y() - display_crop.bottom()) <= hit
            if near_left and near_top:
                return "top_left"
            if near_right and near_top:
                return "top_right"
            if near_left and near_bottom:
                return "bottom_left"
            if near_right and near_bottom:
                return "bottom_right"
            if near_left:
                return "left"
            if near_right:
                return "right"
            if near_top:
                return "top"
            if near_bottom:
                return "bottom"
        if display_crop.contains(point.toPoint()):
            return "move"
        return ""

    def crop_cursor_for_action(self, action):
        return {
            "move": Qt.SizeAllCursor,
            "left": Qt.SizeHorCursor,
            "right": Qt.SizeHorCursor,
            "top": Qt.SizeVerCursor,
            "bottom": Qt.SizeVerCursor,
            "top_left": Qt.SizeFDiagCursor,
            "bottom_right": Qt.SizeFDiagCursor,
            "top_right": Qt.SizeBDiagCursor,
            "bottom_left": Qt.SizeBDiagCursor,
        }.get(action, Qt.ArrowCursor)

    def clamped_crop_rect(self, rect):
        if self.crop_image_rect.isNull():
            return QRect()
        min_size = 12
        left = max(self.crop_image_rect.left(), min(rect.left(), self.crop_image_rect.right() - min_size + 1))
        top = max(self.crop_image_rect.top(), min(rect.top(), self.crop_image_rect.bottom() - min_size + 1))
        right = min(self.crop_image_rect.right() + 1, max(rect.left() + min_size, rect.left() + rect.width()))
        bottom = min(self.crop_image_rect.bottom() + 1, max(rect.top() + min_size, rect.top() + rect.height()))
        if right - left < min_size:
            left = max(self.crop_image_rect.left(), right - min_size)
        if bottom - top < min_size:
            top = max(self.crop_image_rect.top(), bottom - min_size)
        return QRect(left, top, right - left, bottom - top)

    def adjusted_crop_rect(self, source_point):
        rect = QRect(self.crop_drag_start_rect)
        dx = round(source_point.x() - self.crop_drag_start_pos.x())
        dy = round(source_point.y() - self.crop_drag_start_pos.y())
        action = self.crop_drag_action
        if action == "move":
            moved = QRect(rect)
            moved.translate(dx, dy)
            if moved.left() < self.crop_image_rect.left():
                moved.moveLeft(self.crop_image_rect.left())
            if moved.top() < self.crop_image_rect.top():
                moved.moveTop(self.crop_image_rect.top())
            if moved.right() > self.crop_image_rect.right():
                moved.moveRight(self.crop_image_rect.right())
            if moved.bottom() > self.crop_image_rect.bottom():
                moved.moveBottom(self.crop_image_rect.bottom())
            return moved
        left, top, right, bottom = rect.left(), rect.top(), rect.right() + 1, rect.bottom() + 1
        if "left" in action:
            left += dx
        if "right" in action:
            right += dx
        if "top" in action:
            top += dy
        if "bottom" in action:
            bottom += dy
        return self.clamped_crop_rect(QRect(left, top, right - left, bottom - top))

    def action_at(self, x, y):
        if self.is_zoomed():
            return ""
        for action, rect in self.hitboxes.items():
            x1, y1, x2, y2 = rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                return action
        return ""

    def mousePressEvent(self, event):
        crop_action = self.crop_action_at(event.position())
        if crop_action:
            self.crop_drag_action = crop_action
            self.crop_drag_start_pos = self.display_point_to_source(event.position())
            self.crop_drag_start_rect = QRect(self.crop_rect)
            self.cropChangeStarted.emit()
            self.setCursor(QCursor(self.crop_cursor_for_action(crop_action)))
            event.accept()
            return
        action = self.action_at(*self.event_position(event))
        if action:
            self.clicked.emit(action)
            return
        if self.is_zoomed() and self.event_position(event) != (-1, -1):
            self.is_panning = True
            self.last_pan_pos = event.position()
            self.setCursor(QCursor(Qt.ClosedHandCursor))

    def mouseMoveEvent(self, event):
        if self.crop_drag_action:
            self.crop_rect = self.adjusted_crop_rect(self.display_point_to_source(event.position()))
            self.cropChanged.emit(self.crop_settings_from_rect(self.crop_rect))
            self.refresh_scaled_pixmap()
            event.accept()
            return
        if self.is_panning:
            delta = event.position() - self.last_pan_pos
            self.pan_offset += delta
            self.last_pan_pos = event.position()
            self.refresh_scaled_pixmap()
            return
        action = self.action_at(*self.event_position(event))
        crop_action = self.crop_action_at(event.position())
        if crop_action:
            cursor = self.crop_cursor_for_action(crop_action)
        else:
            cursor = Qt.PointingHandCursor if action else Qt.ArrowCursor
        self.setCursor(QCursor(cursor))
        self.hovered.emit(action)

    def mouseReleaseEvent(self, event):
        if self.crop_drag_action:
            self.crop_drag_action = ""
            self.setCursor(QCursor(Qt.ArrowCursor))
            event.accept()
            return
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
