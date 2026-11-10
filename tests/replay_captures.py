"""
Replays saved capture images through the real OCR -> matching pipeline.

Usage (from the project root):
    python tests/replay_captures.py                 # all images in tests/captures
    python tests/replay_captures.py path/to/folder  # another folder
    python tests/replay_captures.py --compare-invert

Optional expectations file: <folder>/expected.json
    {"capture_2026-11-10_21-03-11_123.png": ["Infernal Blade"],
     "storm_beak.png": []}
Images not listed still run; their results are printed as "(no expectation)".
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import cv2

import config as c
import ocr_utils as utils
from set_tesseract_path import set_tesseract_path

set_tesseract_path()

from tracking.ocr_capture import ocr_from_image, prepare_ocr_mask
from tracking.term_matching import PRECOMP_TERMS, get_matched_terms, review_failed_capture

# Fail fast if the app module can't resolve the functions capture_once calls.
import curio_tracker  # noqa: E402
assert callable(getattr(curio_tracker, "review_failed_capture", None)), \
    "curio_tracker is missing the review_failed_capture import"

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp")


def run_pipeline(image_rgb):
    """Mirrors curio_tracker.capture_once + review_failed_capture, without saving."""
    timings = {}
    t0 = time.perf_counter()
    _, mask = prepare_ocr_mask(image_rgb)
    t1 = time.perf_counter()
    text, _ = ocr_from_image(image_rgb, prepared_mask=mask)
    t2 = time.perf_counter()
    matched = get_matched_terms(text, allow_dupes=True)
    stage = "exact"
    rejected = []

    if not matched:
        # Call the real review function (as capture_once does) so the
        # harness exercises the same code path as the app.
        text, matched = review_failed_capture(
            image_rgb, scale=2, allow_dupes=True, prepared_mask=mask
        )
        # Re-derive which review stage matched, for reporting only.
        if not matched:
            stage = "none"
        elif get_matched_terms(text, allow_dupes=True):
            stage = "review-exact"
        else:
            stage = "review-fuzzy"
        utils.find_review_fuzzy_terms(text, PRECOMP_TERMS, rejected=rejected)
    t3 = time.perf_counter()

    timings["filter"] = (t1 - t0) * 1000
    timings["ocr1"] = (t2 - t1) * 1000
    timings["total"] = (t3 - t0) * 1000
    terms = sorted({m["term"] for m in matched})
    return terms, stage, rejected, text, timings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default=c.RAW_CAPTURES_DIR)
    parser.add_argument("--compare-invert", action="store_true",
                        help="run each image with OCR_INVERT_FOR_TESSERACT off and on")
    parser.add_argument("--show-text", action="store_true", help="print OCR text per image")
    parser.add_argument("--write-expected", action="store_true",
                        help="write current results for unlabeled images into expected.json")
    args = parser.parse_args()

    if not os.path.isdir(args.folder):
        print(f"No folder: {args.folder}")
        return 1

    expected = {}
    exp_path = os.path.join(args.folder, "expected.json")
    if os.path.exists(exp_path):
        with open(exp_path, encoding="utf-8") as f:
            expected = json.load(f)

    images = sorted(n for n in os.listdir(args.folder) if n.lower().endswith(IMAGE_EXTS))
    if not images:
        print(f"No images in {args.folder}")
        return 1

    new_expected = {}
    modes = [False, True] if args.compare_invert else [c.OCR_INVERT_FOR_TESSERACT]
    stats = {m: {"pass": 0, "fail": 0, "ocr1": 0.0, "total": 0.0} for m in modes}

    for name in images:
        bgr = cv2.imread(os.path.join(args.folder, name))
        if bgr is None:
            print(f"[SKIP] {name}: unreadable")
            continue
        image_rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        print(f"\n=== {name} ({image_rgb.shape[1]}x{image_rgb.shape[0]})")

        for invert in modes:
            c.OCR_INVERT_FOR_TESSERACT = invert
            terms, stage, rejected, text, t = run_pipeline(image_rgb)
            s = stats[invert]
            s["ocr1"] += t["ocr1"]
            s["total"] += t["total"]

            if args.write_expected and name not in expected and invert == modes[0]:
                new_expected[name] = terms

            if name in expected:
                ok = sorted(expected[name]) == terms
                s["pass" if ok else "fail"] += 1
                verdict = "PASS" if ok else f"FAIL (expected {sorted(expected[name])})"
            else:
                verdict = "(no expectation)"

            label = f"invert={'on ' if invert else 'off'} " if args.compare_invert else ""
            print(f"  {label}{verdict} | matched={terms} | via={stage} | "
                  f"filter={t['filter']:.0f}ms ocr={t['ocr1']:.0f}ms total={t['total']:.0f}ms")
            for r in rejected:
                print(f"      rejected '{r['term']}' ~ '{r['candidate']}' "
                      f"{r['similarity']:.3f} ({r['reason']})")
            if args.show_text:
                print("      " + text.strip().replace("\n", "\n      "))

    if new_expected:
        merged = {**expected, **new_expected}
        with open(exp_path, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(merged.items())), f, indent=2)
        print(f"\nWrote {len(new_expected)} new expectation(s) to {exp_path} -- review them!")

    n = len(images)
    print("\n=== Summary")
    for invert, s in stats.items():
        label = f"invert={'on ' if invert else 'off'} " if args.compare_invert else ""
        print(f"  {label}pass={s['pass']} fail={s['fail']} unlabeled={n - s['pass'] - s['fail']} | "
              f"avg first-OCR={s['ocr1'] / n:.0f}ms avg total={s['total'] / n:.0f}ms")

    return 1 if any(s["fail"] for s in stats.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
