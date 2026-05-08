from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect

from logo_core import resource_path

APP_VERSION = "1"
APP_TITLE = "កម្មវិធីដាក់Logoលើរូបភាព - Thanun"
TITLE_LOGO_FILE = "Title Logo.png"
TITLE_FONT_FILE = "KhmerOSmuollight.ttf"
NORMAL_FONT_FILE = "KhmerOSsiemreap.ttf"
WINDOW_SIZE = (1260, 900)
WINDOW_SCREEN_MARGIN = 32
COMPACT_WINDOW_WIDTH = 1120
COMPACT_WINDOW_HEIGHT = 820

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

NORMAL_FONT_FAMILY = "Khmer OS Siemreap"
TITLE_FONT_FAMILY = "Khmer OS Muol Light"
LATIN_FONT_FAMILY = "Comic Sans MS"
FONT_STACK = f'"{LATIN_FONT_FAMILY}", "{NORMAL_FONT_FAMILY}", "Noto Sans Khmer", "Khmer OS Battambang", "Leelawadee UI", "Segoe UI", "Roboto", "Arial"'
TITLE_FONT_STACK = f'"{TITLE_FONT_FAMILY}", "{LATIN_FONT_FAMILY}", "{NORMAL_FONT_FAMILY}", "Noto Sans Khmer", "Khmer OS Muol Light", "Arial"'

SITE_STYLE = {
    "bg": "#09090b",
    "panel": "#18181b",
    "accent": "#3b82f6",
    "border": "#27272a",
    "text": "#f4f4f5",
    "cyan": "#00e5ff",
}


def register_app_font(filename, fallback_family):
    path = resource_path(filename)
    if not path.exists():
        return fallback_family

    font_id = QFontDatabase.addApplicationFont(str(path))
    if font_id < 0:
        return fallback_family

    families = QFontDatabase.applicationFontFamilies(font_id)
    return families[0] if families else fallback_family


def load_app_fonts():
    global NORMAL_FONT_FAMILY, TITLE_FONT_FAMILY, FONT_STACK, TITLE_FONT_STACK
    NORMAL_FONT_FAMILY = register_app_font(NORMAL_FONT_FILE, NORMAL_FONT_FAMILY)
    TITLE_FONT_FAMILY = register_app_font(TITLE_FONT_FILE, TITLE_FONT_FAMILY)
    FONT_STACK = f'"{LATIN_FONT_FAMILY}", "{NORMAL_FONT_FAMILY}", "Noto Sans Khmer", "Khmer OS Battambang", "Leelawadee UI", "Segoe UI", "Roboto", "Arial"'
    TITLE_FONT_STACK = f'"{TITLE_FONT_FAMILY}", "{LATIN_FONT_FAMILY}", "{NORMAL_FONT_FAMILY}", "Noto Sans Khmer", "Khmer OS Muol Light", "Arial"'


def make_font(size, bold=False, family=None):
    family = family or LATIN_FONT_FAMILY
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


def screen_fitting_window_size():
    app = QApplication.instance()
    screen = app.primaryScreen() if app else None
    if screen is None:
        return QSize(*WINDOW_SIZE)

    available = screen.availableGeometry()
    width = min(WINDOW_SIZE[0], max(1, available.width() - WINDOW_SCREEN_MARGIN))
    height = min(WINDOW_SIZE[1], max(1, available.height() - WINDOW_SCREEN_MARGIN))
    return QSize(width, height)


def center_window_on_screen(window):
    app = QApplication.instance()
    screen = app.primaryScreen() if app else None
    if screen is None:
        return

    available = screen.availableGeometry()
    top_left = available.center() - window.rect().center()
    window.move(top_left)


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
        font-family: {TITLE_FONT_STACK};
        font-size: 16px;
        font-weight: 400;
        margin-top: 8px;
    }}
    QLabel#fieldLabel {{
        color: {THEME["text"]};
        font-size: 15px;
    }}
    QLabel#hintLabel, QLabel#mutedLabel {{
        color: {THEME["muted"]};
        font-size: 13px;
    }}
    QLabel#statusLabel, QLabel#creatorLabel {{
        color: {THEME["cyan"]};
        font-family: {TITLE_FONT_STACK};
        font-weight: 400;
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
        padding-left: 0px;
        padding-right: 0px;
    }}
    QSlider::groove:horizontal {{
        height: 4px;
        background: rgba(71, 220, 255, 0.16);
        border: none;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: #47dcff;
        border: 2px solid {THEME["sidebar"]};
        width: 18px;
        height: 18px;
        margin: -7px 0px;
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
        min-height: 44px;
        border-radius: 13px;
        padding-left: 14px;
        padding-right: 34px;
        color: {THEME["text"]};
        background: {dropdown_gradient};
        border: 1px solid rgba(71, 220, 255, 0.32);
        font-size: 13px;
        font-weight: 700;
    }}
    QComboBox#materialCombo:hover {{
        background: {button_hover_gradient};
        border: 1px solid rgba(237, 221, 83, 0.42);
    }}
    QComboBox#materialCombo::drop-down {{
        width: 34px;
        border: none;
        background: transparent;
    }}
    QComboBox#materialCombo::down-arrow {{
        image: none;
        width: 0;
        height: 0;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {THEME["text"]};
        border-bottom: 0px solid transparent;
        margin-right: 11px;
    }}
    QComboBox#materialCombo[open="true"]::down-arrow {{
        border-top: 0px solid transparent;
        border-bottom: 6px solid {THEME["text"]};
    }}
    QComboBox#materialCombo[open="false"]::down-arrow {{
        border-top: 6px solid {THEME["text"]};
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
        font-family: {TITLE_FONT_STACK};
        font-size: 21px;
        font-weight: 400;
    }}
    QLabel#errorTitle {{
        color: {THEME["danger"]};
        font-family: {TITLE_FONT_STACK};
        font-size: 21px;
        font-weight: 400;
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
    QScrollBar:horizontal {{
        height: 0px;
        max-height: 0px;
        background: transparent;
        border: none;
    }}
    QScrollBar::handle:horizontal,
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        height: 0px;
        max-height: 0px;
        background: transparent;
        border: none;
    }}
    """
