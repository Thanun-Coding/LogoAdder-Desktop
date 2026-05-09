from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from logo_core import resource_path


def apply_app_icon(dialog):
    icon_path = resource_path("applogo.ico")
    if icon_path.exists():
        dialog.setWindowIcon(QIcon(str(icon_path)))


def fit_dialog_to_screen(dialog, preferred_width, preferred_height):
    """Keep fixed dialogs usable on smaller laptop screens and high display scaling."""
    app = QApplication.instance()
    screen = dialog.screen() if dialog.screen() else (app.primaryScreen() if app else None)
    if screen is None:
        dialog.setFixedSize(preferred_width, preferred_height)
        return

    available = screen.availableGeometry()
    width = min(preferred_width, max(300, available.width() - 64))
    height = min(preferred_height, max(150, available.height() - 64))
    dialog.setFixedSize(width, height)
