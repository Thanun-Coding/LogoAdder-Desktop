import queue
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

import logo_core as core
from dialogs import apply_app_icon, fit_dialog_to_screen
from logo_core import (
    KHMER_POSITIONS,
    OUTPUT_FORMATS,
    POSITION_VALUES,
    PREVIEW_SIZE,
    build_output_path,
    compose_logo,
    get_config_error,
    is_duplicate_preset_name,
    list_images,
    load_config,
    normalize_output_settings,
    normalize_position,
    normalize_selected_image_paths,
    open_rgba_image,
    preset_from_settings,
    resource_path,
    save_config,
)
from preview import pil_to_pixmap, ui_font
from styles import (
    APP_TITLE,
    COMPACT_WINDOW_HEIGHT,
    COMPACT_WINDOW_WIDTH,
    SITE_STYLE,
    THEME,
    TITLE_FONT_FAMILY,
    TITLE_LOGO_FILE,
    add_shadow,
    center_window_on_screen,
    make_font,
    screen_fitting_window_size,
)
from ui_widgets import DropOverlay, FriendlySlider, LiveHeader, MaterialComboBox, PreviewLabel, ShortcutConfirmDialog
from workers import run_processing_worker


class LogoAdderUltra(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        config_error = get_config_error()
        # Photo folders are intentionally session-only so startup does not touch old user images.
        self.config["folder_path"] = ""
        if self.config.get("logo_path") and not Path(self.config["logo_path"]).exists():
            self.config["logo_path"] = ""
        self.current_preview_index = 0
        self.image_list = []
        self.inputs = {}
        self.is_updating_from_slider = False
        self.processing_thread = None
        self.processing_started_at = None
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
        if config_error:
            self.write_log(f"! {config_error}")
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.poll_processing_queue)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.update_live_preview)

    def setup_window(self):
        self.setWindowTitle(APP_TITLE)
        self.setFixedSize(screen_fitting_window_size())
        center_window_on_screen(self)
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
        self.sidebar.setFixedWidth(350 if self.width() >= COMPACT_WINDOW_WIDTH else 310)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(18, 18, 2, 18)
        sidebar_layout.setSpacing(12)
        layout.addWidget(self.sidebar)

        self.create_sidebar(sidebar_layout)
        self.create_main_area(layout)
        self.drop_overlay = DropOverlay(root)
        self.drop_overlay.setGeometry(root.rect())

    def create_sidebar(self, layout):
        card_width = self.sidebar.width() - 36
        header = QFrame()
        header.setObjectName("sidebarHeader")
        header.setFixedWidth(card_width)
        add_shadow(header, blur=24, y_offset=8, alpha=76)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 16, 12, 16)
        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        title_logo = resource_path(TITLE_LOGO_FILE)
        if title_logo.exists():
            logo.setPixmap(QPixmap(str(title_logo)).scaled(card_width - 24, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo.setText("កម្មវិធីដាក់Logoលើរូបភាព")
            logo.setFont(make_font(22, family=TITLE_FONT_FAMILY))
        header_layout.addWidget(logo)
        layout.addWidget(header, 0, Qt.AlignLeft)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("sidebarScroll")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        scroll.horizontalScrollBar().setEnabled(False)
        scroll.horizontalScrollBar().valueChanged.connect(lambda _value: scroll.horizontalScrollBar().setValue(0))
        scroll_content = QWidget()
        scroll_content.setMinimumWidth(0)
        scroll_content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.sidebar_body = scroll_content
        self.sidebar_layout = QVBoxLayout(scroll_content)
        self.sidebar_layout.setContentsMargins(16, 8, 24, 8)
        self.sidebar_layout.setSpacing(10)
        self.sidebar_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        scroll.setWidget(scroll_content)
        self.sidebar_scroll = scroll
        layout.addWidget(scroll, 1)

        footer = QFrame()
        footer.setObjectName("sidebarFooter")
        footer.setFixedWidth(card_width)
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
        layout.addWidget(footer, 0, Qt.AlignLeft)

        self.populate_sidebar()

    def populate_sidebar(self):
        self.add_section("រូបភាព")
        source_row = QHBoxLayout()
        self.btn_browse_photos = self.create_button("ជ្រើសរើស Photo", self.browse_photos)
        self.btn_browse_folder = self.create_button("ជ្រើសរើស Folder", self.browse_folder)
        source_row.addWidget(self.btn_browse_photos)
        source_row.addWidget(self.btn_browse_folder)
        self.sidebar_layout.addLayout(source_row)
        self.folder_path_lbl = self.create_hint_label("មិនទាន់មានរូបភាព!")

        self.add_section("ឡូហ្គោ")
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

        self.create_input_group("ទំហំ Logo (%)", "logo_size", 1, 100, self.config["logo_size"])
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
        if self.width() < COMPACT_WINDOW_WIDTH or self.height() < COMPACT_WINDOW_HEIGHT:
            self.preview_canvas.setMinimumSize(520, 280)
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
        log_height = 110 if self.height() < COMPACT_WINDOW_HEIGHT else 150
        self.log_box.setMinimumHeight(log_height)
        self.log_box.setMaximumHeight(log_height)
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
        paths = [Path(url.toLocalFile()) for url in urls if url.toLocalFile()]
        image_paths = normalize_selected_image_paths(paths)
        if image_paths:
            self.set_photo_files(image_paths)
            return

        folder_paths = [path for path in paths if path.is_dir()]
        if folder_paths:
            self.set_folder(folder_paths[0])
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
        data = self.current_config() if hasattr(self, "output_format_menu") else self.config.copy()
        data.pop("folder_path", None)
        saved = save_config(data)
        if not saved and hasattr(self, "log_box"):
            self.write_log(f"! {get_config_error()}")
        return saved

    def apply_selected_preset(self, name):
        preset = self.config.get("presets", {}).get(name)
        if not preset:
            return
        self.config["selected_preset"] = name
        self.persist_presets()
        self.pos_menu.setCurrentText(normalize_position(preset.get("position")))
        self.set_input_value("logo_size", int(preset.get("logo_size", 5)))
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
        fit_dialog_to_screen(dialog, 360, 205)
        apply_app_icon(dialog)
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
            if is_duplicate_preset_name(name, self.config.get("presets", {})):
                choice = self.duplicate_preset_dialog(name)
                if choice == "rename":
                    name_entry.setProperty("error", True)
                    self.refresh_style(name_entry)
                    name_entry.setFocus()
                    name_entry.selectAll()
                    return
                if choice != "overwrite":
                    return
            self.config["presets"][name] = preset_from_settings(self.current_config())
            self.refresh_preset_menu()
            self.preset_menu.setCurrentText(name)
            if not self.persist_presets():
                self.themed_message_dialog("បញ្ហា Config", get_config_error() or "មិនអាចរក្សាទុក config បានទេ", danger=True)
            self.write_log(f"> បានរក្សាទុកPreset: {name}")
            dialog.accept()

        save_btn.clicked.disconnect()
        save_btn.clicked.connect(save_preset)
        for button in (save_btn, close_btn):
            button.setProperty("dialogButton", True)
            self.refresh_style(button)
        name_entry.returnPressed.connect(save_preset)
        dialog.exec()

    def duplicate_preset_dialog(self, name):
        dialog = QDialog(self)
        dialog.setWindowTitle("Preset មានរួចហើយ")
        dialog.setObjectName("materialDialog")
        fit_dialog_to_screen(dialog, 410, 180)
        apply_app_icon(dialog)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(7)
        title = QLabel("Preset មានរួចហើយ")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignCenter)
        body = QLabel(f"Preset '{name}' មានរួចហើយ។ ប្ដូរឈ្មោះ ឬរក្សាទុកលើឈ្មោះនេះ?")
        body.setObjectName("hintLabel")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)

        row = QHBoxLayout()
        row.setSpacing(8)
        overwrite_btn = QPushButton("រក្សាទុកលើឈ្មោះនេះ")
        overwrite_btn.setProperty("variant", "success")
        overwrite_btn.setProperty("dialogButton", True)
        overwrite_btn.setCursor(Qt.PointingHandCursor)
        overwrite_btn.setFocusPolicy(Qt.NoFocus)
        rename_btn = QPushButton("ប្ដូរឈ្មោះ")
        rename_btn.setProperty("variant", "danger")
        rename_btn.setProperty("dialogButton", True)
        rename_btn.setCursor(Qt.PointingHandCursor)
        rename_btn.setFocusPolicy(Qt.NoFocus)

        choice = {"value": ""}

        def choose(value):
            choice["value"] = value
            dialog.accept()

        overwrite_btn.clicked.connect(lambda: choose("overwrite"))
        rename_btn.clicked.connect(lambda: choose("rename"))
        row.addWidget(overwrite_btn, 2)
        row.addWidget(rename_btn, 1)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addLayout(row)
        dialog.exec()
        return choice["value"]

    def themed_message_dialog(self, title_text, body_text, confirm_text="យល់ព្រម", danger=False):
        dialog = QDialog(self)
        dialog.setWindowTitle(title_text)
        dialog.setObjectName("materialDialog")
        fit_dialog_to_screen(dialog, 360, 165)
        apply_app_icon(dialog)

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

    def confirm_dialog(self, title_text, body_text, confirm_text="លុប", cancel_text="បិទ", confirm_keys=None):
        dialog = ShortcutConfirmDialog(confirm_keys=confirm_keys, parent=self)
        dialog.setWindowTitle(title_text)
        dialog.setObjectName("materialDialog")
        fit_dialog_to_screen(dialog, 360, 165)
        apply_app_icon(dialog)

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
        confirm_btn.setProperty("variant", "success")
        confirm_btn.setProperty("dialogButton", True)
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
        if not self.confirm_dialog("លុប Preset", f"លុប Preset '{name}' មែនទេ?", confirm_text="លុប", cancel_text="បិទ", confirm_keys={Qt.Key_Space}):
            return
        del self.config["presets"][name]
        self.refresh_preset_menu()
        if not self.persist_presets():
            self.themed_message_dialog("បញ្ហា Config", get_config_error() or "មិនអាចរក្សាទុក config បានទេ", danger=True)
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
        except (OSError, ValueError, RuntimeError) as error:
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
        image_paths = normalize_selected_image_paths(paths)
        if not image_paths:
            self.themed_message_dialog("រកមិនឃើញរូបភាព", "មិនមានរូបភាពដែលគាំទ្រសម្រាប់បើកទេ។")
            return
        self.image_list = [path.name for path in image_paths]
        parent = image_paths[0].parent
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
            self.preview_canvas.clear_preview("សូមជ្រើសរើសរូបភាព ឬទម្លាក់ Folder នៅទីនេះ")
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
        except (OSError, ValueError, RuntimeError) as error:
            self.write_log(f"! Preview failed: {error}")
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
            except (RuntimeError, TypeError):
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
        conflict_policy = "rename"
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
        self.processing_started_at = time.monotonic()
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
        fit_dialog_to_screen(dialog, 440, 235)
        apply_app_icon(dialog)

        selected = {"policy": None}
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("រូបភាពមានរួចហើយ")
        title.setObjectName("dialogTitle")
        title.setAlignment(Qt.AlignCenter)
        body = QLabel(f"រកឃើញ {conflict_count} រូបភាពដែលអាចមានឈ្មោះជាន់គ្នា។\nជម្រើសសុវត្ថិភាពគឺប្តូរឈ្មោះថ្មី ដើម្បីមិនលុបលទ្ធផលចាស់។")
        body.setObjectName("hintLabel")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignCenter)

        overwrite_btn = QPushButton("លុបរូបភាពដើម និងរក្សាទុកថ្មី")
        overwrite_btn.setProperty("variant", "danger")
        rename_btn = QPushButton("ប្តូរឈ្មោះថ្មី")
        rename_btn.setProperty("variant", "success")
        rename_btn.setDefault(True)
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
        action_row.addWidget(rename_btn)
        action_row.addWidget(overwrite_btn)
        action_row.addWidget(cancel_btn)

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addLayout(action_row)

        if dialog.exec() == QDialog.Accepted:
            return selected["policy"]
        return None

    def processing_worker(self, folder, logo_path, files, settings, conflict_policy="rename"):
        run_processing_worker(folder, logo_path, files, settings, conflict_policy, self.processing_queue, self.cancel_requested)

    def poll_processing_queue(self):
        try:
            while True:
                message = self.processing_queue.get_nowait()
                kind = message[0]
                if kind == "progress":
                    _, index, total, filename = message
                    self.progress.setValue(int(index / total * 1000))
                    self.count_label.setText(f"{index} / {total}")
                    remaining = max(total - index, 0)
                    eta_text = ""
                    if self.processing_started_at and index:
                        elapsed = max(time.monotonic() - self.processing_started_at, 0.1)
                        seconds_left = int((elapsed / index) * remaining)
                        eta_text = f" | នៅសល់ {remaining} | ~{seconds_left}s"
                    self.status_label.setText(f"កំពុងដំណើរការ: {filename}{eta_text}")
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
        self.processing_started_at = None
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
        fit_dialog_to_screen(dialog, 380, 205)
        dialog.setMaximumSize(400, 230)
        apply_app_icon(dialog)

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
            self.status_label.setText("បានស្នើបោះបង់ - កំពុងបញ្ឈប់ការងារថ្មី.....")
            self.write_log("> បានស្នើបោះបង់។ រូបភាពដែលកំពុងដំណើរការរួចអាចត្រូវរង់ចាំបន្តិច។")
            self.btn_start.setEnabled(False)
            self.btn_start.setText("កំពុងបោះបង់.....")

    def refresh_style(self, widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
