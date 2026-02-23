import unittest

from app.core.config import settings
from app.services.file_service import FileService


class TestDataPathAccess(unittest.TestCase):
    def test_append_token_when_data_protected(self):
        original_auth_enabled = settings.API_AUTH_ENABLED
        original_public_access = settings.DATA_PUBLIC_ACCESS
        original_token = settings.API_AUTH_TOKEN
        try:
            settings.API_AUTH_ENABLED = True
            settings.DATA_PUBLIC_ACCESS = False
            settings.API_AUTH_TOKEN = "demo_token"
            self.assertEqual(
                FileService.to_public_data_path("data/uploads/demo.mp4"),
                "/data/uploads/demo.mp4?api_token=demo_token",
            )
        finally:
            settings.API_AUTH_ENABLED = original_auth_enabled
            settings.DATA_PUBLIC_ACCESS = original_public_access
            settings.API_AUTH_TOKEN = original_token

    def test_no_token_when_public_access_enabled(self):
        original_auth_enabled = settings.API_AUTH_ENABLED
        original_public_access = settings.DATA_PUBLIC_ACCESS
        original_token = settings.API_AUTH_TOKEN
        try:
            settings.API_AUTH_ENABLED = True
            settings.DATA_PUBLIC_ACCESS = True
            settings.API_AUTH_TOKEN = "demo_token"
            self.assertEqual(
                FileService.to_public_data_path("data/uploads/demo.mp4"),
                "/data/uploads/demo.mp4",
            )
        finally:
            settings.API_AUTH_ENABLED = original_auth_enabled
            settings.DATA_PUBLIC_ACCESS = original_public_access
            settings.API_AUTH_TOKEN = original_token


if __name__ == "__main__":
    unittest.main()
