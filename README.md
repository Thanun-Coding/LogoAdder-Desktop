# LogoAdder

Windows desktop app for batch-adding a logo or watermark to images.

## What It Does

LogoAdder lets you:

- Select one image folder or several image files.
- Select a logo image.
- Preview the logo placement before exporting.
- Adjust logo size, opacity, position, and margins.
- Adjust photos with brightness, highlight, contrast, saturation, sharpness, warm/cool tone, rotation, and simple auto enhancement.
- Choose output format, quality, file name prefix, and output folder name.
- Export processed images into a separate output folder.

Supported input formats include PNG, JPG/JPEG, WebP, BMP, TIFF, HEIC, and HEIF. HEIC/HEIF files are decoded through `pillow-heif`; when output format is set to `Same as source`, HEIC/HEIF inputs are exported as JPG because Pillow does not save HEIC by default.

## Requirements

- Windows
- Python 3.10 or newer
- Tested locally with Python 3.14.4

Install dependencies from `requirements.txt`. For development checks, install `requirements-dev.txt`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

For test/development tools:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

## Run From Source

```powershell
.\.venv\Scripts\python LogoAdder.py
```

If you do not use a virtual environment:

```powershell
python -m pip install -r requirements.txt
python LogoAdder.py
```

## Run Tests

```powershell
.\.venv\Scripts\python -m unittest discover -s tests
```

Or, if development requirements are installed:

```powershell
.\.venv\Scripts\python -m pytest
```

The helper tests are designed to run without opening the GUI.

## Build EXE

```powershell
.\build_exe.ps1
```

The build script uses `.venv\Scripts\python.exe` when it exists, otherwise it falls back to `python` on `PATH`.

The executable is created at:

```text
dist\LogoAdder.exe
```

The build uses PyInstaller one-file mode so users can receive only one app file.

The build bundles:

- `assets/applogo.ico`
- `assets/Title Logo.png`
- `assets/KhmerOSmuollight.ttf`
- `assets/KhmerOSsiemreap.ttf`

If PyInstaller prints a `qt_material must be imported after PySide or PyQt` warning, it is from the local virtual environment. The app does not use `qt_material`, and the build script excludes it.

## Config And Output

- User presets are saved to `%APPDATA%\LogoAdder\config.json` on Windows.
- Exported images go into the selected image folder under the configured output folder name, defaulting to `Outputs`.
- If output files already exist, the safer default is to rename new files instead of overwriting old ones.
- Output folder names and file prefixes are sanitized so unsafe Windows path characters cannot write outside the selected image folder.

## Important Files

- `LogoAdder.py`: small app entry point.
- `main_window.py`: main PySide6 window and user workflow.
- `ui_widgets.py`: custom combo box, slider, preview label, and drag overlay widgets.
- `dialogs.py`: shared dialog sizing/icon helpers.
- `preview.py`: Pillow-to-Qt preview helpers.
- `workers.py`: multiprocessing batch worker orchestration and cancel handling.
- `styles.py`: app constants, fonts, sizing helpers, and QSS styling.
- `logo_core.py`: reusable image, config, preset, path, and processing helpers.
- `requirements.txt`: runtime/build dependencies.
- `requirements-dev.txt`: optional development/test dependencies.
- `assets/`: bundled icon, title image, and Khmer fonts.
- `docs/Agent.md`: detailed project guide for coding agents.
- `tests/test_logo_helpers.py`: unit tests for the helper behavior.
- `build_exe.ps1`: beginner-friendly PyInstaller build command.
- `LogoAdder.spec`: PyInstaller spec generated for the app.
