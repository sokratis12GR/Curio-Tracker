"""End-to-end OCR check: real Tesseract on a real capture, then the exact term matcher."""
import os
import shutil
import sys
import unittest

import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pytesseract

EXAMPLE_IMAGE = os.path.join(ROOT, "assets", "ocr_example.jpeg")


def _find_tesseract():
    on_path = shutil.which("tesseract")
    if on_path:
        return on_path
    bundled = os.path.join(ROOT, "tesseract", "tesseract.exe" if sys.platform == "win32" else "tesseract")
    return bundled if os.path.isfile(bundled) else None


TESSERACT = _find_tesseract()


@unittest.skipUnless(TESSERACT, "Tesseract is not installed")
class OcrPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT
        tessdata = os.path.join(os.path.dirname(TESSERACT), "tessdata")
        if os.path.isdir(tessdata):
            os.environ["TESSDATA_PREFIX"] = tessdata

        from tracking.ocr_capture import ocr_from_image
        from tracking import term_matching

        image = cv2.cvtColor(cv2.imread(EXAMPLE_IMAGE), cv2.COLOR_BGR2RGB)
        cls.full_text, _ = ocr_from_image(image)
        cls.terms = {m["term"] for m in term_matching.get_matched_terms(cls.full_text, allow_dupes=True)}

    def test_tesseract_produces_text(self):
        self.assertIn("orb of scouring", self.full_text.lower())

    def test_known_curio_is_matched(self):
        self.assertIn("orb of scouring", {t.lower() for t in self.terms}, sorted(self.terms))


if __name__ == "__main__":
    unittest.main()
