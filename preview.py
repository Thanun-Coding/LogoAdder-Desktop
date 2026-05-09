from PIL import ImageFont
from PySide6.QtGui import QImage, QPixmap

from logo_core import resource_path


def ui_font(size, bold=False):
    font_name = "arialbd.ttf" if bold else "arial.ttf"
    khmer_font = resource_path("KhmerOSsiemreap.ttf")
    if khmer_font.exists():
        try:
            return ImageFont.truetype(str(khmer_font), size)
        except OSError:
            pass
    try:
        return ImageFont.truetype(font_name, size)
    except OSError:
        return ImageFont.load_default()


def pil_to_pixmap(image):
    image = image.convert("RGBA")
    data = image.tobytes("raw", "RGBA")
    qimage = QImage(data, image.width, image.height, image.width * 4, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())
