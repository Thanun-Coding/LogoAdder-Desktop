# Agent Guide

This project is a Python desktop application for batch-adding a logo or watermark to images. It is not a web app and does not use `package.json`, routing, or a `src/` folder.

## Project Overview

- App name: `LogoAdder`
- Main entry point: `LogoAdder.py`
- Core helper module: `logo_core.py`
- UI framework: PySide6
- Image processing: Pillow
- Styling: custom QSS in `styles.py`
- Packaging: PyInstaller via `build_exe.ps1` and `LogoAdder.spec`

The app lets users choose a folder or selected image files, choose a logo, preview placement, configure logo size, opacity, position, margins, output format, output quality, output folder/name prefix, and process images in batch.

## Important Files

- `LogoAdder.py`
  - Small application entry point.

- `main_window.py`
  - Main GUI window, application state, dialogs, preview flow, and user workflow.

- `ui_widgets.py`
  - Custom widgets such as the combo box, slider, preview label, and drag overlay.

- `dialogs.py`
  - Shared dialog sizing and icon helpers.

- `preview.py`
  - Pillow-to-Qt preview helpers.

- `workers.py`
  - Multiprocessing batch worker orchestration and cancel behavior.

- `styles.py`
  - App constants, fonts, sizing helpers, and QSS styling.

- `logo_core.py`
  - Pure/shared logic for supported extensions, config load/save, presets, output path generation, image sizing, logo positioning, margin scaling, output saving, and error summaries.
  - Also owns helper-friendly image processing functions used by tests and worker processes.
  - Prefer putting testable non-UI behavior here instead of adding more logic to `LogoAdder.py`.

- `tests/test_logo_helpers.py`
  - Unit tests for helper functions and image-processing behavior.

- `requirements.txt`
  - Runtime/build dependencies.

- `build_exe.ps1`
  - Builds the Windows executable with PyInstaller.

- `LogoAdder.spec`
  - PyInstaller spec file.

- `assets/`
  - Bundled icon, title image, and Khmer fonts.

- `docs/`
  - Project guide and non-runtime documentation.

- `config.json`
  - Local app state for presets and selected preset.
  - This file is ignored by git.

## Generated / Local Artifacts

These folders are generated or local output and should usually not be edited manually:

- `build/`
- `dist/`
- `Outputs/`
- `__pycache__/`
- `tests/__pycache__/`
- `tests/Outputs/`

Be careful with large generated image files under `tests/Outputs/`; they may not be intended source fixtures.

## Run From Source

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python LogoAdder.py
```

## Run Tests

```powershell
python -m unittest discover -s tests
```

The helper tests import from `logo_core.py` where possible, so they do not need to open the GUI.

## Build EXE

```powershell
.\build_exe.ps1
```

Expected output:

```text
dist\LogoAdder.exe
```

The build intentionally uses PyInstaller one-file mode so users can receive one app file.

The build bundles:

- `assets/applogo.ico`
- `assets/Title Logo.png`
- `assets/KhmerOSmuollight.ttf`
- `assets/KhmerOSsiemreap.ttf`
- `assets/brown cheese.otf`

## Config And Paths

- User presets are stored at `%APPDATA%\LogoAdder\config.json` on Windows.
- `folder_path` is intentionally session-only so startup does not touch an old photo folder.
- Output folder names and file name prefixes are sanitized in `logo_core.py`.
- Use `resource_path()` for bundled read-only assets such as `applogo.ico`, `Title Logo.png`, SVG icons, and bundled fonts. Source assets live in `assets/`.

## Development Notes

- Keep source files UTF-8. The app contains Khmer UI text.
- Prefer small, focused edits and keep module responsibilities clear.
- Put reusable or testable logic in `logo_core.py`.
- Keep UI-specific code in `main_window.py`, `ui_widgets.py`, `dialogs.py`, `preview.py`, or `styles.py`.
- Do not remove Khmer labels or bundled image/icon assets unless asked.
- Preserve Windows behavior, especially file dialogs, hidden `config.json`, Explorer opening, and PyInstaller packaging.
- Avoid destructive git operations. The worktree may contain generated files or user changes.

## Known Risks / Cleanup Targets

1. Fixed window/dialog sizes can still be brittle for some display scaling and Khmer text.
2. Generated build/output folders may be present in the repo workspace.
3. Full GUI behavior still needs manual testing on a small laptop screen.

## Recommended Change Order

1. Add or update focused tests before changing output path, preset, margin, or image-composition behavior.
2. Keep README and this guide in sync when changing setup, config, or build behavior.
3. Clean generated artifacts only when they are clearly not fixtures or deliverables.
