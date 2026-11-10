import re
import time

import cv2
import numpy as np
import pytesseract

import config as c
import ocr_utils as utils
from logger import log_message
from settings import get_setting

VALID_STACK_MAX_VALUES = frozenset({20, 30, 40})

OCR_DIGIT_TRANSLATION = str.maketrans({
    "O": "0", "o": "0",
    "I": "1", "l": "1", "!": "1", "i": "1",
    "B": "8",
    "S": "5", "s": "5",
    "g": "9", "q": "9",
    "\\": "/", "-": "/", "|": "/",
})

STACK_RATIO_PATTERN = re.compile(r"\b(\d{1,3})\s*[/|\\\-]\s*(\d{2})\b")

OCR_COLOR_RANGES = tuple(
    (np.asarray(lo, dtype=np.uint8), np.asarray(hi, dtype=np.uint8))
    for lo, hi in (
        (c.replica_l_hsv, c.replica_u_hsv),
        (c.rare_l_hsv, c.rare_u_hsv),
        (c.currency_l_hsv, c.currency_u_hsv),
        (c.scarab_l_hsv, c.scarab_u_hsv),
        (c.enchant_l_hsv, c.enchant_u_hsv),
    )
)


def get_ocr_bbox(poe_bbox):
    left, top, right, bottom = poe_bbox

    width = right - left
    height = bottom - top

    region_left = float(get_setting("Application", "ocr_region_left", c.DEFAULT_OCR_REGION_LEFT))

    region_top = float(get_setting("Application", "ocr_region_top", c.DEFAULT_OCR_REGION_TOP))

    region_right = float(get_setting("Application", "ocr_region_right", c.DEFAULT_OCR_REGION_RIGHT))

    region_bottom = float(get_setting("Application", "ocr_region_bottom", c.DEFAULT_OCR_REGION_BOTTOM))

    return (
        left + int(width * region_left),
        top + int(height * region_top),
        left + int(width * region_right),
        top + int(height * region_bottom)
    )


#############################################################################
# Experimental Shine Removal & Readability improvements for                 #
# HDR Curio Tracking                                                        #
#############################################################################
def hdr_remove_shine(image_np):
    if image_np.shape[-1] == 4:
        image_np = cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)

    hsv = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)

    hue, sat, val = cv2.split(hsv)

    height, width = val.shape

    kernel = int(min(height, width) * 0.05)
    kernel = max(31, min(kernel, 61))

    if kernel % 2 == 0:
        kernel += 1

    bg = cv2.GaussianBlur(val, (kernel, kernel), 0)

    shine = cv2.subtract(val, bg)

    val_float = val.astype(np.float32)

    mask = (shine > 210) & (val > 240)

    val_float[mask] *= 0.90

    val = np.clip(val_float, 0, 255).astype(np.uint8)

    hsv = cv2.merge((hue, sat, val))

    rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    clahe = cv2.createCLAHE(
        clipLimit=1.5,
        tileGridSize=(8, 8)
    )

    gray = clahe.apply(gray)
    if c.OCR_DEBUGGING:
        cv2.imwrite("shine_mask.png", mask.astype(np.uint8) * 255)
        log_message(
            "VAL:",
            val.min(),
            val.max(),
            "SHINE:",
            shine.min(),
            shine.max(),
            "PERCENTILES:",
            np.percentile(shine, [90, 95, 99, 99.9])
        )
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)


#############################################################
# Saves the information on the screen based on colors       #
# which is afterwards extracted as text                     #
#############################################################
def filter_item_text(image_np, fullscreen=False):
    t0 = time.perf_counter()

    # Convert RGB straight to HSV (no intermediate BGR step).
    hsv = cv2.cvtColor(image_np, cv2.COLOR_RGB2HSV)
    t2 = time.perf_counter()

    combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)

    mask_start = time.perf_counter()

    for lo, hi in OCR_COLOR_RANGES:
        current_mask = cv2.inRange(hsv, lo, hi)
        cv2.bitwise_or(combined_mask, current_mask, dst=combined_mask)

    mask_end = time.perf_counter()

    # No morphological close: a 1x1 kernel would be a no-op.
    t3 = time.perf_counter()

    if c.OCR_DEBUGGING:
        img_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
        contours, _ = cv2.findContours(
            combined_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        debug_image = cv2.bitwise_and(
            img_bgr,
            img_bgr,
            mask=combined_mask
        )
        cv2.drawContours(debug_image, contours, -1, (0, 0, 255), 1)
        cv2.imwrite("ocr_debug_highlighted.png", debug_image)

    t4 = time.perf_counter()

    result = cv2.cvtColor(
        combined_mask,
        cv2.COLOR_GRAY2RGB
    )

    t5 = time.perf_counter()

    if c.DEBUGGING:
        log_message(
            f"[FILTER PERF] "
            f"rgb_to_hsv={(t2 - t0) * 1000:.1f}ms | "
            f"color_masks={(mask_end - mask_start) * 1000:.1f}ms | "
            f"ocr_debug={(t4 - t3) * 1000:.1f}ms | "
            f"gray_to_rgb={(t5 - t4) * 1000:.1f}ms | "
            f"total={(t5 - t0) * 1000:.1f}ms"
        )

    return result


#############################################################################
# Runs OCR on the given image array and returns title-cased text.           #
#                                                                           #
#    Args:                                                                  #
#        image_np (np.ndarray): The image as a NumPy array (RGB).           #
#        scale (int): Scale factor for resizing before OCR.                 #
#        psm (int): Page segmentation mode for Tesseract.                   #
#        lang (str): Language for Tesseract OCR.                            #
#        apply_filter (bool): Whether to run filter_item_text() first.      #
#                                                                           #
#    Returns:                                                               #
#        str: The OCR'd text in smart title case.                           #
#############################################################################
#############################################################
# HDR shine removal (if enabled) + color filtering.         #
# Returns (processed_image, filtered_mask) so the mask can  #
# be reused by the failed-capture review pass.              #
#############################################################
def prepare_ocr_mask(image_np):
    if c.IS_HDR_ENABLED:
        image_np = hdr_remove_shine(image_np)

        if c.OCR_DEBUGGING:
            cv2.imwrite(
                "hdr_fixed.png",
                cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
            )

    image_np_filtered = filter_item_text(image_np)

    if c.OCR_DEBUGGING:
        cv2.imwrite(
            "filtered.png",
            cv2.cvtColor(image_np_filtered, cv2.COLOR_RGB2BGR)
        )

    return image_np, image_np_filtered


def ocr_from_image(image_np, scale=1, psm=6, lang="eng", apply_filter=True, prepared_mask=None):
    t0 = time.perf_counter()

    if apply_filter and prepared_mask is not None:
        image_np_filtered = prepared_mask
        t1 = t0
        t2 = time.perf_counter()
    elif apply_filter:
        image_np, image_np_filtered = prepare_ocr_mask(image_np)
        t1 = t0
        t2 = time.perf_counter()
    else:
        image_np_filtered = image_np
        t1 = t0
        t2 = t0

    if scale != 1:
        image_np_filtered = cv2.resize(
            image_np_filtered,
            (
                int(image_np_filtered.shape[1]) * scale,
                int(image_np_filtered.shape[0]) * scale
            ),
            # LANCZOS4 gives smoother glyph edges than INTER_NEAREST, which
            # noticeably improves Tesseract accuracy on the upscaled mask.
            interpolation=cv2.INTER_LANCZOS4
        )

    t3 = time.perf_counter()

    if c.DEBUGGING:
        h, w = image_np_filtered.shape[:2]

        gray = cv2.cvtColor(
            image_np_filtered,
            cv2.COLOR_RGB2GRAY
        )

        nonzero = cv2.countNonZero(gray)
        total_pixels = w * h
        density = (nonzero / total_pixels * 100) if total_pixels else 0

        log_message(
            f"[OCR INPUT] "
            f"size={w}x{h} | "
            f"pixels={total_pixels:,} | "
            f"nonzero={nonzero:,} | "
            f"density={density:.2f}% | "
            f"psm={psm} | "
            f"scale={scale}"
        )

    tess_config = f"--psm {psm}"
    tess_input = image_np_filtered

    #############################################################
    # Experimental: hand Tesseract black-on-white text and skip #
    # its own inversion check. See OCR_INVERT_FOR_TESSERACT.    #
    #############################################################
    if apply_filter and c.OCR_INVERT_FOR_TESSERACT:
        tess_input = cv2.bitwise_not(image_np_filtered)
        tess_config += " -c tessedit_do_invert=0"

    text = pytesseract.image_to_string(
        tess_input,
        config=tess_config,
        lang=lang
    )

    t4 = time.perf_counter()

    if c.DEBUGGING:
        lines = text.splitlines()

        log_message(
            f"[OCR RESULT] "
            f"chars={len(text)} | "
            f"lines={len(lines)} | "
            f"nonempty_lines={sum(bool(line.strip()) for line in lines)}"
        )

    formatted_text = utils.smart_title_case(text)

    t5 = time.perf_counter()

    if c.DEBUGGING:
        log_message(
            f"[OCR PERF] "
            f"hdr+filter={(t2 - t0) * 1000:.1f}ms"
            f"{' (reused)' if prepared_mask is not None else ''} | "
            f"resize={(t3 - t2) * 1000:.1f}ms | "
            f"tesseract={(t4 - t3) * 1000:.1f}ms | "
            f"title_case={(t5 - t4) * 1000:.1f}ms | "
            f"total={(t5 - t0) * 1000:.1f}ms"
        )

    if c.DEBUGGING:
        log_message(
            "Filtered image stats:",
            image_np_filtered.min(),
            image_np_filtered.max()
        )

        if c.OCR_DEBUGGING:
            cv2.namedWindow("Filtered Mask", cv2.WINDOW_NORMAL)
            cv2.imshow("Filtered Mask", image_np_filtered)
            cv2.moveWindow("Filtered Mask", 100, 100)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    return formatted_text, image_np


####################################################################
# Checks for a match of x/y and if currency applies the stack size #
####################################################################
def extract_currency_value(lines, title_lines, matched_term, term_types):
    if term_types.get(matched_term) not in {c.CURRENCY_TYPE, c.SCARAB_TYPE}:
        return None

    matched_title = matched_term.title()
    idx = next((i for i, line in enumerate(title_lines) if matched_title in line), None)
    if idx is None:
        return None

    # Search current and next 2 lines
    for j in range(idx, min(idx + 3, len(lines))):
        line = lines[j].translate(OCR_DIGIT_TRANSLATION)

        # Match flexible patterns like 19/20, 19 / 20, 19|20, etc.
        match = STACK_RATIO_PATTERN.search(line)
        if match:
            raw_current, raw_max = match.groups()

            try:
                current = int(raw_current)
                maximum = int(raw_max)
            except ValueError:
                continue

            if maximum in VALID_STACK_MAX_VALUES and 0 <= current <= maximum:
                return current, maximum

            # Fallback fix: take last digit of current if it's obviously wrong
            if maximum in VALID_STACK_MAX_VALUES:
                current_last = int(str(current)[-1])
                if current_last <= maximum:
                    return current_last, maximum

    return 1, 20
