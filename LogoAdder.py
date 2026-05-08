import multiprocessing
import os
import sys

os.environ.setdefault("QT_LOGGING_RULES", "qt.text.font.db.warning=false")

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

try:
    from PySide6.QtWidgets import QApplication, QStyleFactory
except ModuleNotFoundError:
    QApplication = None
    QStyleFactory = None


def require_gui_dependencies():
    missing = []
    if QApplication is None:
        missing.append("PySide6")
    if Image is None:
        missing.append("pillow")
    if missing:
        raise RuntimeError(f"Missing required package(s): {', '.join(missing)}")


def main():
    multiprocessing.freeze_support()
    try:
        require_gui_dependencies()
    except RuntimeError as error:
        print(error)
        print("Install dependencies with: pip install -r requirements.txt")
        return 1

    from styles import load_app_fonts, material_qss

    app = QApplication(sys.argv)
    load_app_fonts()
    from main_window import LogoAdderUltra

    app.setStyle(QStyleFactory.create("Fusion"))
    app.setStyleSheet(material_qss())
    window = LogoAdderUltra()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
