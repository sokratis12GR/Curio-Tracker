"""Stack-size reading: real Tesseract on real curio screenshots."""
import os
import shutil
import sys
import unittest

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pytesseract

FIXTURES = os.path.join(ROOT, "tests", "fixtures")

EXPECTED = {
    "stack_sizes_chaos_tailoring.png": {"Chaos Orb": (15, 20), "Tailoring Orb": (1, 20)},
    "stack_sizes_alchemy_instilling.png": {
        "Orb Of Alchemy": (19, 20),
        "Instilling Orb": (18, 20),
        "Tailoring Orb": (1, 20),
    },
}


def _find_tesseract():
    on_path = shutil.which("tesseract")
    if on_path:
        return on_path
    bundled = os.path.join(ROOT, "tesseract", "tesseract.exe" if sys.platform == "win32" else "tesseract")
    return bundled if os.path.isfile(bundled) else None


TESSERACT = _find_tesseract()


@unittest.skipUnless(TESSERACT, "Tesseract is not installed")
class StackSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT
        tessdata = os.path.join(os.path.dirname(TESSERACT), "tessdata")
        if os.path.isdir(tessdata):
            os.environ["TESSDATA_PREFIX"] = tessdata

    def test_stack_sizes_read_below_titles(self):
        from tracking.ocr_capture import extract_stack_sizes

        for name, expected in EXPECTED.items():
            with self.subTest(image=name):
                image = cv2.cvtColor(cv2.imread(os.path.join(FIXTURES, name)), cv2.COLOR_BGR2RGB)
                self.assertEqual(extract_stack_sizes(image, list(expected)), expected)

    def test_text_fallback_rejects_implausible_ratios(self):
        from tracking.ocr_capture import extract_currency_value
        import config as c

        types = {"Chaos Orb": c.CURRENCY_TYPE}
        lines = ["Chaos Orb", "Stack Size: 116/20"]
        self.assertIsNone(extract_currency_value(lines, tuple(lines), "Chaos Orb", types))

        lines = ["Chaos Orb", "Stack Size: 16/20"]
        self.assertEqual(extract_currency_value(lines, tuple(lines), "Chaos Orb", types), (16, 20))


if __name__ == "__main__":
    unittest.main()
