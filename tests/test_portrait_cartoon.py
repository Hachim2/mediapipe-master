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
from portrait_cartoon import crop_face, save_portrait, prepare_print_image, print_png


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
            printable_bytes = (page.parent / "tirage.png").read_bytes()
            self.assertIn(base64.b64encode(printable_bytes).decode("ascii"), html)
            self.assertIn("window.print()", html)
            self.assertIn("@page { size: 100mm 148mm", html)
            self.assertNotIn("<h1>", html)
            printable = cv2.imdecode(np.frombuffer(printable_bytes, np.uint8), 1)
            self.assertEqual(printable.shape, (1748, 1181, 3))
        np.testing.assert_array_equal(self.frame, original)

    def test_fit_preserves_whole_image_and_aspect_ratio(self):
        for width, height in ((400, 200), (200, 400), (400, 400)):
            with self.subTest(size=(width, height)):
                source = np.full((height, width, 3), (20, 80, 150), np.uint8)
                result = prepare_print_image(source, 4)
                ys, xs = np.where(np.any(result != 255, axis=2))
                actual_w, actual_h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
                self.assertAlmostEqual(actual_w / actual_h, width / height, delta=0.003)
                margin = round(4 * 300 / 25.4)
                self.assertGreaterEqual(xs.min(), margin)
                self.assertGreaterEqual(ys.min(), margin)
                self.assertGreaterEqual(1180 - xs.max(), margin)
                self.assertGreaterEqual(1747 - ys.max(), margin)
                np.testing.assert_array_equal(result[ys.min(), xs.min()], source[0, 0])
                np.testing.assert_array_equal(result[ys.max(), xs.max()], source[-1, -1])

    def test_invalid_margin_is_rejected(self):
        for margin in (-1, 50, float("nan")):
            with self.subTest(margin=margin), self.assertRaises(ValueError):
                prepare_print_image(self.frame, margin)

    def test_png_resolution_metadata(self):
        import struct
        png = print_png(self.frame)
        index = png.index(b"pHYs")
        self.assertEqual(struct.unpack(">IIB", png[index + 4:index + 13]), (11811, 11811, 1))


if __name__ == "__main__":
    unittest.main()
