import os
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tracking.ocr_capture import OCR_COLOR_RANGES, filter_item_text


def legacy_filter_item_text(image_np):
    """Reference implementation; the production filter must produce identical output."""
    img_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in OCR_COLOR_RANGES:
        cv2.bitwise_or(combined_mask, cv2.inRange(hsv, lo, hi), dst=combined_mask)
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, np.ones((1, 1), np.uint8))
    return cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2RGB)


class FilterEquivalenceTests(unittest.TestCase):
    def test_matches_legacy_on_random_images(self):
        rng = np.random.default_rng(1234)
        for shape in [(50, 80, 3), (311, 517, 3), (720, 716, 3)]:
            img = rng.integers(0, 256, size=shape, dtype=np.uint8)
            np.testing.assert_array_equal(filter_item_text(img), legacy_filter_item_text(img))

    def test_matches_legacy_on_real_screenshots(self):
        folder = os.path.join(os.path.dirname(__file__), "captures")
        if not os.path.isdir(folder):
            self.skipTest("no tests/captures folder")
        for name in os.listdir(folder):
            if name.lower().endswith((".png", ".jpg", ".jpeg")):
                img = cv2.cvtColor(cv2.imread(os.path.join(folder, name)), cv2.COLOR_BGR2RGB)
                np.testing.assert_array_equal(filter_item_text(img), legacy_filter_item_text(img), name)


if __name__ == "__main__":
    unittest.main()
