# LogoAdder Agent Guide

LogoAdder is a Windows desktop app. Do not treat it as a web project: there is no router, backend server, database, API layer, or auth system.

## App Shape

- Entry point: `LogoAdder.py`
- Main UI/controller: `main_window.py`
- Pure image/config/path logic: `logo_core.py`
- Batch worker orchestration: `workers.py`
- Custom widgets: `ui_widgets.py`
- QSS/theme/fonts/window sizing: `styles.py`
- Pillow-to-Qt preview helpers: `preview.py`
- Dialog helpers: `dialogs.py`
- Khmer digit helpers: `ui_text.py`
- Tests: `tests/test_logo_helpers.py`
- Build: `build_exe.ps1` and `LogoAdder.spec`
- Runtime assets: `assets/`

Startup flow:

1. `LogoAdder.py` calls `multiprocessing.freeze_support()`.
2. It checks PySide6/Pillow availability.
3. It loads app fonts with `styles.load_app_fonts()`.
4. It applies `styles.material_qss()`.
5. It opens `main_window.LogoAdderUltra`.

Processing flow:

1. UI collects selected photos/folder, logo, output settings, logo placement, and photo adjustments.
2. Preview uses Pillow in `main_window.py`, with helpers from `logo_core.py` and `preview.py`.
3. Final export uses `workers.run_processing_worker()`.
4. Worker processes call `logo_core.process_logo_task()`.
5. Outputs go under the selected image folder, default subfolder `Outputs`.

## File Ownership Rules

- Put testable non-UI behavior in `logo_core.py`.
- Keep PySide6 code out of `logo_core.py`.
- Keep reusable widget behavior in `ui_widgets.py`, not duplicated in `main_window.py`.
- Keep shared dialog sizing/icon behavior in `dialogs.py`.
- Keep QSS, theme colors, font registration, and app sizing constants in `styles.py`.
- Keep multiprocessing queue/executor behavior in `workers.py`.
- Do not introduce circular imports.
- Use `resource_path()` for bundled assets. Do not hardcode absolute local paths.

## UI Rules

- Preserve the current fixed-window desktop layout unless explicitly asked:
  - left sidebar for controls
  - right side for preview, status/logs, progress, and process actions
- Sidebar horizontal scrolling must stay disabled.
- The result/log box should remain read-only and non-clickable unless explicitly changed.
- Use existing helper patterns:
  - `create_button`
  - `create_combo`
  - `create_input_group`
  - `refresh_style`
  - `fit_dialog_to_screen`
- For QSS changes, prefer object names and dynamic properties over inline widget styles.
- Fixed dialogs should use `fit_dialog_to_screen()` when practical.
- Do not remove preview navigation, hotkeys, zoom, pan, or drag/drop behavior unless requested.

## Photo Adjustment Rules

- Adjustment slider changes update preview immediately.
- Per-photo adjustments are session-only and stored in `self.photo_adjustments`.
- Global adjustments can be captured in presets, but live adjustment changes should not auto-save to config.
- `Reset` in the adjustment popup should not clear rotation/flip transform settings unless requested.
- `Shift + Auto` applies auto adjustment to all currently loaded photos.
- Auto adjustment should remain local/simple; do not add AI/cloud dependencies.

## Khmer And Font Rules

- Keep source files UTF-8.
- Terminal mojibake does not automatically mean Khmer source text is broken.
- Khmer title/section text uses `KhmerOSmuollight.ttf`.
- Normal Khmer UI text uses `KhmerOSsiemreap.ttf`.
- Footer creator name uses `brown cheese.otf`.
- English UI text uses the configured font stack in `styles.py`.
- Do not replace Khmer labels with English unless asked.
- Use `to_khmer_digits()` only for visible UI numbers.
- Use `from_khmer_digits()` for user-entered numeric text.
- Keep internal values, config, file paths, filenames, and calculations in normal ASCII digits.

## Image Processing Rules

- Open user images through `open_rgba_image()`.
- `open_rgba_image()` applies EXIF orientation and converts to RGBA.
- HEIC/HEIF support depends on `pillow-heif` and `register_heif_opener()`.
- Supported inputs: PNG, JPG/JPEG, WebP, BMP, TIFF/TIF, HEIC, HEIF.
- Pillow does not save HEIC. `Same as source` for HEIC/HEIF must output JPG.
- Final output order:
  1. open image / apply EXIF orientation
  2. apply photo adjustments
  3. apply rotation/flips
  4. compose logo
  5. save output
- Logo size is based on the shortest image edge via `calculate_scale_anchor()`.
- Margins are preview-based and scaled for final output with `scale_margins()`.
- Output names/folders must use sanitizing helpers. Never allow user text to write outside the selected image folder.
- Default conflict behavior should remain safe rename, not overwrite.

## Config And Preset Rules

- Config path on Windows: `%APPDATA%\LogoAdder\config.json`.
- `folder_path` is session-only and should not be restored on startup.
- Do not auto-save all live UI settings.
- Presets are the durable settings mechanism.
- `persist_presets()` should persist only presets and selected preset metadata unless the product decision changes.
- `preset_from_settings()` must not store `folder_path`.
- Per-photo session adjustments must not be saved to presets.

## Build Rules

- Normal build command:

```powershell
.\build_exe.ps1
```

- Expected output: `dist\LogoAdder.exe`.
- Keep PyInstaller one-file/windowed behavior unless requested.
- Keep `build_exe.ps1` and `LogoAdder.spec` asset lists synchronized.
- Required bundled assets:
  - `assets/applogo.ico`
  - `assets/Title Logo.png`
  - `assets/KhmerOSmuollight.ttf`
  - `assets/KhmerOSsiemreap.ttf`
  - `assets/brown cheese.otf`
  - `assets/arrows-clockwise.svg`
  - `assets/flip-vertical.svg`
  - `assets/flip-horizontal.svg`
- Keep hidden import `pillow_heif`.
- The local `qt_material` warning is known; the app excludes and does not use `qt_material`.
- Do not commit `build/`, `dist/`, caches, logs, `Outputs/`, or generated test/output images unless explicitly requested.

## Test Rules

Run after code changes:

```powershell
.\.venv\Scripts\python.exe -m py_compile LogoAdder.py logo_core.py main_window.py ui_widgets.py styles.py dialogs.py preview.py workers.py ui_text.py
.\.venv\Scripts\python.exe -m pytest
```

Fallback if pytest is unavailable:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Add/update tests for changes to:

- output naming/conflicts
- path sanitization
- config/preset behavior
- image adjustment behavior
- logo sizing/positioning
- HEIC/HEIF behavior

Avoid broad GUI tests. Use narrow offscreen smoke checks only when useful.

## Fragile Areas

- `main_window.py` is large and mixes UI setup, dialogs, preview, state, and processing orchestration.
- Preview behavior and final export behavior are separate paths; verify both when changing image logic.
- Fixed window/dialog sizes can fail on small screens and display scaling.
- Multiprocessing cancel can stop new work but may not instantly stop already-running image tasks.
- Packaging breaks if asset names change without updating both build files.
- Output overwrite behavior can destroy user files; modify carefully.
- Config persistence is sensitive because users expect live settings not to auto-save.

## Safe Workflow

1. Inspect relevant files before editing.
2. Keep changes small and tied to the request.
3. Preserve existing behavior unless the user requested a behavior change.
4. Prefer `logo_core.py` plus tests for logic changes.
5. Use existing UI/style helpers for visual changes.
6. Update `README.md`, `docs/Agent.md`, `build_exe.ps1`, or `LogoAdder.spec` only when the change affects them.
7. Run compile/tests after code changes.
8. Build the EXE only when requested or when packaging changed.
9. Report modified files and checks run.
