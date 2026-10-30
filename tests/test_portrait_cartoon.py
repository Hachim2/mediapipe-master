"""Verifications des captures et exports sans camera ni navigateur."""

import base64
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portrait_cartoon import crop_face, save_portrait


class PortraitTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.full((120, 160, 3), 190, dtype=np.uint8)
        self.points = [SimpleNamespace(x=0.3, y=0.2), SimpleNamespace(x=0.7, y=0.8)]

    def test_missing_or_invalid_face_is_rejected(self):
        for points in (None, [], [SimpleNamespace(x=float("nan"), y=0.5)],
                       [SimpleNamespace(x=2, y=2), SimpleNamespace(x=3, y=3)]):
            with self.subTest(points=points), self.assertRaises(ValueError):
                crop_face(self.frame, points)

    def test_crop_clips_at_frame_edges_and_copies_pixels(self):
        points = [SimpleNamespace(x=0, y=0), SimpleNamespace(x=1, y=1)]
        crop = crop_face(self.frame, points)
        self.assertEqual(crop.shape, self.frame.shape)
        crop[:] = 0
        self.assertTrue(np.all(self.frame == 190))

    def test_export_contains_readable_images_and_embedded_print_image(self):
        original = self.frame.copy()
        with tempfile.TemporaryDirectory() as directory:
            page = save_portrait(self.frame, self.points, directory)
            second = save_portrait(self.frame, self.points, directory)
            self.assertNotEqual(page.parent, second.parent)
            photo = cv2.imdecode(np.frombuffer((page.parent / "photo.png").read_bytes(), np.uint8), 1)
            cartoon_bytes = (page.parent / "cartoon.png").read_bytes()
            cartoon = cv2.imdecode(np.frombuffer(cartoon_bytes, np.uint8), 1)
            self.assertIsNotNone(photo)
            self.assertEqual(photo.shape, cartoon.shape)
            html = page.read_text(encoding="utf-8")
            self.assertIn(base64.b64encode(cartoon_bytes).decode("ascii"), html)
            self.assertIn("window.print()", html)
            self.assertIn("@page { size: A4", html)
        np.testing.assert_array_equal(self.frame, original)


if __name__ == "__main__":
    unittest.main()
