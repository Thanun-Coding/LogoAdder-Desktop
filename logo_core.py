import ctypes
import json
import os
import sys
from pathlib import Path


SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif")
ALPHA_EXTENSIONS = (".png", ".webp")
OUTPUT_FORMATS = ("Same as source", "PNG", "JPG", "WebP")

KHMER_POSITIONS = {
    "top_left": "លើ-ឆ្វេង",
    "top_right": "លើ-ស្តាំ",
    "bottom_left": "ក្រោម-ឆ្វេង",
    "bottom_right": "ក្រោម-ស្តាំ",
    "center": "កណ្ដាល",
}
POSITION_VALUES = list(KHMER_POSITIONS.values())
DEFAULT_POSITION = KHMER_POSITIONS["top_right"]

DEFAULT_OUTPUT_SETTINGS = {
    "format": "Same as source",
    "quality": 100,
    "name_prefix": "EOA",
    "folder_name": "Outputs",
}

DEFAULT_CONFIG = {
    "opacity": 1.0,
    "position": DEFAULT_POSITION,
    "logo_size": 5,
    "logo_path": "",
    "folder_path": "",
    "m_top": 10,
    "m_bottom": 10,
    "m_left": 10,
    "m_right": 10,
    "output": DEFAULT_OUTPUT_SETTINGS.copy(),
    "presets": {},
    "selected_preset": "",
}


def application_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_FILE = application_dir() / "config.json"


def resource_path(relative_path):
    base_path = Path(getattr(sys, "_MEIPASS", application_dir()))
    return base_path / relative_path


def set_hidden_attribute(path, hidden=True):
    if os.name != "nt" or not hasattr(ctypes, "windll") or not Path(path).exists():
        return

    file_attribute_hidden = 0x02
    kernel32 = ctypes.windll.kernel32
    attrs = kernel32.GetFileAttributesW(str(path))
    if attrs == -1:
        return

    if hidden:
        attrs |= file_attribute_hidden
    else:
        attrs &= ~file_attribute_hidden
    kernel32.SetFileAttributesW(str(path), attrs)


def is_supported_image(filename):
    return str(filename).lower().endswith(SUPPORTED_EXTENSIONS)


def should_preserve_alpha(filename):
    return str(filename).lower().endswith(ALPHA_EXTENSIONS)


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def detect_image_orientation(image_width, image_height):
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be greater than zero")
    if image_width > image_height:
        return "landscape"
    if image_height > image_width:
        return "portrait"
    return "square"


def calculate_scale_anchor(image_width, image_height):
    orientation = detect_image_orientation(image_width, image_height)
    if orientation == "landscape":
        return image_width
    if orientation == "portrait":
        return image_height
    return image_width


def calculate_logo_size(image_width, image_height, logo_width, logo_height, size_percent):
    anchor = calculate_scale_anchor(image_width, image_height)
    if logo_width <= 0 or logo_height <= 0:
        raise ValueError("logo dimensions must be greater than zero")

    percent = clamp(float(size_percent), 1.0, 100.0)
    width = max(1, int(round(anchor * (percent / 100))))
    height = max(1, int(round(logo_height * (width / logo_width))))
    return width, height


def normalize_position(position):
    return position if position in POSITION_VALUES else DEFAULT_POSITION


def calculate_position(image_size, logo_size, position, margins):
    image_width, image_height = image_size
    logo_width, logo_height = logo_size
    position = normalize_position(position)
    top = int(margins.get("top", 0))
    bottom = int(margins.get("bottom", 0))
    left = int(margins.get("left", 0))
    right = int(margins.get("right", 0))

    if position == KHMER_POSITIONS["top_left"]:
        x, y = left, top
    elif position == KHMER_POSITIONS["top_right"]:
        x, y = image_width - logo_width - right, top
    elif position == KHMER_POSITIONS["bottom_left"]:
        x, y = left, image_height - logo_height - bottom
    elif position == KHMER_POSITIONS["bottom_right"]:
        x, y = image_width - logo_width - right, image_height - logo_height - bottom
    else:
        x, y = (image_width - logo_width) // 2, (image_height - logo_height) // 2

    return clamp(x, 0, max(0, image_width - logo_width)), clamp(y, 0, max(0, image_height - logo_height))


def scale_margins(margins, original_size, preview_size):
    preview_width, preview_height = preview_size
    if preview_width <= 0 or preview_height <= 0:
        return margins.copy()

    sx = original_size[0] / preview_width
    sy = original_size[1] / preview_height
    return {
        "top": int(round(margins.get("top", 0) * sy)),
        "bottom": int(round(margins.get("bottom", 0) * sy)),
        "left": int(round(margins.get("left", 0) * sx)),
        "right": int(round(margins.get("right", 0) * sx)),
    }


def list_images(folder):
    try:
        return sorted(f for f in os.listdir(folder) if is_supported_image(f))
    except OSError:
        return []


def normalize_selected_image_paths(paths):
    normalized = []
    seen = set()

    for raw_path in paths:
        path = Path(raw_path)
        if path.is_file() and is_supported_image(path.name):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                normalized.append(path)

    if not normalized:
        return []

    parent = normalized[0].parent
    return [path for path in normalized if path.parent == parent]


def normalize_output_settings(settings):
    settings = settings if isinstance(settings, dict) else {}
    output_format = settings.get("format", DEFAULT_OUTPUT_SETTINGS["format"])
    if output_format not in OUTPUT_FORMATS:
        output_format = DEFAULT_OUTPUT_SETTINGS["format"]

    try:
        quality = int(settings.get("quality", DEFAULT_OUTPUT_SETTINGS["quality"]))
    except (TypeError, ValueError):
        quality = DEFAULT_OUTPUT_SETTINGS["quality"]

    legacy_suffix = str(settings.get("suffix", "")).strip()
    name_prefix = str(settings.get("name_prefix", "")).strip()
    if not name_prefix and legacy_suffix:
        name_prefix = legacy_suffix.strip("_- ") or DEFAULT_OUTPUT_SETTINGS["name_prefix"]
    folder_name = str(settings.get("folder_name", DEFAULT_OUTPUT_SETTINGS["folder_name"])).strip()

    return {
        "format": output_format,
        "quality": int(clamp(quality, 1, 100)),
        "name_prefix": name_prefix or DEFAULT_OUTPUT_SETTINGS["name_prefix"],
        "folder_name": folder_name or DEFAULT_OUTPUT_SETTINGS["folder_name"],
    }


def extension_for_format(original_extension, output_format):
    if output_format == "PNG":
        return ".png"
    if output_format == "JPG":
        return ".jpg"
    if output_format == "WebP":
        return ".webp"
    return original_extension


def build_output_path(folder, filename, output_settings, sequence_number=1):
    settings = normalize_output_settings(output_settings)
    source = Path(filename)
    extension = extension_for_format(source.suffix, settings["format"])
    output_name = f"{settings['name_prefix']}-{int(sequence_number)}{extension}"
    return Path(folder) / settings["folder_name"] / output_name


def unique_output_path(output_path):
    output_path = Path(output_path)
    if not output_path.exists():
        return output_path

    counter = 1
    while True:
        candidate = output_path.with_name(f"{output_path.stem}-{counter}{output_path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def save_output_image(image, output_path, output_settings=None):
    output_path = Path(output_path)
    settings = normalize_output_settings(output_settings)
    save_kwargs = {}
    suffix = output_path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        image = image.convert("RGB")
        save_kwargs["quality"] = settings["quality"]
    elif suffix == ".webp":
        save_kwargs["quality"] = settings["quality"]
        save_kwargs["lossless"] = should_preserve_alpha(output_path.name)
    elif not should_preserve_alpha(output_path.name):
        image = image.convert("RGB")
    image.save(output_path, **save_kwargs)


def preset_from_settings(settings):
    output = normalize_output_settings(settings.get("output", {}))
    return {
        "logo_path": str(settings.get("logo_path", "")),
        "position": normalize_position(settings.get("position")),
        "logo_size": int(clamp(float(settings.get("logo_size", 5)), 1, 100)),
        "opacity": clamp(float(settings.get("opacity", 1.0)), 0.0, 1.0),
        "m_top": int(clamp(float(settings.get("m_top", 10)), 0, 500)),
        "m_bottom": int(clamp(float(settings.get("m_bottom", 10)), 0, 500)),
        "m_left": int(clamp(float(settings.get("m_left", 10)), 0, 500)),
        "m_right": int(clamp(float(settings.get("m_right", 10)), 0, 500)),
        "output": output,
    }


def normalize_presets(presets):
    if not isinstance(presets, dict):
        return {}
    return {str(name): preset_from_settings(value) for name, value in presets.items() if str(name).strip()}


def load_config():
    config = DEFAULT_CONFIG.copy()
    config["output"] = DEFAULT_OUTPUT_SETTINGS.copy()
    config["presets"] = {}
    if CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open("r", encoding="utf-8") as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                config.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass

    config["position"] = normalize_position(config.get("position"))
    config["output"] = normalize_output_settings(config.get("output"))
    config["presets"] = normalize_presets(config.get("presets"))
    return config


def save_config(data):
    try:
        set_hidden_attribute(CONFIG_FILE, hidden=False)
        with CONFIG_FILE.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        set_hidden_attribute(CONFIG_FILE, hidden=True)
    except OSError:
        pass


def build_error_summary(errors):
    if not errors:
        return "No failed files."
    lines = ["Failed files:"]
    for error in errors:
        lines.append(f"{error.get('file', 'Unknown')} - {error.get('error', 'Unknown error')}")
    return "\n".join(lines)


def write_error_summary(output_dir, errors):
    if not errors:
        return None
    path = Path(output_dir) / "failed_files.txt"
    path.write_text(build_error_summary(errors), encoding="utf-8")
    return path
