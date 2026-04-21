import os
import queue
import subprocess
import sys
import threading
import webbrowser
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

os.environ.setdefault("QT_LOGGING_RULES", "qt.text.font.db.warning=false")

import logo_core as core
from logo_core import (
    DEFAULT_OUTPUT_SETTINGS,
    KHMER_POSITIONS,
    OUTPUT_FORMATS,
    POSITION_VALUES,
    build_output_path,
    calculate_logo_size,
    calculate_position,
    is_supported_image,
    list_images,
    load_config,
    normalize_output_settings,
    normalize_position,
    preset_from_settings,
    resource_path,
    save_config,
    save_output_image,
    scale_margins,
    should_preserve_alpha,
    unique_output_path,
    write_error_summary,
)

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ModuleNotFoundError:
    Image = None
    ImageDraw = None
    ImageFilter = None
    ImageFont = None

try:
    from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRect, QSize, Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QCursor, QDragEnterEvent, QDropEvent, QFont, QIcon, QImage, QLinearGradient, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDialog,
        QFileDialog,
        QFrame,
        QGraphicsDropShadowEffect,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListView,
        QMainWindow,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSlider,
        QSizePolicy,
        QSpacerItem,
        QStyle,
        QStyleFactory,
        QStyledItemDelegate,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError:
    QApplication = None

try:
    from qt_material import apply_stylesheet
except ModuleNotFoundError:
    apply_stylesheet = None


APP_TITLE = "កម្មវិធីដាក់Logoលើរូបភាព - Thanun"
TITLE_LOGO_FILE = "Title Logo.png"
WINDOW_SIZE = (1260, 900)
PREVIEW_SIZE = (840, 500)

THEME = {
    "bg": "#050b1d",
    "sidebar": "#07162d",
    "sidebar_dark": "#041024",
    "panel": "#091b35",
    "panel_soft": "#102f56",
    "surface": "#06152c",
    "stroke": "#1f6fa6",
    "blue": "#0587f2",
    "blue_light": "#37c7ff",
    "blue_dark": "#0756c8",
    "cyan": "#47dcff",
    "success": "#35d898",
    "success_hover": "#25bb80",
    "danger": "#ff5f86",
    "danger_hover": "#db466c",
    "warning": "#eddd53",
    "text": "#f4f8ff",
    "muted": "#a8c7de",
}

FONT_STACK = '"Noto Sans Khmer", "Khmer OS Battambang", "Leelawadee UI", "Segoe UI", "Roboto", "Arial"'

SITE_STYLE = {
    "bg": "#09090b",
    "panel": "#18181b",
    "accent": "#3b82f6",
    "border": "#27272a",
    "text": "#f4f4f5",
    "cyan": "#00e5ff",
}


def require_gui_dependencies():
    missing = []
    if QApplication is None:
        missing.append("PySide6")
    if Image is None:
        missing.append("pillow")
    if missing:
        raise RuntimeError(f"Missing required package(s): {', '.join(missing)}")


def open_rgba_image(path):
    if Image is None:
        raise RuntimeError("Pillow is required to process images. Install it with: pip install pillow")
    return Image.open(path).convert("RGBA")


def contained_preview_size(image_size, bounds=PREVIEW_SIZE):
    width, height = image_size
    bound_width, bound_height = bounds
    if width <= 0 or height <= 0:
        return (1, 1)
    ratio = min(bound_width / width, bound_height / height, 1.0)
    return (max(1, int(round(width * ratio))), max(1, int(round(height * ratio))))


def ui_font(size, bold=False):
    if ImageFont is None:
        return None
    font_name = "arialbd.ttf" if bold else "arial.ttf"
    try:
        return ImageFont.truetype(font_name, size)
    except Exception:
        return ImageFont.load_default()


def compose_logo(base_image, logo_image, position, size_percent, opacity, margins):
    logo_width, logo_height = calculate_logo_size(
        base_image.width,
        logo_image.width,
        logo_image.height,
        size_percent,
    )
    resized_logo = logo_image.resize((logo_width, logo_height), Image.LANCZOS)
    alpha = resized_logo.split()[3].point(lambda p: int(p * core.clamp(float(opacity), 0.0, 1.0)))
    resized_logo.putalpha(alpha)

    x, y = calculate_position(base_image.size, resized_logo.size, position, margins)
    output = base_image.copy()
    output.paste(resized_logo, (x, y), resized_logo)
    return output


def pil_to_pixmap(image):
    image = image.convert("RGBA")
    data = image.tobytes("raw", "RGBA")
    qimage = QImage(data, image.width, image.height, image.width * 4, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


def make_font(size, bold=False, family="Noto Sans Khmer"):
    font = QFont(family, size)
    if bold:
        font.setWeight(QFont.Bold)
    return font


def add_shadow(widget, blur=30, y_offset=10, alpha=90):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(shadow)


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
        self.setFont(make_font(14, bold=True))
        self.view().setFont(make_font(14, bold=True))
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
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setTracking(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)

    def mousePressEvent(self, event):
        if self.orientation() != Qt.Horizontal or self.width() <= 0:
            return super().mousePressEvent(event)
        ratio = core.clamp(event.position().x() / max(1, self.width()), 0.0, 1.0)
        if self.invertedAppearance():
            ratio = 1.0 - ratio
        value = self.minimum() + round(ratio * (self.maximum() - self.minimum()))
        self.setValue(value)
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        event.ignore()


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
        painter.setFont(make_font(17, bold=True))
        radius = 5 + (2 if self.phase < 6 else 0)
        painter.setBrush(QColor("#ff3158" if self.phase < 6 else "#94152b"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(8, 14 - radius // 2, radius * 2, radius * 2)
        painter.setPen(QColor(THEME["cyan"]))
        painter.drawText(30, 25, "LIVE PREVIEW")


class PreviewLabel(QLabel):
    clicked = Signal(str)
    hovered = Signal(str)
    left = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hitboxes = {}
        self.source_pixmap = QPixmap()
        self.display_rect = QRect()
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

    def clear_preview(self, text):
        self.hitboxes = {}
        self.source_pixmap = QPixmap()
        self.display_rect = QRect()
        QLabel.setPixmap(self, QPixmap())
        self.setText(text)

    def refresh_scaled_pixmap(self):
        if self.source_pixmap.isNull():
            return
        available = self.contentsRect().size()
        scaled = self.source_pixmap.scaled(available, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        self.display_rect = QRect(x, y, scaled.width(), scaled.height())
        QLabel.setPixmap(self, scaled)

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
        for action, rect in self.hitboxes.items():
            x1, y1, x2, y2 = rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                return action
        return ""

    def mousePressEvent(self, event):
        action = self.action_at(*self.event_position(event))
        if action:
            self.clicked.emit(action)

    def mouseMoveEvent(self, event):
        action = self.action_at(*self.event_position(event))
        self.setCursor(QCursor(Qt.PointingHandCursor if action else Qt.ArrowCursor))
        self.hovered.emit(action)

    def leaveEvent(self, event):
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
        painter.setFont(make_font(29, bold=True))
        painter.drawText(card.adjusted(0, 40, 0, -90), Qt.AlignCenter, "DROP PHOTOS HERE")
        painter.setPen(QColor(THEME["text"]))
        painter.setFont(make_font(15, bold=True))
        painter.drawText(card.adjusted(0, 110, 0, -35), Qt.AlignCenter, "Drop a folder or photo file to choose images for editing")


class LogoAdderUltra(QMainWindow):
    def __init__(self):
        require_gui_dependencies()
        super().__init__()
        self.config = load_config()
        self.config["folder_path"] = ""
        self.config["logo_path"] = ""
        self.config["output"] = DEFAULT_OUTPUT_SETTINGS.copy()
        self.current_preview_index = 0
        self.image_list = []
        self.inputs = {}
        self.is_updating_from_slider = False
        self.processing_thread = None
        self.processing_queue = queue.Queue()
        self.cancel_requested = threading.Event()
        self.last_output_dir = None
        self.is_processing = False
        self.controls_to_disable = []
        self.preview_source_cache = {"path": None, "image": None}
        self.preview_logo_cache = {"path": None, "image": None}
        self.preview_hover_action = ""
        self.preview_nav_hitboxes = {}

        self.setup_window()
        self.create_layout()
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_processing_queue)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.update_live_preview)

    def setup_window(self):
        self.setWindowTitle(APP_TITLE)
        self.setFixedSize(*WINDOW_SIZE)
        QApplication.instance().setFont(make_font(10))
        icon_path = resource_path("myicon.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setAcceptDrops(True)

    def create_layout(self):
        root = QWidget(self)
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(350)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(18, 18, 4, 18)
        sidebar_layout.setSpacing(12)
        layout.addWidget(self.sidebar)

        self.create_sidebar(sidebar_layout)
        self.create_main_area(layout)
        self.drop_overlay = DropOverlay(root)
        self.drop_overlay.setGeometry(root.rect())

    def create_sidebar(self, layout):
        header = QFrame()
        header.setObjectName("sidebarHeader")
        add_shadow(header, blur=24, y_offset=8, alpha=76)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 16, 12, 16)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        title_logo = resource_path(TITLE_LOGO_FILE)
        if title_logo.exists():
            logo.setPixmap(QPixmap(str(title_logo)).scaled(285, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("កម្មវិធីដាក់Logoលើរូបភាព")
            logo.setFont(make_font(22, bold=True))
        header_layout.addWidget(logo)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("sidebarScroll")
        scroll_content = QWidget()
        self.sidebar_body = scroll_content
        self.sidebar_layout = QVBoxLayout(scroll_content)
        self.sidebar_layout.setContentsMargins(4, 8, 14, 8)
        self.sidebar_layout.setSpacing(10)
        scroll.setWidget(scroll_content)
        self.sidebar_scroll = scroll
        layout.addWidget(scroll, 1)

        footer = QFrame()
        footer.setObjectName("sidebarFooter")
        add_shadow(footer, blur=22, y_offset=8, alpha=72)
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(10, 12, 10, 12)
        by = QLabel("បង្កើតឡើងដោយ")
        by.setAlignment(Qt.AlignCenter)
        by.setObjectName("mutedLabel")
        self.creator_label = QLabel("THANUN")
        self.creator_label.setAlignment(Qt.AlignCenter)
        self.creator_label.setObjectName("creatorLabel")
        self.creator_label.setCursor(Qt.PointingHandCursor)
        self.creator_label.mousePressEvent = lambda _event: webbrowser.open("https://www.facebook.com/thanun2903/")
        footer_layout.addWidget(by)
        footer_layout.addWidget(self.creator_label)
        layout.addWidget(footer)

        self.populate_sidebar()

    def populate_sidebar(self):
        self.add_section("រូបភាព")
        source_row = QHBoxLayout()
        self.btn_browse_photos = self.create_button("Browse Photo", self.browse_photos)
        self.btn_browse_folder = self.create_button("Browse Folder", self.browse_folder)
        source_row.addWidget(self.btn_browse_photos)
        source_row.addWidget(self.btn_browse_folder)
        self.sidebar_layout.addLayout(source_row)
        self.folder_path_lbl = self.create_hint_label("មិនទាន់មានរូបភាព!")

        self.add_section("Logo")
        self.btn_browse_logo = self.create_button("ជ្រើសរើស Logo", self.browse_logo)
        self.sidebar_layout.addWidget(self.btn_browse_logo)
        self.logo_path_lbl = self.create_hint_label(self.truncate_path(self.config.get("logo_path") or "មិនទាន់មាន Logo!"))

        self.add_section("ការកំណត់ទុក")
        self.preset_menu = self.create_preset_combo(self.preset_names(), self.apply_selected_preset)
        self.preset_menu.blockSignals(True)
        self.preset_menu.setCurrentText(self.config.get("selected_preset", ""))
        self.preset_menu.blockSignals(False)
        self.sidebar_layout.addWidget(self.preset_menu)
        preset_row = QHBoxLayout()
        self.btn_save_preset = self.create_button("រក្សាទុក", self.save_preset_dialog)
        self.btn_delete_preset = self.create_button("លុប", self.delete_selected_preset, danger=True)
        preset_row.addWidget(self.btn_save_preset)
        preset_row.addWidget(self.btn_delete_preset)
        self.sidebar_layout.addLayout(preset_row)

        self.create_input_group("ទំហំ Logo (%)", "logo_size", 5, 100, self.config["logo_size"])
        self.create_input_group("កម្រិតច្បាស់ Logo (%)", "opacity", 0, 100, self.config["opacity"])

        self.add_section("ទីតាំង Logo")
        self.margin_widgets = {}
        self.pos_menu = self.create_combo(POSITION_VALUES, self.update_margin_visibility)
        self.pos_menu.setCurrentText(normalize_position(self.config.get("position")))
        self.sidebar_layout.addWidget(self.pos_menu)
        self.controls_to_disable.append(self.pos_menu)

        for key, label in (
            ("m_top", "Margin លើ"),
            ("m_bottom", "Margin ក្រោម"),
            ("m_left", "Margin ឆ្វេង"),
            ("m_right", "Margin ស្តាំ"),
        ):
            self.create_input_group(f"{label} (px)", key, 0, 500, self.config[key], store_margin=True)

        self.update_margin_visibility()
        self.create_output_settings()
        self.apply_initial_preset_selection()
        self.sidebar_layout.addItem(QSpacerItem(1, 18, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def create_main_area(self, parent_layout):
        self.main_area = QFrame()
        self.main_area.setObjectName("mainArea")
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(28, 22, 28, 22)
        main_layout.setSpacing(12)
        parent_layout.addWidget(self.main_area, 1)

        self.live_header = LiveHeader()
        main_layout.addWidget(self.live_header)

        self.preview_container = QFrame()
        self.preview_container.setObjectName("previewContainer")
        add_shadow(self.preview_container, blur=36, y_offset=14, alpha=105)
        preview_layout = QVBoxLayout(self.preview_container)
        preview_layout.setContentsMargins(22, 18, 22, 18)
        self.preview_canvas = PreviewLabel()
        self.preview_canvas.clicked.connect(self.handle_preview_action)
        self.preview_canvas.hovered.connect(self.handle_preview_hover)
        self.preview_canvas.left.connect(self.handle_preview_leave)
        preview_layout.addWidget(self.preview_canvas)
        main_layout.addWidget(self.preview_container, 1)

        status_row = QHBoxLayout()
        self.status_label = QLabel("លទ្ធផល")
        self.status_label.setObjectName("statusLabel")
        self.count_label = QLabel("0 / 0")
        self.count_label.setObjectName("mutedLabel")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        status_row.addWidget(self.count_label)
        main_layout.addLayout(status_row)

        self.log_box = QPlainTextEdit()
        self.log_box.setObjectName("terminal")
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(150)
        self.log_box.setMaximumHeight(150)
        add_shadow(self.log_box, blur=20, y_offset=6, alpha=65)
        main_layout.addWidget(self.log_box)

        self.progress = QProgressBar()
        self.progress.setObjectName("progressBar")
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        main_layout.addWidget(self.progress)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.btn_open_folder = self.create_button("បើក Folder លទ្ធផល", self.open_output)
        self.btn_open_folder.setObjectName("openResultButton")
        self.btn_open_folder.setEnabled(False)
        self.btn_start = self.create_button("ចាប់ផ្តើមដំណើរការ", self.process_images, success=True)
        self.btn_start.setObjectName("startProcessButton")
        actions.addWidget(self.btn_start, 3)
        actions.addWidget(self.btn_open_folder, 1)
        main_layout.addLayout(actions)
        self.update_live_preview()

    def add_section(self, text):
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        self.sidebar_layout.addWidget(label)

    def create_hint_label(self, text):
        label = QLabel(text)
        label.setObjectName("hintLabel")
        label.setWordWrap(True)
        self.sidebar_layout.addWidget(label)
        return label

    def create_button(self, text, callback, danger=False, success=False):
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.NoFocus)
        if danger:
            button.setProperty("variant", "danger")
        elif success:
            button.setProperty("variant", "success")
        else:
            button.setProperty("variant", "primary")
        button.clicked.connect(callback)
        self.controls_to_disable.append(button)
        return button

    def create_combo(self, values, callback):
        combo = MaterialComboBox(values)
        combo.currentTextChanged.connect(callback)
        if hasattr(self, "sidebar_scroll"):
            self.sidebar_scroll.verticalScrollBar().valueChanged.connect(combo.hidePopup)
        self.controls_to_disable.append(combo)
        return combo

    def create_preset_combo(self, values, callback):
        combo = self.create_combo(values, callback)
        combo.view().setTextElideMode(Qt.ElideNone)
        return combo

    def create_output_settings(self):
        output = normalize_output_settings(self.config.get("output"))
        self.add_section("ជ្រើសរើសប្រភេទរូបភាព")
        self.output_format_menu = self.create_combo(OUTPUT_FORMATS, lambda _value: self.on_output_setting_change())
        self.output_format_menu.setCurrentText(output["format"])
        self.sidebar_layout.addWidget(self.output_format_menu)

        self.create_input_group("គុណភាពរូបភាព", "output_quality", 1, 100, output["quality"])
        self.output_suffix_entry = self.create_text_entry("កំណត់ឈ្មោះរូបភាព", output["name_prefix"])
        self.output_folder_entry = self.create_text_entry("កំណត់ឈ្មោះFolder", output["folder_name"])

    def create_text_entry(self, label_text, value):
        frame = QFrame()
        frame.setObjectName("plainInputGroup")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        entry = QLineEdit(value)
        entry.setObjectName("textEntry")
        entry.textChanged.connect(self.on_output_setting_change)
        layout.addWidget(label)
        layout.addWidget(entry)
        self.sidebar_layout.addWidget(frame)
        self.controls_to_disable.append(entry)
        return entry

    def create_input_group(self, label_text, config_key, min_val, max_val, default, store_margin=False):
        frame = QFrame()
        frame.setObjectName("inputGroup")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        entry = QLineEdit()
        entry.setObjectName("numberEntry")
        entry.setAlignment(Qt.AlignCenter)
        entry.setFixedWidth(62)
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(entry)

        value = default
        if config_key == "opacity" and value <= 1.0:
            value = int(value * 100)
        value = int(core.clamp(float(value), min_val, max_val))
        slider = FriendlySlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(value)
        entry.setText(str(value))

        def on_slider(new_value):
            self.is_updating_from_slider = True
            entry.setText(str(int(new_value)))
            self.is_updating_from_slider = False
            self.on_slider_move()

        def on_entry(text):
            if self.is_updating_from_slider or not text.strip():
                return
            try:
                new_value = int(text)
            except ValueError:
                return
            if min_val <= new_value <= max_val:
                slider.setValue(new_value)
                self.on_slider_move()

        slider.valueChanged.connect(on_slider)
        entry.textChanged.connect(on_entry)
        layout.addLayout(row)
        layout.addWidget(slider)
        self.sidebar_layout.addWidget(frame)
        self.inputs[config_key] = {"slider": slider, "entry": entry, "frame": frame}
        self.controls_to_disable.extend([entry, slider])
        if store_margin:
            self.margin_widgets[config_key] = frame
        return self.inputs[config_key]

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_overlay.setGeometry(self.centralWidget().rect())
            self.drop_overlay.show()
            self.drop_overlay.raise_()

    def dragLeaveEvent(self, event):
        self.drop_overlay.hide()

    def dropEvent(self, event: QDropEvent):
        self.drop_overlay.hide()
        urls = event.mimeData().urls()
        if not urls:
            return
        path = Path(urls[0].toLocalFile())
        if path.is_dir():
            self.set_folder(path)
        elif is_supported_image(path.name):
            self.set_folder(path.parent)
            if path.name in self.image_list:
                self.current_preview_index = self.image_list.index(path.name)
                self.update_live_preview()
        else:
            self.themed_message_dialog("ឯកសារមិនគាំទ្រ", "ទម្លាក់Folderរូបភាព ឬរូបភាពដើម្បីកែ! ជ្រើសរើស Logo ដោយប្រើប៊ូតុងជ្រើសរើស Logo។")

    def current_margins(self):
        return {
            "top": self.inputs["m_top"]["slider"].value(),
            "bottom": self.inputs["m_bottom"]["slider"].value(),
            "left": self.inputs["m_left"]["slider"].value(),
            "right": self.inputs["m_right"]["slider"].value(),
        }

    def current_output_settings(self):
        return normalize_output_settings(
            {
                "format": self.output_format_menu.currentText(),
                "quality": self.inputs["output_quality"]["slider"].value(),
                "name_prefix": self.output_suffix_entry.text(),
                "folder_name": self.output_folder_entry.text(),
            }
        )

    def current_config(self):
        return {
            "logo_path": self.config.get("logo_path", ""),
            "folder_path": self.config.get("folder_path", ""),
            "position": self.pos_menu.currentText(),
            "logo_size": self.inputs["logo_size"]["slider"].value(),
            "opacity": self.inputs["opacity"]["slider"].value() / 100,
            "m_top": self.inputs["m_top"]["slider"].value(),
            "m_bottom": self.inputs["m_bottom"]["slider"].value(),
            "m_left": self.inputs["m_left"]["slider"].value(),
            "m_right": self.inputs["m_right"]["slider"].value(),
            "output": self.current_output_settings(),
            "presets": self.config.get("presets", {}),
            "selected_preset": self.preset_menu.currentText(),
        }

    def preset_names(self):
        names = sorted(self.config.get("presets", {}).keys())
        return names if names else ["មិនទាន់មានការកំណត់ទុក"]

    def refresh_preset_menu(self):
        names = self.preset_names()
        current = self.preset_menu.currentText()
        self.preset_menu.blockSignals(True)
        self.preset_menu.clear()
        self.preset_menu.addItems(names)
        self.preset_menu.blockSignals(False)
        if current in names:
            self.preset_menu.setCurrentText(current)
        else:
            self.preset_menu.setCurrentText(names[0])

    def persist_presets(self):
        save_config(
            {
                "presets": self.config.get("presets", {}),
                "selected_preset": self.config.get("selected_preset", ""),
            }
        )

    def apply_selected_preset(self, name):
        preset = self.config.get("presets", {}).get(name)
        if not preset:
            return
        self.config["selected_preset"] = name
        self.persist_presets()
        self.pos_menu.setCurrentText(normalize_position(preset.get("position")))
        self.set_input_value("logo_size", int(preset.get("logo_size", 10)))
        self.set_input_value("opacity", int(float(preset.get("opacity", 1.0)) * 100))
        for key in ("m_top", "m_bottom", "m_left", "m_right"):
            self.set_input_value(key, int(preset.get(key, 10)))
        output = normalize_output_settings(preset.get("output"))
        self.output_format_menu.setCurrentText(output["format"])
        self.set_input_value("output_quality", output["quality"])
        self.output_suffix_entry.setText(output["name_prefix"])
        self.output_folder_entry.setText(output["folder_name"])
        logo_path = preset.get("logo_path", "")
        if logo_path and Path(logo_path).exists():
            self.config["logo_path"] = logo_path
            self.logo_path_lbl.setText(self.truncate_path(logo_path))
        self.update_margin_visibility()

    def apply_initial_preset_selection(self):
        selected = self.config.get("selected_preset", "")
        if selected not in self.config.get("presets", {}):
            return
        self.preset_menu.setCurrentText(selected)
        self.apply_selected_preset(selected)

    def closeEvent(self, event):
        if hasattr(self, "preset_menu"):
            selected = self.preset_menu.currentText()
            if selected in self.config.get("presets", {}):
                self.config["selected_preset"] = selected
            elif self.config.get("selected_preset") not in self.config.get("presets", {}):
                self.config["selected_preset"] = ""
            self.persist_presets()
        super().closeEvent(event)

    def set_input_value(self, key, value):
        self.inputs[key]["slider"].setValue(value)
        self.inputs[key]["entry"].setText(str(value))

    def save_preset_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("រក្សាទុកPreset")
        dialog.setObjectName("materialDialog")
        dialog.setFixedSize(360, 205)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)
        title = QLabel("រក្សាទុកPreset")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("ដាក់ឈ្មោះសម្រាប់Presetនេះ!")
        subtitle.setObjectName("hintLabel")
        subtitle.setAlignment(Qt.AlignCenter)
        name_entry = QLineEdit()
        name_entry.setObjectName("textEntry")
        row = QHBoxLayout()
        save_btn = self.create_button("រក្សាទុក", lambda: None, success=True)
        close_btn = self.create_button("បិទ", dialog.reject, danger=True)
        row.addWidget(save_btn)
        row.addWidget(close_btn)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(name_entry)
        layout.addSpacing(12)
        layout.addLayout(row)
        layout.setContentsMargins(20, 18, 20, 24)

        def save_preset():
            name = name_entry.text().strip()
            if not name:
                name_entry.setProperty("error", True)
                self.refresh_style(name_entry)
                return
            self.config["presets"][name] = preset_from_settings(self.current_config())
            self.refresh_preset_menu()
            self.preset_menu.setCurrentText(name)
            self.persist_presets()
            self.write_log(f"> បានរក្សាទុកPreset: {name}")
            dialog.accept()

        save_btn.clicked.disconnect()
        save_btn.clicked.connect(save_preset)
        for button in (save_btn, close_btn):
            button.setProperty("dialogButton", True)
            self.refresh_style(button)
        name_entry.returnPressed.connect(save_preset)
        dialog.exec()

    def themed_message_dialog(self, title_text, body_text, confirm_text="យល់ព្រម", danger=False):
        dialog = QDialog(self)
        dialog.setWindowTitle(title_text)
        dialog.setObjectName("materialDialog")
        dialog.setFixedSize(360, 165)
        icon_path = resource_path("myicon.ico")
        if icon_path.exists():
            dialog.setWindowIcon(QIcon(str(icon_path)))

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(5)
        title = QLabel(title_text)
        title.setObjectName("errorTitle" if "បញ្ហា" in title_text else "dialogTitle")
        title.setAlignment(Qt.AlignCenter)
        body = QLabel(body_text)
        body.setObjectName("hintLabel")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)
        button = QPushButton(confirm_text)
        button.setProperty("variant", "danger" if danger else "primary")
        button.setProperty("dialogButton", True)
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.NoFocus)
        button.clicked.connect(dialog.accept)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(button)
        dialog.exec()

    def confirm_dialog(self, title_text, body_text, confirm_text="លុប", cancel_text="បិទ"):
        dialog = QDialog(self)
        dialog.setWindowTitle(title_text)
        dialog.setObjectName("materialDialog")
        dialog.setFixedSize(360, 165)
        icon_path = resource_path("myicon.ico")
        if icon_path.exists():
            dialog.setWindowIcon(QIcon(str(icon_path)))

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(5)
        title = QLabel(title_text)
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignCenter)
        body = QLabel(body_text)
        body.setObjectName("hintLabel")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)
        row = QHBoxLayout()
        row.setSpacing(8)
        confirm_btn = QPushButton(confirm_text)
        confirm_btn.setProperty("variant", "danger")
        confirm_btn.setProperty("dialogButton", True)
        confirm_btn.setProperty("deleteAction", True)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setFocusPolicy(Qt.NoFocus)
        cancel_btn = QPushButton(cancel_text)
        cancel_btn.setProperty("variant", "danger")
        cancel_btn.setProperty("dialogButton", True)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFocusPolicy(Qt.NoFocus)
        confirm_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        row.addWidget(confirm_btn)
        row.addWidget(cancel_btn)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addLayout(row)
        return dialog.exec() == QDialog.Accepted

    def delete_selected_preset(self):
        name = self.preset_menu.currentText()
        if name not in self.config.get("presets", {}):
            return
        if not self.confirm_dialog("លុប Preset", f"លុប Preset '{name}' មែនទេ?", confirm_text="លុប", cancel_text="បិទ"):
            return
        del self.config["presets"][name]
        self.refresh_preset_menu()
        self.persist_presets()
        self.write_log(f"> បានលុប Preset: {name}")

    def update_margin_visibility(self, choice=None):
        if not hasattr(self, "margin_widgets") or not all(key in self.inputs for key in ("m_top", "m_bottom", "m_left", "m_right")):
            return
        position = normalize_position(self.pos_menu.currentText())
        active = {
            KHMER_POSITIONS["top_left"]: {"m_top", "m_left"},
            KHMER_POSITIONS["top_right"]: {"m_top", "m_right"},
            KHMER_POSITIONS["bottom_left"]: {"m_bottom", "m_left"},
            KHMER_POSITIONS["bottom_right"]: {"m_bottom", "m_right"},
            KHMER_POSITIONS["center"]: set(),
        }[position]
        for key, widget in self.margin_widgets.items():
            widget.setVisible(key in active)
        if hasattr(self, "output_format_menu"):
            self.on_slider_move()

    def on_output_setting_change(self):
        if hasattr(self, "output_format_menu"):
            self.config.update(self.current_config())

    def on_slider_move(self, *_):
        if not hasattr(self, "pos_menu") or not hasattr(self, "output_format_menu"):
            return
        self.config.update(self.current_config())
        if hasattr(self, "preview_timer"):
            self.preview_timer.start(110)

    def write_log(self, text):
        self.log_box.appendPlainText(text)
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def clear_log(self):
        self.log_box.clear()

    def browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "ជ្រើសរើស Logo", "", "រូបភាព (*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.tif);;ឯកសារទាំងអស់ (*.*)")
        if path:
            self.set_logo(Path(path))

    def set_logo(self, path):
        try:
            with open_rgba_image(path):
                pass
        except Exception as error:
            self.themed_message_dialog("បញ្ហា Logo", f"មិនអាចបើក Logo បានទេ:\n{error}", danger=True)
            return
        self.config["logo_path"] = str(path)
        self.logo_path_lbl.setText(self.truncate_path(path))
        self.preview_logo_cache = {"path": None, "image": None}
        self.update_live_preview()

    def browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "ជ្រើសរើស Folder រូបភាព")
        if path:
            self.set_folder(Path(path))

    def browse_photos(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "ជ្រើសរើសរូបភាព", "", "រូបភាព (*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.tif);;ឯកសារទាំងអស់ (*.*)")
        if paths:
            self.set_photo_files([Path(path) for path in paths])

    def set_folder(self, path):
        files = list_images(path)
        if not files:
            self.themed_message_dialog("រកមិនឃើញរូបភាព", "មិនមានប្រភេទរូបភាពដែលគាំទ្រក្នុង Folder នេះទេ។")
            return
        self.image_list = files
        self.config["folder_path"] = str(path)
        self.folder_path_lbl.setText(f"{self.truncate_path(path)} ({len(files)} រូបភាព)")
        self.current_preview_index = 0
        self.preview_source_cache = {"path": None, "image": None}
        self.progress.setValue(0)
        self.count_label.setText(f"0 / {len(files)}")
        self.btn_open_folder.setEnabled(False)
        self.update_live_preview()

    def set_photo_files(self, paths):
        image_paths = [path for path in paths if is_supported_image(path.name)]
        if not image_paths:
            self.themed_message_dialog("រកមិនឃើញរូបភាព", "មិនមានរូបភាពដែលគាំទ្រសម្រាប់បើកទេ។")
            return
        parent = image_paths[0].parent
        image_paths = [path for path in image_paths if path.parent == parent]
        self.image_list = [path.name for path in image_paths]
        self.config["folder_path"] = str(parent)
        self.folder_path_lbl.setText(f"{len(self.image_list)} រូបភាពពី {self.truncate_path(parent)}")
        self.current_preview_index = 0
        self.preview_source_cache = {"path": None, "image": None}
        self.progress.setValue(0)
        self.count_label.setText(f"0 / {len(self.image_list)}")
        self.btn_open_folder.setEnabled(False)
        self.update_live_preview()

    def handle_preview_action(self, action):
        if action == "prev":
            self.prev_photo()
        elif action == "next":
            self.next_photo()

    def handle_preview_hover(self, action):
        if action != self.preview_hover_action:
            self.preview_hover_action = action
            if self.image_list:
                self.update_live_preview()

    def handle_preview_leave(self):
        if self.preview_hover_action:
            self.preview_hover_action = ""
            self.update_live_preview()

    def draw_preview_controls(self, canvas, count_text):
        draw = ImageDraw.Draw(canvas)
        button_size = 50
        center_y = PREVIEW_SIZE[1] // 2
        self.preview_nav_hitboxes = {
            "prev": (0, 0, int(PREVIEW_SIZE[0] * 0.3), PREVIEW_SIZE[1]),
            "next": (int(PREVIEW_SIZE[0] * 0.7), 0, PREVIEW_SIZE[0], PREVIEW_SIZE[1]),
        }
        self.preview_canvas.hitboxes = self.preview_nav_hitboxes

        left = (20, center_y - button_size // 2, 20 + button_size, center_y + button_size // 2)
        right = (PREVIEW_SIZE[0] - 20 - button_size, center_y - button_size // 2, PREVIEW_SIZE[0] - 20, center_y + button_size // 2)
        count_w, count_h = 94, 34
        count = ((PREVIEW_SIZE[0] - count_w) // 2, PREVIEW_SIZE[1] - count_h - 20, (PREVIEW_SIZE[0] + count_w) // 2, PREVIEW_SIZE[1] - 20)

        self.draw_nav_indicator(canvas, left, "<", self.preview_hover_action == "prev")
        self.draw_nav_indicator(canvas, right, ">", self.preview_hover_action == "next")
        self.draw_glass_rect(canvas, count, radius=17, blur_radius=5, fill=(10, 10, 12, 204), outline=(255, 255, 255, 26), shadow=True)
        count_font = ui_font(13, bold=True)
        self.draw_centered_text(draw, count, count_text, SITE_STYLE["cyan"], count_font, letter_spacing=2)

    def draw_nav_indicator(self, canvas, rect, arrow, hovered):
        if hovered:
            grow = 3
            rect = (rect[0] - grow, rect[1] - grow, rect[2] + grow, rect[3] + grow)
            fill = (0, 229, 255, 26)
            outline = (0, 229, 255, 153)
            text_fill = "#ffffff"
            shadow_fill = (0, 229, 255, 75)
        else:
            fill = (15, 15, 20, 102)
            outline = (0, 229, 255, 51)
            text_fill = SITE_STYLE["cyan"]
            shadow_fill = (0, 0, 0, 95)
        self.draw_glass_rect(canvas, rect, radius=14, blur_radius=8, fill=fill, outline=outline, shadow=True, shadow_fill=shadow_fill)
        draw = ImageDraw.Draw(canvas)
        arrow_font = ui_font(24, bold=True)
        self.draw_centered_text(draw, rect, arrow, text_fill, arrow_font, y_adjust=-1)

    def draw_glass_rect(self, canvas, rect, radius, blur_radius, fill, outline, shadow=False, shadow_fill=(0, 0, 0, 120)):
        rect = tuple(int(value) for value in rect)
        x1, y1, x2, y2 = rect
        if shadow:
            shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            shadow_draw.rounded_rectangle((x1, y1 + 4, x2, y2 + 4), radius=radius, fill=shadow_fill)
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(10))
            canvas.alpha_composite(shadow_layer)
        mask = Image.new("L", (x2 - x1, y2 - y1), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, x2 - x1 - 1, y2 - y1 - 1), radius=radius, fill=255)
        crop = canvas.crop((x1, y1, x2, y2)).filter(ImageFilter.GaussianBlur(blur_radius))
        tint = Image.new("RGBA", crop.size, fill)
        crop.alpha_composite(tint)
        canvas.paste(crop, (x1, y1), mask)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((x1, y1, x2 - 1, y2 - 1), radius=radius, outline=outline, width=1)

    def draw_centered_text(self, draw, rect, text, fill, font, y_adjust=0, letter_spacing=0):
        if letter_spacing:
            text_w = sum(draw.textlength(char, font=font) for char in text) + letter_spacing * max(len(text) - 1, 0)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_h = bbox[3] - bbox[1]
            x = rect[0] + (rect[2] - rect[0] - text_w) / 2
            y = rect[1] + (rect[3] - rect[1] - text_h) / 2 - bbox[1] + y_adjust
            for char in text:
                draw.text((x, y), char, fill=fill, font=font)
                x += draw.textlength(char, font=font) + letter_spacing
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = rect[0] + (rect[2] - rect[0] - text_w) / 2 - bbox[0]
        y = rect[1] + (rect[3] - rect[1] - text_h) / 2 - bbox[1] + y_adjust
        draw.text((x, y), text, fill=fill, font=font)

    def prev_photo(self):
        if self.image_list:
            self.current_preview_index = (self.current_preview_index - 1) % len(self.image_list)
            self.update_live_preview()

    def next_photo(self):
        if self.image_list:
            self.current_preview_index = (self.current_preview_index + 1) % len(self.image_list)
            self.update_live_preview()

    def truncate_path(self, path, length=46):
        text = str(path)
        return "..." + text[-length:] if len(text) > length + 3 else text

    def open_output(self):
        path = self.last_output_dir or (Path(self.config.get("folder_path", "")) / self.current_output_settings()["folder_name"])
        if path.exists():
            subprocess.Popen(["explorer", str(path.resolve())])

    def update_live_preview(self):
        logo_path = self.config.get("logo_path")
        folder_path = self.config.get("folder_path")
        has_images = bool(self.image_list and folder_path)
        if not has_images:
            self.preview_canvas.clear_preview("សូមជ្រើសរើសរូបភាព")
            return

        canvas = Image.new("RGBA", PREVIEW_SIZE, THEME["surface"])
        photo_path = Path(folder_path) / self.image_list[self.current_preview_index]
        try:
            if self.preview_source_cache["path"] != str(photo_path):
                self.preview_source_cache = {"path": str(photo_path), "image": open_rgba_image(photo_path)}
            original = self.preview_source_cache["image"]
            display = original.copy()
            display.thumbnail((PREVIEW_SIZE[0] - 16, PREVIEW_SIZE[1] - 16), Image.LANCZOS)
            preview = display
            if logo_path and Path(logo_path).exists():
                if self.preview_logo_cache["path"] != str(logo_path):
                    self.preview_logo_cache = {"path": str(logo_path), "image": open_rgba_image(logo_path)}
                preview = compose_logo(display, self.preview_logo_cache["image"], self.pos_menu.currentText(), self.inputs["logo_size"]["slider"].value(), self.inputs["opacity"]["slider"].value() / 100, self.current_margins())
            offset = ((PREVIEW_SIZE[0] - preview.width) // 2, (PREVIEW_SIZE[1] - preview.height) // 2)
            shadow = Image.new("RGBA", (preview.width + 26, preview.height + 26), (0, 0, 0, 0))
            draw = ImageDraw.Draw(shadow)
            draw.rectangle((13, 13, preview.width + 13, preview.height + 13), fill=(86, 204, 242, 95))
            shadow = shadow.filter(ImageFilter.GaussianBlur(12))
            canvas.alpha_composite(shadow, (offset[0] - 13, offset[1] - 13))
            canvas.paste(preview, offset)
            canvas_draw = ImageDraw.Draw(canvas)
            canvas_draw.rectangle((offset[0] - 2, offset[1] - 2, offset[0] + preview.width + 1, offset[1] + preview.height + 1), outline=(86, 204, 242, 235), width=2)
            count_text = f"{self.current_preview_index + 1} / {len(self.image_list)}"
            self.draw_preview_controls(canvas, count_text)
            self.count_label.setText(count_text)
        except Exception as error:
            self.preview_canvas.clear_preview(f"បញ្ហា Preview Screen:\n{error}")
            return
        self.preview_canvas.set_preview_pixmap(pil_to_pixmap(canvas))

    def set_processing_state(self, processing):
        self.is_processing = processing
        for control in self.controls_to_disable:
            control.setEnabled(not processing)
        self.btn_start.setEnabled(True)
        if processing:
            self.btn_start.setText("បោះបង់ដំណើរការ")
            self.btn_start.setProperty("variant", "danger")
            self.btn_start.clicked.disconnect()
            self.btn_start.clicked.connect(self.cancel_processing)
        else:
            self.btn_start.setText("ចាប់ផ្តើមដំណើរការ")
            self.btn_start.setProperty("variant", "success")
            try:
                self.btn_start.clicked.disconnect()
            except Exception:
                pass
            self.btn_start.clicked.connect(self.process_images)
        self.refresh_style(self.btn_start)

    def process_images(self):
        if self.is_processing:
            return
        folder = self.config.get("folder_path")
        logo_path = self.config.get("logo_path")
        if not folder or not Path(folder).exists() or not logo_path or not Path(logo_path).exists():
            self.themed_message_dialog("បញ្ហា", "សូមជ្រើសរើសFolderរូបភាព និង Logo!", danger=True)
            return
        files = self.image_list or list_images(folder)
        if not files:
            self.themed_message_dialog("រកមិនឃើញរូបភាព", "មិនមានរូបភាពសម្រាប់ដំណើរការទេ។")
            return
        settings = self.current_config()
        output_settings = normalize_output_settings(settings.get("output"))
        conflict_count = self.count_output_conflicts(folder, files, output_settings)
        conflict_policy = "overwrite"
        if conflict_count:
            conflict_policy = self.ask_output_conflict_policy(conflict_count)
            if conflict_policy is None:
                self.status_label.setText("បានបោះបង់: មានឯកសារឈ្មោះដូចគ្នា")
                return
        self.clear_log()
        self.progress.setValue(0)
        self.count_label.setText(f"0 / {len(files)}")
        self.status_label.setText("កំពុងចាប់ផ្តើមដំណើរការ......")
        self.btn_open_folder.setEnabled(False)
        self.cancel_requested.clear()
        self.config.update(settings)
        self.set_processing_state(True)
        self.processing_thread = threading.Thread(target=self.processing_worker, args=(folder, logo_path, files, settings, conflict_policy), daemon=True)
        self.processing_thread.start()
        self.poll_timer.start(100)

    def count_output_conflicts(self, folder, files, output_settings):
        return sum(1 for index, filename in enumerate(files, start=1) if build_output_path(folder, filename, output_settings, index).exists())

    def ask_output_conflict_policy(self, conflict_count):
        dialog = QDialog(self)
        dialog.setWindowTitle("ឯកសារមានរួចហើយ")
        dialog.setObjectName("materialDialog")
        dialog.setFixedSize(440, 235)
        icon_path = resource_path("myicon.ico")
        if icon_path.exists():
            dialog.setWindowIcon(QIcon(str(icon_path)))

        selected = {"policy": None}
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("រូបភាពមានរួចហើយ")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignCenter)
        body = QLabel(f"រកឃើញ {conflict_count} រូបភាពដែលអាចមានឈ្មោះជាន់គ្នា។\nជ្រើសរើសរបៀបដែលអ្នកចង់រក្សាទុកលទ្ធផល។")
        body.setObjectName("hintLabel")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)

        overwrite_btn = QPushButton("លុបរូបភាពដើម និងរក្សាទុកថ្មី")
        overwrite_btn.setProperty("variant", "danger")
        rename_btn = QPushButton("ប្តូរឈ្មោះថ្មី")
        rename_btn.setProperty("variant", "success")
        cancel_btn = QPushButton("បោះបង់")
        cancel_btn.setProperty("variant", "primary")
        for button in (overwrite_btn, rename_btn, cancel_btn):
            button.setCursor(Qt.PointingHandCursor)
            button.setFocusPolicy(Qt.NoFocus)
            button.setMinimumHeight(34)
            button.setProperty("conflictAction", True)
            button.setProperty("dialogButton", True)

        def choose(policy):
            selected["policy"] = policy
            dialog.accept()

        overwrite_btn.clicked.connect(lambda: choose("overwrite"))
        rename_btn.clicked.connect(lambda: choose("rename"))
        cancel_btn.clicked.connect(dialog.reject)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(overwrite_btn)
        action_row.addWidget(rename_btn)
        action_row.addWidget(cancel_btn)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addLayout(action_row)

        if dialog.exec() == QDialog.Accepted:
            return selected["policy"]
        return None

    def processing_worker(self, folder, logo_path, files, settings, conflict_policy="overwrite"):
        errors = []
        successes = 0
        output_settings = normalize_output_settings(settings.get("output"))
        output_dir = Path(folder) / output_settings["folder_name"]
        output_dir.mkdir(exist_ok=True)
        margin_settings = {"top": settings["m_top"], "bottom": settings["m_bottom"], "left": settings["m_left"], "right": settings["m_right"]}
        try:
            logo = open_rgba_image(logo_path)
        except Exception as error:
            self.processing_queue.put(("fatal", f"មិនអាចបើក Logo បានទេ: {error}"))
            return

        def process_one(index, filename):
            if self.cancel_requested.is_set():
                return "cancelled", index, filename, None
            input_path = Path(folder) / filename
            output_path = build_output_path(folder, filename, output_settings, index)
            if conflict_policy == "rename":
                output_path = unique_output_path(output_path)
            base = open_rgba_image(input_path)
            preview_size = contained_preview_size(base.size)
            margins = scale_margins(margin_settings, base.size, preview_size)
            output = compose_logo(base, logo, settings["position"], settings["logo_size"], settings["opacity"], margins)
            save_output_image(output, output_path, output_settings)
            return "success", index, filename, None

        total = len(files)
        completed = 0
        next_index = 0
        pending = {}
        max_workers = min(4, max(1, os.cpu_count() or 1), total)
        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            while (next_index < total or pending) and not self.cancel_requested.is_set():
                while next_index < total and len(pending) < max_workers and not self.cancel_requested.is_set():
                    file_index = next_index + 1
                    filename = files[next_index]
                    pending[executor.submit(process_one, file_index, filename)] = filename
                    next_index += 1
                if not pending:
                    break
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    filename = pending.pop(future)
                    completed += 1
                    try:
                        status, _index, processed_file, error = future.result()
                        if status == "cancelled":
                            continue
                        successes += 1
                        filename = processed_file
                    except Exception as error:
                        errors.append({"file": filename, "error": str(error)})
                        self.processing_queue.put(("error", filename, str(error)))
                    self.processing_queue.put(("progress", completed, total, filename))
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
        if self.cancel_requested.is_set():
            self.processing_queue.put(("cancelled", successes, errors, output_dir))
            return
        if errors:
            write_error_summary(output_dir, errors)
        self.processing_queue.put(("done", successes, errors, output_dir))

    def poll_processing_queue(self):
        try:
            while True:
                message = self.processing_queue.get_nowait()
                kind = message[0]
                if kind == "progress":
                    _, index, total, filename = message
                    self.progress.setValue(int(index / total * 1000))
                    self.count_label.setText(f"{index} / {total}")
                    self.status_label.setText(f"កំពុងដំណើរការ: {filename}")
                    self.write_log(f"> {filename}")
                elif kind == "error":
                    _, filename, error = message
                    self.write_log(f"! {filename} - {error}")
                elif kind == "fatal":
                    self.finish_processing(0, [{"file": "Logo", "error": message[1]}], None, cancelled=False)
                    self.themed_message_dialog("បញ្ហា Logo", message[1], danger=True)
                    return
                elif kind == "cancelled":
                    _, successes, errors, output_dir = message
                    self.finish_processing(successes, errors, output_dir, cancelled=True)
                    return
                elif kind == "done":
                    _, successes, errors, output_dir = message
                    self.finish_processing(successes, errors, output_dir, cancelled=False)
                    return
        except queue.Empty:
            pass
        if not self.is_processing:
            self.poll_timer.stop()

    def finish_processing(self, successes, errors, output_dir, cancelled=False):
        self.last_output_dir = output_dir
        self.set_processing_state(False)
        self.btn_open_folder.setEnabled(bool(output_dir))
        status = "បានបោះបង់" if cancelled else "រួចរាល់"
        self.status_label.setText(f"{status}: ជោគជ័យ {successes}, បរាជ័យ {len(errors)}")
        self.write_log(f"> {status}: ជោគជ័យ {successes}, បរាជ័យ {len(errors)}")
        if errors:
            self.write_log("> បានរក្សាទុកសេចក្តីសង្ខេបបញ្ហាទៅ failed_files.txt")
        self.show_finish_dialog(status, successes, len(errors), output_dir)

    def show_finish_dialog(self, status, successes, failures, output_dir):
        dialog = QDialog(self)
        dialog.setWindowTitle(status)
        dialog.setObjectName("materialDialog")
        dialog.setFixedSize(380, 205)
        dialog.setMaximumSize(400, 230)
        icon_path = resource_path("myicon.ico")
        if icon_path.exists():
            dialog.setWindowIcon(QIcon(str(icon_path)))

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(9)

        title = QLabel("ដំណើរការបានបញ្ចប់")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignCenter)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(18)
        success_label = QLabel(f"ជោគជ័យ {successes}")
        success_label.setObjectName("successText")
        success_label.setAlignment(Qt.AlignCenter)
        failure_label = QLabel(f"បរាជ័យ {failures}")
        failure_label.setObjectName("failureText")
        failure_label.setAlignment(Qt.AlignCenter)
        summary_row.addWidget(success_label)
        summary_row.addWidget(failure_label)

        row = QHBoxLayout()
        row.setSpacing(10)
        open_btn = QPushButton("បើកFolderលទ្ធផល")
        open_btn.setProperty("variant", "success")
        open_btn.setProperty("dialogButton", True)
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setFocusPolicy(Qt.NoFocus)
        open_btn.setEnabled(bool(output_dir))
        close_btn = QPushButton("បិទ")
        close_btn.setProperty("variant", "danger")
        close_btn.setProperty("dialogButton", True)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFocusPolicy(Qt.NoFocus)
        open_btn.clicked.connect(lambda: (dialog.accept(), self.open_output()))
        close_btn.clicked.connect(dialog.accept)
        row.addWidget(open_btn, 2)
        row.addWidget(close_btn, 1)

        layout.addWidget(title)
        layout.addLayout(summary_row)
        layout.addLayout(row)
        dialog.exec()

    def cancel_processing(self):
        if self.is_processing:
            self.cancel_requested.set()
            self.status_label.setText("កំពុងបោះបង់.....")
            self.btn_start.setEnabled(False)
            self.btn_start.setText("កំពុងបោះបង់.....")

    def refresh_style(self, widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)


def material_qss():
    app_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #040a1d, stop:0.52 #071c3d, stop:1 #052a4c)"
    sidebar_gradient = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #061735, stop:0.55 #071f40, stop:1 #041024)"
    panel_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0a2448, stop:0.55 #071a35, stop:1 #071426)"
    button_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0587f2, stop:0.55 #00b7ff, stop:1 #35d898)"
    button_hover_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1399ff, stop:0.55 #37c7ff, stop:1 #57e5ad)"
    dropdown_gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0756c8, stop:0.62 #0587f2, stop:1 #00aeea)"
    return f"""
    QWidget#appRoot, QMainWindow {{
        background: {app_gradient};
        color: {THEME["text"]};
        font-family: {FONT_STACK};
        font-size: 13px;
    }}
    QFrame#sidebar {{
        background: {sidebar_gradient};
    }}
    QFrame#sidebarHeader, QFrame#sidebarFooter {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #082650, stop:1 #06152d);
        border: 1px solid rgba(71, 220, 255, 0.18);
        border-radius: 18px;
    }}
    QFrame#mainArea {{
        background: transparent;
    }}
    QFrame#previewContainer {{
        background: {panel_gradient};
        border: 1px solid rgba(71, 220, 255, 0.35);
        border-radius: 20px;
    }}
    QLabel#previewLabel {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #061932, stop:1 #041024);
        border: 1px solid rgba(71, 220, 255, 0.34);
        border-radius: 18px;
        color: {THEME["muted"]};
        font-size: 16px;
        font-weight: 700;
    }}
    QLabel#sectionLabel {{
        color: {THEME["text"]};
        font-size: 16px;
        font-weight: 700;
        margin-top: 8px;
    }}
    QLabel#fieldLabel {{
        color: {THEME["text"]};
        font-size: 14px;
    }}
    QLabel#hintLabel, QLabel#mutedLabel {{
        color: {THEME["muted"]};
        font-size: 13px;
    }}
    QLabel#statusLabel, QLabel#creatorLabel {{
        color: {THEME["cyan"]};
        font-weight: 700;
    }}
    QLabel#creatorLabel {{
        font-size: 27px;
        letter-spacing: 1px;
    }}
    QScrollArea#sidebarScroll {{
        border: none;
        background: transparent;
        padding-right: 0px;
    }}
    QScrollArea#sidebarScroll > QWidget > QWidget {{
        background: transparent;
    }}
    QFrame#inputGroup, QFrame#plainInputGroup {{
        background: transparent;
        border: none;
    }}
    QPushButton {{
        min-height: 40px;
        border-radius: 12px;
        border: 1px solid rgba(71, 220, 255, 0.28);
        padding: 8px 16px;
        color: #f4f8ff;
        font-weight: 800;
        background: {button_gradient};
    }}
    QPushButton:hover {{
        background: {button_hover_gradient};
        border: 1px solid rgba(237, 221, 83, 0.44);
    }}
    QPushButton:pressed {{
        background: {THEME["blue_dark"]};
        padding-top: 9px;
        padding-bottom: 7px;
    }}
    QPushButton:focus {{
        outline: none;
        background: {button_gradient};
    }}
    QPushButton[variant="danger"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff5f86, stop:1 #f093fb);
        color: #ffffff;
    }}
    QPushButton[variant="danger"]:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff789a, stop:1 #ffb2ec);
        color: #ffffff;
    }}
    QPushButton[variant="danger"]:focus {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff5f86, stop:1 #f093fb);
        color: #ffffff;
    }}
    QPushButton[deleteAction="true"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff1744, stop:0.55 #c51162, stop:1 #7b1fa2);
        color: #ffffff;
    }}
    QPushButton[deleteAction="true"]:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff4569, stop:0.55 #e21a79, stop:1 #9c27b0);
        color: #ffffff;
    }}
    QPushButton[deleteAction="true"]:focus {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff1744, stop:0.55 #c51162, stop:1 #7b1fa2);
        color: #ffffff;
    }}
    QPushButton[variant="success"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1ec8ff, stop:1 #35d898);
        color: #03101a;
    }}
    QPushButton[variant="success"]:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #47dcff, stop:1 #57e5ad);
        color: #04121b;
    }}
    QPushButton[variant="success"]:focus {{
        background: {THEME["success"]};
        color: #04121b;
    }}
    QPushButton:disabled {{
        background: {THEME["panel_soft"]};
        color: {THEME["muted"]};
    }}
    QPushButton#startProcessButton {{
        min-height: 46px;
        font-size: 15px;
        border-radius: 14px;
    }}
    QPushButton#openResultButton {{
        min-height: 42px;
        font-size: 13px;
    }}
    QPushButton[dialogButton="true"] {{
        min-height: 34px;
        max-height: 36px;
        border-radius: 10px;
        padding: 5px 12px;
        font-size: 12px;
    }}
    QPushButton[conflictAction="true"] {{
        border-radius: 11px;
        padding: 6px 10px;
        font-size: 12px;
    }}
    QLineEdit {{
        min-height: 34px;
        border-radius: 10px;
        border: 1px solid rgba(71, 220, 255, 0.28);
        background: rgba(6, 21, 44, 0.86);
        color: {THEME["text"]};
        padding: 4px 10px;
        selection-background-color: {THEME["blue"]};
    }}
    QLineEdit:focus {{
        border: 1px solid #eddd53;
    }}
    QLineEdit[error="true"] {{
        border: 1px solid {THEME["danger"]};
    }}
    QLineEdit#numberEntry {{
        qproperty-alignment: AlignCenter;
    }}
    QSlider {{
        background: transparent;
        border: none;
    }}
    QSlider::groove:horizontal {{
        height: 4px;
        background: rgba(71, 220, 255, 0.16);
        border: none;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: #47dcff;
        border: 3px solid {THEME["sidebar"]};
        width: 18px;
        height: 18px;
        margin: -7px 0;
        border-radius: 9px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {THEME["cyan"]};
        border: 3px solid {THEME["sidebar"]};
    }}
    QSlider::handle:horizontal:pressed {{
        background: #ffffff;
        border: 3px solid {THEME["cyan"]};
    }}
    QSlider::sub-page:horizontal {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b7ff, stop:1 #57c785);
        border: none;
        border-radius: 2px;
    }}
    QSlider::add-page:horizontal {{
        background: transparent;
        border: none;
        border-radius: 2px;
    }}
    QComboBox#materialCombo {{
        min-height: 46px;
        border-radius: 13px;
        padding-left: 16px;
        padding-right: 38px;
        color: {THEME["text"]};
        background: {dropdown_gradient};
        border: 1px solid rgba(71, 220, 255, 0.32);
        font-weight: 700;
    }}
    QComboBox#materialCombo:hover {{
        background: {button_hover_gradient};
        border: 1px solid rgba(237, 221, 83, 0.42);
    }}
    QComboBox#materialCombo::drop-down {{
        width: 38px;
        border: none;
        background: transparent;
    }}
    QComboBox#materialCombo::down-arrow {{
        image: none;
        width: 0;
        height: 0;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 7px solid {THEME["text"]};
        border-bottom: 0px solid transparent;
        margin-right: 12px;
    }}
    QComboBox#materialCombo[open="true"]::down-arrow {{
        border-top: 0px solid transparent;
        border-bottom: 7px solid {THEME["text"]};
    }}
    QComboBox#materialCombo[open="false"]::down-arrow {{
        border-top: 7px solid {THEME["text"]};
        border-bottom: 0px solid transparent;
    }}
    QComboBox QAbstractItemView {{
        background: #06152d;
        color: #ffffff;
        border: 1px solid rgba(71, 220, 255, 0.36);
        border-radius: 14px;
        padding: 7px;
        selection-background-color: {THEME["blue"]};
        selection-color: #ffffff;
        outline: none;
    }}
    QComboBox QAbstractItemView::item {{
        min-height: 38px;
        padding: 9px 14px;
        border-radius: 13px;
        margin: 2px;
    }}
    QComboBox[centerOptions="true"] QAbstractItemView::item,
    QAbstractItemView[centerOptions="true"]::item {{
        text-align: center;
    }}
    QComboBox QAbstractItemView::item:selected {{
        background: {dropdown_gradient};
        color: #ffffff;
        font-weight: 800;
        border-radius: 13px;
    }}
    QComboBox QAbstractItemView::item:hover {{
        background: #0d5fcf;
        border-radius: 13px;
    }}
    QPlainTextEdit#terminal {{
        background: #020b18;
        color: #7de7ff;
        border: 1px solid rgba(71, 220, 255, 0.22);
        border-radius: 14px;
        padding: 10px;
        font-family: "Cascadia Mono", Consolas, monospace;
        font-size: 12px;
        selection-background-color: {THEME["blue_dark"]};
    }}
    QProgressBar#progressBar {{
        height: 11px;
        border-radius: 6px;
        background: rgba(71, 220, 255, 0.12);
        text-align: center;
        color: transparent;
    }}
    QProgressBar#progressBar::chunk {{
        border-radius: 5px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00b7ff, stop:0.55 #57c785, stop:1 #eddd53);
    }}
    QDialog#materialDialog {{
        background: {panel_gradient};
        border: 1px solid rgba(71, 220, 255, 0.32);
        border-radius: 18px;
    }}
    QLabel#dialogTitle {{
        color: {THEME["cyan"]};
        font-size: 21px;
        font-weight: 700;
    }}
    QLabel#errorTitle {{
        color: {THEME["danger"]};
        font-size: 21px;
        font-weight: 800;
    }}
    QLabel#successText {{
        color: {THEME["success"]};
        font-size: 17px;
        font-weight: 800;
    }}
    QLabel#failureText {{
        color: {THEME["danger"]};
        font-size: 17px;
        font-weight: 800;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 9px;
        border: none;
        margin: 8px 0px 8px 0px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(84, 217, 255, 0.22);
        border: none;
        border-radius: 4px;
        min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: rgba(84, 217, 255, 0.42);
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        width: 0px;
        height: 0px;
        subcontrol-origin: margin;
        background: transparent;
        border: none;
        border-radius: 4px;
    }}
    QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
        width: 0px;
        height: 0px;
        image: none;
        background: transparent;
        border: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
        border: none;
        border-radius: 4px;
    }}
    """


def main():
    try:
        require_gui_dependencies()
    except RuntimeError as error:
        print(error)
        print("Install dependencies with: pip install -r requirements.txt")
        return 1

    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    if apply_stylesheet is not None:
        apply_stylesheet(app, theme="dark_blue.xml")
        app.setStyleSheet(app.styleSheet() + "\n" + material_qss())
    else:
        app.setStyleSheet(material_qss())
    window = LogoAdderUltra()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
