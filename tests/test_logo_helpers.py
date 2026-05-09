import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

import logo_core
from logo_core import (
    ADJUSTMENT_DEFAULTS,
    DEFAULT_OUTPUT_SETTINGS,
    KHMER_POSITIONS,
    apply_photo_adjustments,
    auto_adjust_image,
    build_error_summary,
    build_output_path,
    calculate_logo_size,
    calculate_position,
    calculate_scale_anchor,
    contained_preview_size,
    detect_image_orientation,
    estimate_auto_adjustments,
    is_duplicate_preset_name,
    is_dialog_confirm_key,
    is_supported_image,
    initialize_logo_worker,
    normalize_adjustments,
    normalize_output_settings,
    normalize_selected_image_paths,
    nearest_quality_preset,
    preset_from_settings,
    open_rgba_image,
    process_logo_task,
    sanitize_path_part,
    save_config,
    save_output_image,
    load_config,
    should_preserve_alpha,
    slider_position_from_value,
    slider_value_from_position,
    unique_output_path,
)
from ui_text import from_khmer_digits, to_khmer_digits


class LogoHelperTests(unittest.TestCase):
    def test_supported_image_extensions_are_case_insensitive(self):
        self.assertTrue(is_supported_image("photo.JPG"))
        self.assertTrue(is_supported_image("poster.webp"))
        self.assertTrue(is_supported_image("camera.HEIC"))
        self.assertTrue(is_supported_image("camera.heif"))
        self.assertFalse(is_supported_image("notes.txt"))

    def test_logo_size_never_returns_zero_dimensions(self):
        self.assertEqual(calculate_logo_size(3, 3, 2, 1, 5), (1, 1))

    def test_logo_size_keeps_aspect_ratio(self):
        self.assertEqual(calculate_logo_size(2000, 1000, 1000, 400, 10), (100, 40))

    def test_logo_size_uses_shortest_edge_for_landscape_and_portrait(self):
        landscape = calculate_logo_size(2000, 1000, 1000, 400, 5)
        portrait = calculate_logo_size(1000, 2000, 1000, 400, 5)

        self.assertEqual(landscape, (50, 20))
        self.assertEqual(portrait, landscape)

    def test_logo_size_scales_proportionally_for_mixed_resolutions(self):
        large = calculate_logo_size(3000, 2000, 1000, 400, 5)
        small = calculate_logo_size(1200, 800, 1000, 400, 5)

        self.assertEqual(large, (100, 40))
        self.assertEqual(small, (40, 16))

    def test_scale_anchor_uses_shortest_edge(self):
        self.assertEqual(calculate_scale_anchor(1200, 800), 800)
        self.assertEqual(calculate_scale_anchor(800, 1200), 800)

    def test_image_orientation_detection_uses_base_dimensions(self):
        self.assertEqual(detect_image_orientation(2000, 1000), "landscape")
        self.assertEqual(detect_image_orientation(1000, 2000), "portrait")
        self.assertEqual(detect_image_orientation(1000, 1000), "square")

    def test_position_uses_requested_corner_margins(self):
        result = calculate_position(
            image_size=(1000, 600),
            logo_size=(100, 50),
            position=KHMER_POSITIONS["bottom_right"],
            margins={"top": 10, "bottom": 30, "left": 20, "right": 40},
        )

        self.assertEqual(result, (860, 520))

    def test_center_position_ignores_margins(self):
        result = calculate_position(
            image_size=(1000, 600),
            logo_size=(100, 50),
            position=KHMER_POSITIONS["center"],
            margins={"top": 10, "bottom": 30, "left": 20, "right": 40},
        )

        self.assertEqual(result, (450, 275))

    def test_contained_preview_size_matches_thumbnail_bounds_without_upscaling(self):
        self.assertEqual(contained_preview_size((4000, 2000), (840, 500)), (840, 420))
        self.assertEqual(contained_preview_size((320, 240), (840, 500)), (320, 240))

    def test_slider_position_mapping_reaches_minimum_at_left_edge(self):
        self.assertEqual(slider_value_from_position(0, 240, 1, 100), 1)
        self.assertEqual(slider_value_from_position(240, 240, 1, 100), 100)
        self.assertEqual(slider_value_from_position(120, 240, 1, 100), 51)

    def test_slider_value_position_mapping_puts_minimum_on_left_edge(self):
        self.assertEqual(slider_position_from_value(1, 1, 100, 240), 0)
        self.assertEqual(slider_position_from_value(100, 1, 100, 240), 240)

    def test_dialog_confirm_key_only_matches_configured_shortcuts(self):
        self.assertTrue(is_dialog_confirm_key(32, {32}))
        self.assertFalse(is_dialog_confirm_key(16777220, {32}))

    def test_duplicate_preset_name_ignores_surrounding_whitespace(self):
        self.assertTrue(is_duplicate_preset_name("  Daily  ", {"Daily": {}}))
        self.assertFalse(is_duplicate_preset_name("Night", {"Daily": {}}))

    def test_alpha_output_is_preserved_for_formats_that_support_it(self):
        self.assertTrue(should_preserve_alpha("watermark.png"))
        self.assertTrue(should_preserve_alpha("watermark.webp"))
        self.assertFalse(should_preserve_alpha("watermark.jpg"))
        self.assertFalse(should_preserve_alpha("watermark.jpeg"))

    def test_open_rgba_image_applies_exif_orientation(self):
        with TemporaryDirectory() as temp_dir:
            from PIL import Image

            path = Path(temp_dir) / "rotated.jpg"
            image = Image.new("RGB", (80, 40), "white")
            exif = image.getexif()
            exif[274] = 6
            image.save(path, exif=exif)

            result = open_rgba_image(path)

            self.assertEqual(result.size, (40, 80))

    def test_adjustment_settings_are_clamped_and_defaulted(self):
        settings = normalize_adjustments(
            {
                "brightness": 500,
                "highlight": -500,
                "contrast": "bad",
                "saturation": 20,
                "sharpness": 300,
                "warmth": -20,
                "rotation": 91,
                "flip_horizontal": True,
                "flip_vertical": False,
                "auto": True,
            }
        )

        self.assertEqual(normalize_adjustments({}), ADJUSTMENT_DEFAULTS)
        self.assertEqual(settings["brightness"], 100)
        self.assertEqual(settings["highlight"], -100)
        self.assertEqual(settings["contrast"], 0)
        self.assertEqual(settings["saturation"], 20)
        self.assertEqual(settings["sharpness"], 100)
        self.assertEqual(settings["warmth"], -20)
        self.assertEqual(settings["rotation"], 0)
        self.assertEqual(settings["flip_horizontal"], 1)
        self.assertEqual(settings["flip_vertical"], 0)
        self.assertEqual(settings["auto"], 1)

    def test_photo_adjustments_change_pixels_and_keep_rgba(self):
        from PIL import Image

        image = Image.new("RGBA", (4, 4), (100, 110, 120, 200))
        result = apply_photo_adjustments(
            image,
            {
                "brightness": 20,
                "contrast": 10,
                "saturation": 25,
                "sharpness": 30,
                "warmth": 40,
            },
        )

        self.assertEqual(result.mode, "RGBA")
        self.assertNotEqual(result.getpixel((0, 0)), image.getpixel((0, 0)))
        self.assertEqual(result.getpixel((0, 0))[3], 200)

    def test_highlight_adjustment_changes_bright_pixels_more_than_dark_pixels(self):
        from PIL import Image

        image = Image.new("RGBA", (2, 1))
        image.putpixel((0, 0), (50, 50, 50, 255))
        image.putpixel((1, 0), (230, 230, 230, 255))

        result = apply_photo_adjustments(image, {"highlight": -50})

        self.assertEqual(result.getpixel((0, 0))[0], 50)
        self.assertLess(result.getpixel((1, 0))[0], 230)

    def test_photo_adjustment_rotation_changes_dimensions(self):
        from PIL import Image

        image = Image.new("RGBA", (40, 20), "white")
        result = apply_photo_adjustments(image, {"rotation": 90})

        self.assertEqual(result.size, (20, 40))

    def test_photo_adjustment_flips_pixels(self):
        from PIL import Image

        image = Image.new("RGBA", (2, 1))
        image.putpixel((0, 0), (255, 0, 0, 255))
        image.putpixel((1, 0), (0, 0, 255, 255))

        result = apply_photo_adjustments(image, {"flip_horizontal": 1})

        self.assertEqual(result.getpixel((0, 0)), (0, 0, 255, 255))
        self.assertEqual(result.getpixel((1, 0)), (255, 0, 0, 255))

    def test_auto_adjust_returns_valid_rgba_image(self):
        from PIL import Image

        image = Image.new("RGBA", (8, 8), (80, 90, 100, 180))
        result = auto_adjust_image(image)

        self.assertEqual(result.mode, "RGBA")
        self.assertEqual(result.size, image.size)

    def test_estimate_auto_adjustments_returns_slider_settings(self):
        from PIL import Image

        image = Image.new("RGBA", (8, 8), (70, 80, 95, 255))
        settings = estimate_auto_adjustments(image)

        self.assertIn("brightness", settings)
        self.assertIn("contrast", settings)
        self.assertEqual(settings["auto"], 0)
        self.assertEqual(settings["rotation"], 0)

    def test_output_path_uses_suffix_and_selected_format(self):
        settings = normalize_output_settings({"format": "PNG", "name_prefix": "EOA", "folder_name": "Export"})

        result = build_output_path("C:/Images", "photo.jpg", settings, 7)

        self.assertEqual(str(result).replace("\\", "/"), "C:/Images/Export/EOA-7.png")

    def test_unique_output_path_adds_number_when_file_exists(self):
        with TemporaryDirectory() as temp_dir:
            existing = Path(temp_dir) / "EOA-1.png"
            existing.write_text("old", encoding="utf-8")

            result = unique_output_path(existing)

            self.assertEqual(result.name, "EOA-1-1.png")

    def test_process_logo_task_uses_cached_logo_payload(self):
        with TemporaryDirectory() as temp_dir:
            from PIL import Image

            folder = Path(temp_dir)
            Image.new("RGB", (100, 80), "white").save(folder / "photo.png")
            logo = Image.new("RGBA", (20, 10), (255, 0, 0, 255))
            initialize_logo_worker((logo.size, logo.tobytes("raw", "RGBA")))

            result = process_logo_task(
                (
                    str(folder),
                    "photo.png",
                    1,
                    DEFAULT_OUTPUT_SETTINGS,
                    "overwrite",
                    {"top": 0, "bottom": 0, "left": 0, "right": 0},
                    KHMER_POSITIONS["top_left"],
                    10,
                    1.0,
                )
            )

            self.assertEqual(result[:3], ("success", 1, "photo.png"))
            self.assertTrue((folder / "Outputs" / "EOA-1.png").exists())

    def test_output_path_keeps_original_extension_when_format_is_same(self):
        result = build_output_path("C:/Images", "photo.JPEG", DEFAULT_OUTPUT_SETTINGS, 3)

        self.assertEqual(str(result).replace("\\", "/"), "C:/Images/Outputs/EOA-3.JPEG")

    def test_output_path_converts_heic_same_as_source_to_jpg(self):
        result = build_output_path("C:/Images", "photo.HEIC", DEFAULT_OUTPUT_SETTINGS, 3)

        self.assertEqual(str(result).replace("\\", "/"), "C:/Images/Outputs/EOA-3.jpg")

    def test_output_path_can_keep_source_name(self):
        settings = normalize_output_settings({"format": "JPG", "use_source_name": True, "folder_name": "Ready"})

        result = build_output_path("C:/Images", "IMG_001.png", settings, 3)

        self.assertEqual(str(result).replace("\\", "/"), "C:/Images/Ready/IMG_001.jpg")

    def test_save_output_image_converts_jpg_to_rgb(self):
        with TemporaryDirectory() as temp_dir:
            from PIL import Image

            output_path = Path(temp_dir) / "photo.jpg"
            image = Image.new("RGBA", (8, 8), (255, 0, 0, 120))

            save_output_image(image, output_path, {"format": "JPG", "quality": 90})

            with Image.open(output_path) as saved:
                self.assertEqual(saved.mode, "RGB")

    def test_save_output_image_preserves_png_alpha(self):
        with TemporaryDirectory() as temp_dir:
            from PIL import Image

            output_path = Path(temp_dir) / "photo.png"
            image = Image.new("RGBA", (8, 8), (255, 0, 0, 120))

            save_output_image(image, output_path, {"format": "PNG"})

            with Image.open(output_path) as saved:
                self.assertEqual(saved.mode, "RGBA")
                self.assertEqual(saved.getpixel((0, 0))[3], 120)

    def test_output_settings_are_clamped_and_defaulted(self):
        settings = normalize_output_settings({"format": "bad", "quality": 500, "name_prefix": "", "folder_name": ""})

        self.assertEqual(settings["format"], "Same as source")
        self.assertEqual(settings["quality"], 100)
        self.assertEqual(settings["name_prefix"], "EOA")
        self.assertEqual(settings["folder_name"], "Outputs")
        self.assertFalse(settings["use_source_name"])

    def test_quality_values_snap_to_nearest_preset(self):
        self.assertEqual(nearest_quality_preset(84), 85)
        self.assertEqual(nearest_quality_preset(90), 92)
        self.assertEqual(nearest_quality_preset(98), 100)

    def test_output_settings_sanitize_path_parts(self):
        settings = normalize_output_settings(
            {
                "name_prefix": "../bad:name*",
                "folder_name": r"..\outside/CON",
            }
        )

        self.assertEqual(settings["name_prefix"], "-bad-name-")
        self.assertEqual(settings["folder_name"], "-outside-CON")

    def test_sanitize_path_part_uses_default_for_empty_or_parent_path(self):
        self.assertEqual(sanitize_path_part("..", "Outputs"), "Outputs")
        self.assertEqual(sanitize_path_part("   ", "EOA"), "EOA")

    def test_preset_from_settings_captures_user_options(self):
        preset = preset_from_settings(
            {
                "position": KHMER_POSITIONS["center"],
                "logo_size": 25,
                "opacity": 0.4,
                "m_top": 1,
                "m_bottom": 2,
                "m_left": 3,
                "m_right": 4,
                "folder_path": "C:/DoNotStore",
                "logo_path": "C:/logo.png",
                "output": {"format": "WebP", "quality": 88, "name_prefix": "EOA", "folder_name": "Ready"},
                "adjustments": {"brightness": 10, "rotation": 90, "auto": 1},
            }
        )

        self.assertEqual(preset["position"], KHMER_POSITIONS["center"])
        self.assertEqual(preset["logo_path"], "C:/logo.png")
        self.assertNotIn("folder_path", preset)
        self.assertEqual(preset["output"]["format"], "WebP")
        self.assertEqual(preset["output"]["quality"], 85)
        self.assertEqual(preset["output"]["name_prefix"], "EOA")
        self.assertEqual(preset["adjustments"]["brightness"], 10)
        self.assertEqual(preset["adjustments"]["rotation"], 90)
        self.assertEqual(preset["adjustments"]["auto"], 1)

    def test_preset_margins_are_clamped_to_200(self):
        preset = preset_from_settings({"m_top": 500, "m_bottom": 300, "m_left": 201, "m_right": 200})

        self.assertEqual(preset["m_top"], 200)
        self.assertEqual(preset["m_bottom"], 200)
        self.assertEqual(preset["m_left"], 200)
        self.assertEqual(preset["m_right"], 200)

    def test_khmer_digit_display_helpers_round_trip(self):
        self.assertEqual(to_khmer_digits("100 / 200"), "១០០ / ២០០")
        self.assertEqual(from_khmer_digits("១០០"), "100")

    def test_config_save_load_round_trip_uses_config_file(self):
        with TemporaryDirectory() as temp_dir:
            original_config_file = logo_core.CONFIG_FILE
            logo_core.CONFIG_FILE = Path(temp_dir) / "config.json"
            try:
                saved = save_config(
                    {
                        "logo_path": "C:/logo.png",
                        "position": KHMER_POSITIONS["center"],
                        "logo_size": 20,
                        "opacity": 0.5,
                        "m_top": 1,
                        "m_bottom": 2,
                        "m_left": 3,
                        "m_right": 4,
                        "output": {"format": "PNG", "quality": 90, "name_prefix": "EOA", "folder_name": "Ready"},
                        "presets": {},
                        "selected_preset": "",
                    }
                )

                loaded = load_config()
            finally:
                logo_core.CONFIG_FILE = original_config_file

            self.assertTrue(saved)
            self.assertEqual(loaded["position"], KHMER_POSITIONS["center"])
            self.assertEqual(loaded["output"]["format"], "PNG")
            self.assertEqual(loaded["output"]["folder_name"], "Ready")

    def test_error_summary_lists_failed_files(self):
        summary = build_error_summary([{"file": "a.jpg", "error": "bad file"}, {"file": "b.png", "error": "locked"}])

        self.assertIn("a.jpg - bad file", summary)
        self.assertIn("b.png - locked", summary)

    def test_normalize_selected_image_paths_keeps_only_dropped_files(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            same_parent = root / "inputs"
            other_parent = root / "other"
            same_parent.mkdir()
            other_parent.mkdir()

            kept_a = same_parent / "a.png"
            kept_b = same_parent / "b.jpg"
            ignored_text = same_parent / "note.txt"
            ignored_other_parent = other_parent / "c.png"

            for path in (kept_a, kept_b, ignored_other_parent):
                path.write_bytes(b"img")
            ignored_text.write_text("x", encoding="utf-8")

            result = normalize_selected_image_paths([kept_a, ignored_text, kept_b, ignored_other_parent, kept_a])

            self.assertEqual(result, [kept_a, kept_b])


if __name__ == "__main__":
    unittest.main()
    auto_adjust_image,
