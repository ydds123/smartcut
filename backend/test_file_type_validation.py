import unittest
from io import BytesIO

from starlette.datastructures import Headers, UploadFile

from app.services.file_service import FileService


def _upload_file(data: bytes, content_type: str, filename: str = "demo.mp4") -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


class TestFileTypeValidation(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_mp4_with_valid_signature(self):
        file = _upload_file(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 256, "video/mp4")
        self.assertTrue(await FileService.validate_video_type(file))
        self.assertEqual(file.file.tell(), 0)

    async def test_rejects_spoofed_mime_without_video_signature(self):
        file = _upload_file(b"#!/bin/bash\necho hello\n", "video/mp4")
        self.assertFalse(await FileService.validate_video_type(file))

    async def test_rejects_container_and_mime_mismatch(self):
        # AVI signature with mp4 MIME should be rejected.
        avi_header = b"RIFF\x24\x80\x00\x00AVI LIST" + b"\x00" * 128
        file = _upload_file(avi_header, "video/mp4", filename="demo.mp4")
        self.assertFalse(await FileService.validate_video_type(file))


if __name__ == "__main__":
    unittest.main()
