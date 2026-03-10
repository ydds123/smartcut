import unittest

from pydantic import ValidationError

from app.schemas.task import SaveReviewDataRequest


class TestSaveReviewDataSchema(unittest.TestCase):
    def test_accepts_valid_scene_ranges(self):
        payload = SaveReviewDataRequest(
            scenes=[
                {"start_ms": 0, "end_ms": 1200},
                {"start_ms": 1200, "end_ms": 2400},
            ]
        )
        self.assertEqual(len(payload.scenes), 2)

    def test_rejects_invalid_scene_range(self):
        with self.assertRaises(ValidationError):
            SaveReviewDataRequest(
                scenes=[
                    {"start_ms": 1000, "end_ms": 1000},
                ]
            )


if __name__ == "__main__":
    unittest.main()
