import re
import time
from difflib import SequenceMatcher

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
STACK_BAND_RATIO_PATTERN = re.compile(r"(\d{1,2})\s*/\s*(20|30|40)\b")

STACK_TEXT_L_HSV = np.array([0, 0, 95], dtype=np.uint8)
STACK_TEXT_U_HSV = np.array([180, 40, 255], dtype=np.uint8)
STACK_BAND_SCALE = 3
TITLE_BOX_MIN_SIMILARITY = 0.8

OCR_COLOR_RANGES = tuple(
    (np.asarray(lo, dtype=np.uint8), np.asarray(hi, dtype=np.uint8))
    for lo, hi in (
        (c.replica_l_hsv, c.replica_u_hsv),
        (c.rare_l_hsv, c.rare_u_hsv),
        (c.currency_l_hsv, c.currency_u_hsv),
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


#############################################################################
# Rebuilds image_to_string-style text from image_to_data output: words      #
# joined by spaces, lines by newlines, blocks/paragraphs by a blank line.   #
#############################################################################
def _text_from_data(data):
    parts = []
    previous = None
    for i, word in enumerate(data["text"]):
        if data["level"][i] != 5:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        if previous is None:
            pass
        elif key != previous:
            parts.append("\n\n" if key[:2] != previous[:2] else "\n")
        else:
            parts.append(" ")
        parts.append(word)
        previous = key
    return "".join(parts) + "\n"


#############################################################################
# Extracts word boxes from image_to_data output, mapped back to the         #
# unscaled image. Each entry: (text, left, top, right, bottom, line_key).   #
#############################################################################
def _words_from_data(data, scale=1):
    words = []
    for i, word in enumerate(data["text"]):
        if data["level"][i] != 5 or not word.strip():
            continue
        left, top = data["left"][i], data["top"][i]
        right, bottom = left + data["width"][i], top + data["height"][i]
        words.append((
            word,
            left // scale, top // scale, right // scale, bottom // scale,
            (data["block_num"][i], data["par_num"][i], data["line_num"][i]),
        ))
    return words


def ocr_from_image(image_np, scale=1, psm=6, lang="eng", apply_filter=True, prepared_mask=None, layout_out=None):
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

    if layout_out is None:
        text = pytesseract.image_to_string(
            tess_input,
            config=tess_config,
            lang=lang
        )
    else:
        data = pytesseract.image_to_data(
            tess_input,
            config=tess_config,
            lang=lang,
            output_type=pytesseract.Output.DICT
        )
        text = _text_from_data(data)
        layout_out.extend(_words_from_data(data, scale))

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
            try:
                cv2.namedWindow("Filtered Mask", cv2.WINDOW_NORMAL)
                cv2.imshow("Filtered Mask", image_np_filtered)
                cv2.moveWindow("Filtered Mask", 100, 100)
                cv2.waitKey(0)
                cv2.destroyAllWindows()
            except cv2.error as e:
                log_message("[DEBUG] OCR preview window unavailable:", e)

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

            if maximum in VALID_STACK_MAX_VALUES and 1 <= current <= maximum:
                return current, maximum

    return None


def _to_rgb(image_np):
    if image_np.ndim == 3 and image_np.shape[-1] == 4:
        return cv2.cvtColor(image_np, cv2.COLOR_RGBA2RGB)
    return image_np


#############################################################################
# Finds the on-screen box of each term's title line from OCR word boxes     #
# (see ocr_from_image's layout_out).                                        #
# Returns {term: [(left, top, right, bottom), ...]} in image coordinates.   #
#############################################################################
def locate_title_boxes(words, terms):
    lines = {}
    for word in words:
        lines.setdefault(word[5], []).append(word)

    boxes = {}
    for term in terms:
        term_words = term.lower().split()
        term_joined = " ".join(term_words)
        found = []
        for line_words in lines.values():
            cleaned = [re.sub(r"[^a-z0-9%']", "", w[0].lower()) for w in line_words]
            for start in range(len(cleaned) - len(term_words) + 1):
                candidate = " ".join(cleaned[start:start + len(term_words)])
                if SequenceMatcher(None, candidate, term_joined).ratio() < TITLE_BOX_MIN_SIMILARITY:
                    continue
                selected = line_words[start:start + len(term_words)]
                left = min(w[1] for w in selected)
                right = max(w[3] for w in selected)
                top = int(np.median([w[2] for w in selected]))
                height = int(np.median([w[4] - w[2] for w in selected]))
                found.append((left, top, right, top + height))
        boxes[term] = found
    return boxes


#############################################################################
# Builds the upscaled black-on-white mask of the neutral-grey band where    #
# "Stack Size: N/MM" sits directly below a title. Returns None if empty.    #
#############################################################################
def _stack_band(image_np, title_box):
    left, top, right, bottom = title_box
    height = bottom - top
    width = right - left
    if height <= 0 or width <= 0:
        return None

    y0 = bottom + int(0.4 * height)
    y1 = min(image_np.shape[0], bottom + int(2.4 * height))
    x0 = max(0, left - width // 2)
    x1 = min(image_np.shape[1], right + width // 2)
    crop = image_np[y0:y1, x0:x1]
    if crop.size == 0:
        return None

    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, STACK_TEXT_L_HSV, STACK_TEXT_U_HSV)
    mask = cv2.resize(mask, None, fx=STACK_BAND_SCALE, fy=STACK_BAND_SCALE, interpolation=cv2.INTER_LANCZOS4)
    return cv2.bitwise_not(mask)


def _parse_stack_ratio(text):
    match = STACK_BAND_RATIO_PATTERN.search(text.translate(OCR_DIGIT_TRANSLATION))
    if not match:
        return None
    current, maximum = int(match.group(1)), int(match.group(2))
    return (current, maximum) if 1 <= current <= maximum else None


#############################################################################
# Reads every stack band in a single Tesseract call: bands are stacked      #
# vertically with white gaps and each OCR'd word is assigned back to its    #
# band by vertical position. Returns one (current, maximum) or None per box.#
#############################################################################
def read_stack_sizes_below(image_np, title_boxes):
    bands = [_stack_band(image_np, box) for box in title_boxes]
    present = [band for band in bands if band is not None]
    if not present:
        return [None] * len(title_boxes)

    gap = 20 * STACK_BAND_SCALE
    sheet_width = max(band.shape[1] for band in present) + 2 * gap
    rows = [np.full((gap, sheet_width), 255, dtype=np.uint8)]
    spans = []
    y = gap
    for band in bands:
        if band is None:
            spans.append(None)
            continue
        row = np.full((band.shape[0], sheet_width), 255, dtype=np.uint8)
        row[:, gap:gap + band.shape[1]] = band
        rows.extend((row, np.full((gap, sheet_width), 255, dtype=np.uint8)))
        spans.append((y, y + band.shape[0]))
        y += band.shape[0] + gap

    data = pytesseract.image_to_data(
        np.vstack(rows),
        config="--psm 6 -c tessedit_do_invert=0",
        output_type=pytesseract.Output.DICT
    )

    band_words = [[] for _ in bands]
    for i, word in enumerate(data["text"]):
        if data["level"][i] != 5 or not word.strip():
            continue
        center = data["top"][i] + data["height"][i] / 2
        for index, span in enumerate(spans):
            if span and span[0] - gap / 2 <= center < span[1] + gap / 2:
                band_words[index].append((data["left"][i], word))
                break

    results = []
    for words in band_words:
        text = " ".join(word for _, word in sorted(words))
        if c.DEBUGGING:
            log_message(f"[Stack Size] band text: {text!r}")
        results.append(_parse_stack_ratio(text))
    return results


#############################################################################
# Reads stack sizes for the given currency/scarab terms by locating each    #
# title and OCR-ing the neutral-grey stack line beneath it.                 #
# `words` should be the layout from the OCR pass that matched the terms;    #
# without it a 1x layout pass is run here.                                  #
# Returns {term: (current, maximum)} for the terms that could be read.      #
#############################################################################
def extract_stack_sizes(image_np, terms, words=None, ocr_mask=None):
    if image_np is None or not terms:
        return {}

    image_np = _to_rgb(image_np)
    if words is None:
        words = []
        ocr_from_image(image_np, prepared_mask=ocr_mask, layout_out=words)

    candidates = [
        (term, box)
        for term, boxes in locate_title_boxes(words, terms).items()
        for box in boxes
    ]
    if not candidates:
        return {}

    ratios = read_stack_sizes_below(image_np, [box for _, box in candidates])

    results = {}
    for (term, _), ratio in zip(candidates, ratios):
        if ratio and term not in results:
            results[term] = ratio
    return results
