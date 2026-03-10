import unittest

from app.api.tasks import get_processing_config_meta
from app.schemas.task import ProcessTaskResponse
from app.services.processing_param_specs import (
    PROCESSING_PARAM_SPECS,
    build_processing_config_meta,
)
from app.services.quality_tuning import DEFAULT_QUALITY_CONFIG, _normalize_quality_config


class TestProcessingParamSpecs(unittest.TestCase):
    def test_default_quality_config_is_derived_from_specs(self):
        expected = {key: spec["default"] for key, spec in PROCESSING_PARAM_SPECS.items()}
        self.assertEqual(DEFAULT_QUALITY_CONFIG, expected)

    def test_pyscenedetect_specs_must_have_source_ref(self):
        missing = [
            key
            for key, spec in PROCESSING_PARAM_SPECS.items()
            if spec.get("provenance") == "pyscenedetect" and not spec.get("source_ref")
        ]
        self.assertEqual(missing, [])

    def test_normalize_quality_config_uses_spec_bounds(self):
        config = dict(DEFAULT_QUALITY_CONFIG)
        config.update(
            {
                "scene_threshold": 999.0,
                "adaptive_threshold": -10.0,
                "adaptive_min_content_val": 300.0,
                "adaptive_frame_window": 0,
                "min_scene_len_frames": -50,
                "downscale": -3,
                "threshold_detector_threshold": 999.0,
                "threshold_detector_fade_bias": -500.0,
            }
        )

        normalized = _normalize_quality_config(config)
        self.assertEqual(normalized["scene_threshold"], 255.0)
        self.assertEqual(normalized["adaptive_threshold"], 0.0)
        self.assertEqual(normalized["adaptive_min_content_val"], 255.0)
        self.assertEqual(normalized["adaptive_frame_window"], 1)
        self.assertEqual(normalized["min_scene_len_frames"], 0)
        self.assertEqual(normalized["downscale"], 0)
        self.assertEqual(normalized["threshold_detector_threshold"], 255.0)
        self.assertEqual(normalized["threshold_detector_fade_bias"], -100.0)

    def test_processing_config_meta_contains_range_and_defaults(self):
        meta = build_processing_config_meta()
        self.assertIn("defaults", meta)
        self.assertIn("fields", meta)
        self.assertIn("groups", meta)

        field_map = {field["key"]: field for field in meta["fields"]}
        self.assertEqual(meta["defaults"]["scene_threshold"], 27.0)
        self.assertEqual(field_map["scene_threshold"]["min"], 0.0)
        self.assertEqual(field_map["scene_threshold"]["max"], 255.0)
        self.assertNotIn("recommended_range", field_map["scene_threshold"])

    def test_detailed_parameters_are_visible(self):
        meta = build_processing_config_meta()
        field_map = {field["key"]: field for field in meta["fields"]}
        for key in (
            "weight_hue",
            "weight_sat",
            "weight_lum",
            "weight_edges",
            "detector",
            "detection_mode",
            "use_transnet",
            "use_threshold_detector",
            "split_copy_mode",
        ):
            self.assertTrue(field_map[key]["ui_visible"], key)

        # Visible numeric detailed fields should include UI metadata used by modal rendering.
        for key in ("weight_hue", "weight_sat", "weight_lum", "weight_edges"):
            self.assertIsNotNone(field_map[key]["group"], key)
            self.assertIsNotNone(field_map[key]["label"], key)

    def test_api_route_returns_processing_meta(self):
        api_meta = get_processing_config_meta()
        service_meta = build_processing_config_meta()
        self.assertEqual(api_meta["version"], service_meta["version"])
        self.assertEqual(api_meta["defaults"], service_meta["defaults"])

    def test_process_task_response_accepts_config_meta(self):
        payload = ProcessTaskResponse(
            status="QUEUED",
            job_id="job-1",
            resolved_config={"scene_threshold": 27.0},
            config_meta={"version": "test"},
        )
        dumped = payload.model_dump()
        self.assertIn("config_meta", dumped)
        self.assertEqual(dumped["config_meta"]["version"], "test")


if __name__ == "__main__":
    unittest.main()
