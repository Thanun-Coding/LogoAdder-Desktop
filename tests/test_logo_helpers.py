import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from LogoAdder import (
    KHMER_POSITIONS,
    calculate_logo_size,
    calculate_position,
    calculate_scale_anchor,
    detect_image_orientation,
    is_supported_image,
    should_preserve_alpha,
    contained_preview_size,
    is_dialog_confirm_key,
    is_duplicate_preset_name,
    initialize_logo_worker,
    process_logo_task,
    slider_position_from_value,
    slider_value_from_position,
)
from logo_core import (
    DEFAULT_OUTPUT_SETTINGS,
    build_error_summary,
    build_output_path,
    normalize_selected_image_paths,
    normalize_output_settings,
    preset_from_settings,
    unique_output_path,
)


class LogoHelperTests(unittest.TestCase):
    def test_supported_image_extensions_are_case_insensitive(self):
        self.assertTrue(is_supported_image("photo.JPG"))
        self.assertTrue(is_supported_image("poster.webp"))
        self.assertFalse(is_supported_image("notes.txt"))

    def test_logo_size_never_returns_zero_dimensions(self):
        self.assertEqual(calculate_logo_size(3, 3, 2, 1, 5), (1, 1))

    def test_logo_size_keeps_aspect_ratio(self):
        self.assertEqual(calculate_logo_size(2000, 1000, 1000, 400, 10), (200, 80))

    def test_logo_size_uses_longest_edge_for_landscape_and_portrait(self):
        landscape = calculate_logo_size(2000, 1000, 1000, 400, 5)
        portrait = calculate_logo_size(1000, 2000, 1000, 400, 5)

        self.assertEqual(landscape, (100, 40))
        self.assertEqual(portrait, landscape)

    def test_logo_size_scales_proportionally_for_mixed_resolutions(self):
        large = calculate_logo_size(3000, 2000, 1000, 400, 5)
        small = calculate_logo_size(1200, 800, 1000, 400, 5)

        self.assertEqual(large, (150, 60))
        self.assertEqual(small, (60, 24))

    def test_scale_anchor_uses_longest_edge(self):
        self.assertEqual(calculate_scale_anchor(1200, 800), 1200)
        self.assertEqual(calculate_scale_anchor(800, 1200), 1200)

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

    def test_output_settings_are_clamped_and_defaulted(self):
        settings = normalize_output_settings({"format": "bad", "quality": 500, "name_prefix": "", "folder_name": ""})

        self.assertEqual(settings["format"], "Same as source")
        self.assertEqual(settings["quality"], 100)
        self.assertEqual(settings["name_prefix"], "EOA")
        self.assertEqual(settings["folder_name"], "Outputs")

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
            }
        )

        self.assertEqual(preset["position"], KHMER_POSITIONS["center"])
        self.assertEqual(preset["logo_path"], "C:/logo.png")
        self.assertNotIn("folder_path", preset)
        self.assertEqual(preset["output"]["format"], "WebP")
        self.assertEqual(preset["output"]["quality"], 88)
        self.assertEqual(preset["output"]["name_prefix"], "EOA")

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
