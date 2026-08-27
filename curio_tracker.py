import json
import os
import platform
import re
import subprocess
import time
import tkinter as tk
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

import cv2
import numpy as np
import pyautogui
import pyperclip
import pytesseract
from PIL import ImageGrab
from termcolor import colored

import config as c
import currency_utils
import ocr_utils as utils
import toasts
from config import data_file_base
from csv_manager import CSVManager
from data_manager import BaseDataManager
from json_manager import JSONManager
from load_utils import get_datasets
from logger import log_message
from ocr_utils import build_parsed_item
from settings import get_setting, set_setting
from win_utils import get_poe_bbox

datasets = get_datasets(force_reload=True)
saved_mode = get_setting("Application", "export_mode", default="CSV").upper()
base = Path(data_file_base)

if saved_mode == "JSON":
    data_mgr = JSONManager(base)
else:
    data_mgr = CSVManager(base)

# default values in case they only run area lvl 83 blueprints
blueprint_area_level = c.default_bp_lvl
blueprint_layout = c.default_bp_area
bp_enchantment = c.SET_BP_ENCHANTMENT_FOR_RUNS

poe_user = c.poe_user
league_version = c.poe_league
duplicate_duration_time = c.time_last_dupe_check_seconds

stack_sizes = {}

non_dup_count = 0
attempt = 1
listener_ref = None
parsed_items = []

MAX_RECENT_TERMS = 5  # keep last 5 entries in memory
recent_terms = []  # list of tuples: (term, datetime)

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


def populate_recent_terms(within_seconds: int = None, max_items: int = None):
    global recent_terms

    max_items = max_items or MAX_RECENT_TERMS
    within_seconds = within_seconds or int(duplicate_duration_time or 60)

    try:
        rows = data_mgr.load_dict()
    except Exception:
        rows = []

    if not rows:
        recent_terms = []
        return

    # Take last max_items rows
    last_rows = rows[-max_items:]
    parsed = []
    now = datetime.now()

    for row in last_rows:
        ts_str = row.get(c.csv_time_header)

        term = None
        for col in (
                c.csv_trinket_header,
                c.csv_replacement_header,
                c.csv_replica_header,
                c.csv_experimented_header,
                c.csv_weapon_enchant_header,
                c.csv_armor_enchant_header,
                c.csv_scarab_header,
                c.csv_currency_header,
        ):
            val = row.get(col)
            if val and val.strip():
                term = utils.smart_title_case(val.strip())
                break

        if not term:
            continue

        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S") if ts_str else None
        except Exception:
            ts = None

        if ts:
            if (now - ts).total_seconds() <= within_seconds:
                parsed.append((term, ts))
        else:
            parsed.append((term, now))

    parsed = parsed[-max_items:]
    recent_terms = parsed.copy()


full_currency = datasets.get("currency") or {}
collection_dataset = datasets.get("collection") or {}


def on_league_change():
    global CURRENCY_DATASET, COLLECTION_DATASET_ACTIVE

    new_league = get_setting("Application", "data_league", c.LEAGUE)
    CURRENCY_DATASET = full_currency.get(new_league, {})

    divine_item = CURRENCY_DATASET.get("Divine Orb")
    if divine_item:
        divine_chaos = currency_utils.convert_to_float(divine_item.get("chaos", 0))
        set_setting("Application", "divine_equivalent", divine_chaos)
        log_message(f"[DEBUG] Stored divine equivalence for {new_league}: {divine_chaos} Chaos")
    else:
        log_message(f"[DEBUG] No Divine Orb found for league {new_league}")

    poeladder_identifier = get_setting("Application", "poeladder_league_identifier", c.FIXED_LADDER_IDENTIFIER)
    poeladder_display_name = get_setting("Application", "poeladder_ggg_league", poeladder_identifier)

    league_collection = collection_dataset.get(poeladder_identifier, {})
    COLLECTION_DATASET_ACTIVE = {term: data.get("owned", False) for term, data in league_collection.items()}

    log_message(
        f"League changed to poe.ninja: {new_league} | poeladder: {poeladder_display_name} ({poeladder_identifier})")

    if c.DEBUGGING:
        log_message(f"DataSet Keys: {collection_dataset.keys()}")
        log_message(f"Collections: {league_collection.items()}")
        log_message(f"Collection Active {COLLECTION_DATASET_ACTIVE.items()}")
        log_currency_dataset(CURRENCY_DATASET)
        log_message(f"[DEBUG] Loaded {len(COLLECTION_DATASET_ACTIVE)} curios for {new_league}")


def log_currency_dataset(dataset):
    if not dataset:
        log_message("[DEBUG] CURRENCY_DATASET is empty or None!")
        return

    log_message(f"[DEBUG] CURRENCY_DATASET contains {len(dataset)} entries:")
    for term, values in dataset.items():
        # Convert values to JSON string for readable logging
        values_str = json.dumps(values, ensure_ascii=False)
        log_message(f"  - {term}: {values_str}")


CURRENCY_DATASET = {}
COLLECTION_DATASET_ACTIVE = {}

TIERS_DATASET = datasets["tiers"]
experimental_items = datasets["experimental"]
term_types = datasets["terms"]
all_terms = set(term_types.keys())
body_armors = datasets["body_armors"]
owned_items = {}
PRECOMP_TERMS = []
for term in all_terms:
    cleaned = utils.remove_possessive_s(term)
    normalized_term = utils.normalize_for_search(cleaned)
    term_type = term_types.get(term, "")
    term_type_cmp = utils.smart_title_case(term_type) if isinstance(term_type, str) else ""
    enchant_parts = None

    if ";" in cleaned and term_type_cmp in (c.ARMOR_ENCHANT_TYPE, c.WEAPON_ENCHANT_TYPE):
        enchant_parts = tuple(
            utils.normalize_for_search(utils.smart_title_case(part.strip()))
            for part in cleaned.split(";", 1)
        )

    PRECOMP_TERMS.append((
        term,
        normalized_term,
        enchant_parts
    ))


def build_enchant_type_lookup(term_types):
    lookup = defaultdict(set)
    for raw_term, type_name in term_types.items():
        norm = utils.normalize_for_search(utils.smart_title_case(raw_term))  # full term
        lookup[norm].add(type_name)
    return lookup


enchant_type_lookup = build_enchant_type_lookup(term_types)


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
def ocr_from_image(image_np, scale=1, psm=6, lang="eng", apply_filter=True):
    t0 = time.perf_counter()

    if apply_filter:
        if c.IS_HDR_ENABLED:
            image_np = hdr_remove_shine(image_np)

            if c.OCR_DEBUGGING:
                cv2.imwrite(
                    "hdr_fixed.png",
                    cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
                )

        t1 = time.perf_counter()

        image_np_filtered = filter_item_text(image_np)

        t2 = time.perf_counter()

        if c.OCR_DEBUGGING:
            cv2.imwrite(
                "filtered.png",
                cv2.cvtColor(image_np_filtered, cv2.COLOR_RGB2BGR)
            )
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

    text = pytesseract.image_to_string(
        image_np_filtered,
        config=f"--psm {psm}",
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
            f"HDR={(t1 - t0) * 1000:.1f}ms | "
            f"filter={(t2 - t1) * 1000:.1f}ms | "
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

    img_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
    t1 = time.perf_counter()

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    t2 = time.perf_counter()

    combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)

    mask_start = time.perf_counter()

    for lo, hi in OCR_COLOR_RANGES:
        current_mask = cv2.inRange(hsv, lo, hi)
        cv2.bitwise_or(combined_mask, current_mask, dst=combined_mask)

    mask_end = time.perf_counter()

    kernel = np.ones((1, 1), np.uint8)
    combined_mask = cv2.morphologyEx(
        combined_mask,
        cv2.MORPH_CLOSE,
        kernel
    )

    t3 = time.perf_counter()

    if c.OCR_DEBUGGING:
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
            f"rgb_to_bgr={(t1 - t0) * 1000:.1f}ms | "
            f"bgr_to_hsv={(t2 - t1) * 1000:.1f}ms | "
            f"color_masks={(mask_end - mask_start) * 1000:.1f}ms | "
            f"morph={(t3 - mask_end) * 1000:.1f}ms | "
            f"ocr_debug={(t4 - t3) * 1000:.1f}ms | "
            f"gray_to_rgb={(t5 - t4) * 1000:.1f}ms | "
            f"total={(t5 - t0) * 1000:.1f}ms"
        )

    return result


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


#################################################
# Check if a term or combo term is in the text. #
#################################################
def is_term_match(normalized_term, normalized_lines, enchant_parts=None) -> bool:
    # --- Handle Enchant Combos ---
    if enchant_parts is not None:
        part1, part2 = enchant_parts

        for i, line in enumerate(normalized_lines):
            if part1 in line or part2 in line:
                # Look ahead 2 lines for the other part
                for j in range(1, 3):
                    if i + j < len(normalized_lines):
                        if (part1 in line and part2 in normalized_lines[i + j]) or (
                                part2 in line and part1 in normalized_lines[i + j]):
                            if c.DEBUGGING:
                                log_message(
                                    f"[EnchantCombo] Found combo '{part1}' & '{part2}' at lines {i} and {i + j}")
                            return True
        return False

    # --- Standard Term Matching ---
    return any(normalized_term in line for line in normalized_lines)


def is_duplicate_recent_entry(value):
    current_time = datetime.now()
    dupe_duration = int(duplicate_duration_time or 60)

    incoming = utils.smart_title_case(value)

    for term, ts in recent_terms:
        if term == incoming and (current_time - ts).total_seconds() < dupe_duration:
            log_message(f"[DupCheck] In-memory dupe found for '{incoming}' (ts={ts})")
            return True

    return False


def mark_term_as_captured(value, timestamp: datetime = None):
    global recent_terms
    ts = timestamp or datetime.now()
    term = utils.smart_title_case(value)

    for idx, (t, old_ts) in enumerate(recent_terms):
        if t == term:
            recent_terms.pop(idx)
            break

    recent_terms.append((term, ts))

    if len(recent_terms) > MAX_RECENT_TERMS:
        recent_terms = recent_terms[-MAX_RECENT_TERMS:]

    # format timestamps for logging
    formatted = [(t, ts.strftime("%Y-%m-%d %H:%M:%S")) for t, ts in recent_terms]

    log_message(f"[RecentTerms] Buffer now: {formatted}")


def remove_recent_term(term: str) -> bool:
    global recent_terms

    term = utils.smart_title_case(term)
    term = term.replace("Replica ", "")
    before = len(recent_terms)

    recent_terms = [
        (t, ts) for (t, ts) in recent_terms
        if t != term
    ]

    removed = len(recent_terms) != before
    if removed:
        log_message(f"[RecentTerms] Removed term: {term}")
    return removed


def clear_recent_terms():
    global recent_terms
    recent_terms.clear()
    log_message("[RecentTerms] Cleared all recent terms")


#################################################
# Gets all matched terms from the list          #
#################################################
def get_matched_terms(text, allow_dupes=False) -> List[Dict]:
    global non_dup_count

    all_candidates = []
    original_terms_source = all_terms
    original_text = text

    text_clean = utils.remove_possessive_s(text)
    normalized_lines = tuple(
        utils.normalize_for_search(line)
        for line in text_clean.splitlines()
    )

    for original_term, normalized_term, enchant_parts in PRECOMP_TERMS:
        if is_term_match(normalized_term, normalized_lines, enchant_parts):
            duplicate = is_duplicate_recent_entry(original_term)
            all_candidates.append((original_term, duplicate))

    #########################################################################################
    # SPECIFICALLY FOR ENCHANTS TO NOT COUNT TWICE FOR MATCHES i.e                          #
    # "8% Increased Explicit Ailment Modifier Magnitudes" and                               #
    # "8% Increased Explicit Ailment Modifier Magnitudes; Has 1 White Socket"               #
    # if it contains "Has 1 White Socket" it will write it/save it as the 2nd one instead   #
    #########################################################################################
    suppress_parts = set()
    full_enchant_terms = set()
    for term_title, _ in all_candidates:
        if ";" in term_title and (term_types.get(term_title) in (c.ARMOR_ENCHANT_TYPE, c.WEAPON_ENCHANT_TYPE)):
            part1, part2 = [utils.smart_title_case(p.strip()) for p in term_title.split(";", 1)]
            suppress_parts.add(part1)
            suppress_parts.add(part2)
            full_enchant_terms.add(term_title)

    if suppress_parts and not full_enchant_terms and c.DEBUGGING:
        log_message("[Suppress] Found sub-parts to suppress but no full enchant terms present")

    ############################################################
    # Group candidates by term type and filter by match length #
    ############################################################
    sorted_terms = sorted(all_candidates, key=lambda x: len(x[0]), reverse=True)
    final_matches = []
    seen = set()

    for term_title, duplicate in sorted_terms:
        # Skip shorter terms already covered by a longer kept match
        if any(term_title in existing for existing in seen):
            continue  # do not add it at all

        seen.add(term_title)
        final_matches.append((term_title, duplicate))

    #######################################
    # Final filtering of suppressed terms #
    #######################################
    matched = []

    for term_title, duplicate in final_matches:
        if term_title in suppress_parts and term_title not in full_enchant_terms:
            continue

        armor_flag = False
        weapon_flag = False

        item_type = term_types.get(term_title)
        base_part = term_title.split(";", 1)[0].strip()
        norm_key = utils.normalize_for_search(utils.smart_title_case(base_part))
        possible_types = enchant_type_lookup.get(norm_key, [])

        # Only assign flags if item_type is an enchant type
        if item_type in (c.ARMOR_ENCHANT_TYPE, c.WEAPON_ENCHANT_TYPE):
            if possible_types:
                if all(t == c.ARMOR_ENCHANT_TYPE for t in possible_types):
                    armor_flag = True
                elif all(t == c.WEAPON_ENCHANT_TYPE for t in possible_types):
                    weapon_flag = True
                else:
                    # Term exists in both armor and weapon types
                    # Use proximity logic to disambiguate
                    if utils.is_armor_enchant_by_body_armor_order(term_title, text, body_armors, enchant_type_lookup):
                        armor_flag = True
                    else:
                        weapon_flag = True
        else:
            # For non-enchant types, force flags false
            armor_flag = False
            weapon_flag = False

        # Append result, respecting duplicate flags and allowance
        if allow_dupes or not duplicate:
            non_dup_count += 1
            matched.append({
                "term": term_title,
                "duplicate": False,
                "armor_enchant_flag": armor_flag,
                "weapon_enchant_flag": weapon_flag,
            })
        else:
            matched.append({
                "term": term_title,
                "duplicate": True,
                "armor_enchant_flag": armor_flag,
                "weapon_enchant_flag": weapon_flag,
            })

    return matched


def process_text(root, text, allow_dupes=False, matched_terms=None) -> None:
    global stack_sizes, attempt
    results = []

    if matched_terms is None:
        matched_terms = get_matched_terms(text, allow_dupes)

    raw_lines = text.splitlines()
    title_lines = tuple(line.title() for line in raw_lines)

    for match in matched_terms:
        term_title = match["term"]
        duplicate = match["duplicate"]
        armor_flag = match["armor_enchant_flag"]
        weapon_flag = match["weapon_enchant_flag"]
        current_number = data_mgr.get_next_record_number()

        item_type = term_types.get(utils.smart_title_case(term_title))

        # Extract stack size / currency ratio
        ratio = extract_currency_value(raw_lines, title_lines, term_title, term_types)
        if ratio:
            stack_size = f"{ratio[0]}"
            stack_sizes[term_title] = stack_size
            if c.DEBUGGING:
                log_message(f"Ratio for {term_title}: {ratio[0]}/{ratio[1]}")
        else:
            stack_size = 1
            stack_sizes[term_title] = stack_size
            if c.DEBUGGING:
                log_message("[Currency Ratio] None found.")

        stack_size_txt = (
            c.stack_size_found.format(stack_size)
            if int(stack_size) > 0 and utils.is_currency_or_scarab(item_type)
            else ""
        )

        # Format result
        type = c.ARMOR_ENCHANT_TYPE if armor_flag else c.WEAPON_ENCHANT_TYPE if weapon_flag else item_type
        if duplicate and not allow_dupes:
            results.append(f"{type}: {term_title} (Duplicate - Skipping)")
        else:
            results.append(f"{type}: {term_title}{stack_size_txt}")

    if c.DEBUGGING:
        highlighted = utils.smart_title_case(text)
        for term in sorted(all_terms, key=len, reverse=True):
            pattern = rf"(?i)\b({re.escape(utils.smart_title_case(term))})\b"
            highlighted = re.sub(
                pattern,
                lambda m: colored(m.group(1), "green", attrs=["bold"]),
                highlighted
            )
        log_message(highlighted)

    if results:
        log_message(c.matches_found, results)
        attempt = 1
    else:
        status = f"{c.matches_not_found} Attempt: #{attempt}"
        toasts.show_message(root, status)
        log_message(status)
        attempt += 1


def write_entry(root, text, timestamp, allow_dupes=False) -> None:
    global stack_sizes, parsed_items, data_mgr
    parsed_items = []

    t0 = time.perf_counter()

    matched_terms = get_matched_terms(text, allow_dupes)

    t1 = time.perf_counter()

    process_text(root, text, allow_dupes, matched_terms)

    t2 = time.perf_counter()

    if c.DEBUGGING:
        log_message(
            f"[MATCH PERF] "
            f"get_matched_terms={(t1 - t0) * 1000:.1f}ms | "
            f"process_text={(t2 - t1) * 1000:.1f}ms | "
            f"total={(t2 - t0) * 1000:.1f}ms | "
            f"matches={len(matched_terms)}"
        )

    if not matched_terms:
        return

    rows_to_write = []

    next_record_number = data_mgr.get_next_record_number(force=True)

    for match in matched_terms:
        term_title = match["term"]
        duplicate = match["duplicate"]
        item_type = term_types.get(utils.smart_title_case(term_title))
        stack_size = stack_sizes.get(term_title, 1)

        if not allow_dupes and duplicate:
            continue

        current_number = next_record_number
        next_record_number += 1

        mark_term_as_captured(term_title)

        currency_data = CURRENCY_DATASET.get(term_title, {})
        tier_data = TIERS_DATASET.get(term_title, {})
        owned = COLLECTION_DATASET_ACTIVE.get(term_title, False)

        item = build_parsed_item(
            record=current_number,
            term_title=term_title,
            item_type=item_type,
            duplicate=duplicate,
            timestamp=timestamp,
            experimental_items=experimental_items,
            stack_size=stack_size,
            area_level=blueprint_area_level,
            blueprint_type=blueprint_layout,
            logged_by=poe_user,
            league=league_version,
            chaos_value=currency_data.get("chaos"),
            divine_value=currency_data.get("divine"),
            tier=tier_data.get("tier", ""),
            wiki=tier_data.get("wiki", ""),
            img=tier_data.get("img", ""),
            five_l_val=currency_data.get("five_link"),
            six_l_val=currency_data.get("six_link"),
            picked=False,
            owned=owned,
            bp_enchantment=c.SET_BP_ENCHANTMENT_FOR_RUNS
        )

        parsed_items.append(item)

        row_dict = {
            c.csv_record_header: current_number,
            c.csv_league_header: league_version,
            c.csv_loggedby_header: poe_user,
            c.csv_blueprint_header: blueprint_layout,
            c.csv_area_level_header: blueprint_area_level,
            c.csv_trinket_header: utils.add_if_trinket(term_title, item_type),
            c.csv_replacement_header: utils.add_if_replacement(term_title, item_type),
            c.csv_replica_header: utils.add_if_replica(term_title, item_type),
            c.csv_experimented_header: utils.add_if_experimental(term_title, item_type),
            c.csv_weapon_enchant_header: utils.add_if_weapon_enchant(term_title, item_type),
            c.csv_armor_enchant_header: utils.add_if_armor_enchant(term_title, item_type),
            c.csv_scarab_header: utils.add_if_scarab(term_title, item_type),
            c.csv_currency_header: utils.add_if_currency(term_title, item_type),
            c.csv_stack_size_header: stack_size if utils.is_currency_or_scarab(item_type) else "",
            c.csv_variant_header: "",
            c.csv_flag_header: False,
            c.csv_time_header: timestamp,
            c.csv_picked_header: False,
            c.csv_owned_header: owned,
            c.csv_enchantment_header: c.SET_BP_ENCHANTMENT_FOR_RUNS
        }

        rows_to_write.append(row_dict)

    if rows_to_write:
        data_mgr.ensure_data_file()
        data_mgr.append_rows(rows_to_write, root)

    data_mgr.last_record_number = next_record_number - 1


def reload_data_manager():
    from settings import get_setting
    from csv_manager import CSVManager
    from json_manager import JSONManager
    from config import data_file_base
    from pathlib import Path

    _base = Path(data_file_base)
    _saved_mode = get_setting("Application", "export_mode", default="CSV").upper()

    if _saved_mode == "JSON":
        _data_mgr = JSONManager(_base)
    else:
        _data_mgr = CSVManager(_base)

    return _data_mgr


def build_row_dict(record_number, term_title, item_type, stack_size, timestamp):
    return {
        c.csv_record_header: record_number,
        c.csv_league_header: league_version,
        c.csv_loggedby_header: poe_user,
        c.csv_blueprint_header: blueprint_layout,
        c.csv_area_level_header: blueprint_area_level,
        c.csv_trinket_header: utils.add_if_trinket(term_title, item_type),
        c.csv_replacement_header: utils.add_if_replacement(term_title, item_type),
        c.csv_replica_header: utils.add_if_replica(term_title, item_type),
        c.csv_experimented_header: utils.add_if_experimental(term_title, item_type),
        c.csv_weapon_enchant_header: utils.add_if_weapon_enchant(term_title, item_type),
        c.csv_armor_enchant_header: utils.add_if_armor_enchant(term_title, item_type),
        c.csv_scarab_header: utils.add_if_scarab(term_title, item_type),
        c.csv_currency_header: utils.add_if_currency(term_title, item_type),
        c.csv_stack_size_header: stack_size if utils.is_currency_or_scarab(item_type) else "",
        c.csv_variant_header: "",
        c.csv_flag_header: False,
        c.csv_time_header: timestamp,
        c.csv_picked_header: False,
        c.csv_enchantment_header: "None"
    }


def init_data():
    log_message("Starting Heist Curio Tracker...")
    reload_data_manager()
    data_mgr.upgrade_structure()
    data_mgr.get_next_record_number()
    populate_recent_terms()


def parse_items_from_rows(rows):
    debug = c.DEBUGGING
    parsed_items = []

    column_to_type = {
        "Trinket": c.TRINKET_TYPE,
        "Replacement": c.REPLACEMENT_TYPE,
        "Replica": c.REPLICA_TYPE,
        "Experimented Base Type": c.EXPERIMENTAL_TYPE,
        "Weapon Enchantment": c.WEAPON_ENCHANT_TYPE,
        "Armor Enchantment": c.ARMOR_ENCHANT_TYPE,
        "Scarab": c.SCARAB_TYPE,
        "Currency": c.CURRENCY_TYPE,
    }

    for row_idx, row in enumerate(rows):
        if debug:
            log_message(f"[DEBUG] Processing row {row_idx}: {row}")

        # Grab common metadata from CSV headers
        record_number = row.get(c.csv_record_header)
        league = row.get(c.csv_league_header, "")
        logged_by = row.get(c.csv_loggedby_header, "")
        blueprint_type = row.get(c.csv_blueprint_header, "")
        area_level = row.get(c.csv_area_level_header, "")
        stack_size = row.get(c.csv_stack_size_header, "")
        variant = row.get(c.csv_variant_header, "")
        # duplicate = row.get(c.csv_flag_header, "FALSE").upper() == "TRUE" # Why was I even calling this????? xd
        timestamp = row.get(c.csv_time_header, "")
        # owned = row.get(c.csv_owned_header, "")
        picked = row.get(c.csv_picked_header, False)
        bp_enchantment = row.get(c.csv_enchantment_header, "None")

        for col_name, inferred_type in column_to_type.items():
            value = row.get(col_name)
            if not value or not value.strip():
                continue

            term_title = utils.smart_title_case(value)
            item_type = term_types.get(term_title, inferred_type)
            estimated_value = CURRENCY_DATASET.get(term_title, {})
            chaos_est = estimated_value.get("chaos")
            divine_est = estimated_value.get("divine")
            five_l_est = estimated_value.get("five_link")
            six_l_est = estimated_value.get("six_link")
            owned = COLLECTION_DATASET_ACTIVE.get(term_title, False)

            item_data_set = TIERS_DATASET.get(term_title, {})
            tier = item_data_set.get("tier", "")
            wiki = item_data_set.get("wiki", "")
            img = item_data_set.get("img", "")
            duplicate = False  # Just predefining
            # Build parsed item directly from CSV header values
            item = build_parsed_item(
                record=record_number,
                term_title=term_title,
                item_type=item_type,
                duplicate=duplicate,
                timestamp=timestamp,
                experimental_items=experimental_items,
                rarity=None,
                league=league,
                logged_by=logged_by,
                blueprint_type=blueprint_type,
                area_level=area_level,
                stack_size=stack_size,
                chaos_value=chaos_est,
                divine_value=divine_est,
                tier=tier,
                owned=owned,
                picked=picked,
                wiki=wiki,
                img=img,
                five_l_val=five_l_est,
                six_l_val=six_l_est,
                bp_enchantment=bp_enchantment
            )
            parsed_items.append(item)

            if debug:
                log_message(f"[DEBUG] Added item: {item.itemName.lines[0]}, "
                            f"duplicate={duplicate}, rarity={item.itemRarity}")

    return parsed_items


def load_all_parsed_items(_data_mgr: BaseDataManager):
    rows = _data_mgr.load_dict()
    return parse_items_from_rows(rows)


def load_recent_parsed_items(_data_mgr: BaseDataManager, within_seconds=120, max_items=5):
    rows = _data_mgr.load_dict()
    if not rows:
        return []

    last_rows = rows[-max_items:]
    timestamps = []
    for row in last_rows:
        ts_str = row.get(c.csv_time_header)
        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S") if ts_str else None
        except Exception:
            ts = None
        timestamps.append(ts)

    if not any(timestamps):
        return parse_items_from_rows(last_rows)

    newest_ts = max(t for t in timestamps if t is not None)
    recent_rows = [
        row for row, ts in zip(last_rows, timestamps)
        if ts and (newest_ts - ts) <= timedelta(seconds=within_seconds)
    ]

    recent_rows = recent_rows[-max_items:]
    return parse_items_from_rows(recent_rows)


#####################################################
# Captures the entire screen, afterwards using      #
# OCR reads the texts and checks for matches.       #
# If a match is found, it will save it in the .csv  #
#####################################################
def capture_once(root):
    validate_attempt(c.capturing_prompt)

    total_start = time.perf_counter()

    bbox_start = time.perf_counter()
    bbox = get_poe_bbox()
    bbox_end = time.perf_counter()

    if not bbox:
        return

    grab_start = time.perf_counter()

    bbox = get_ocr_bbox(bbox)

    screenshot_np = np.array(
        ImageGrab.grab(bbox=bbox)
    )

    grab_end = time.perf_counter()

    ocr_start = time.perf_counter()

    full_text, filtered = ocr_from_image(screenshot_np)

    ocr_end = time.perf_counter()

    write_start = time.perf_counter()

    os.makedirs(c.saves_dir, exist_ok=True)

    write_entry(
        root,
        full_text,
        utils.now_timestamp(),
        allow_dupes=False
    )

    write_end = time.perf_counter()

    total_end = time.perf_counter()

    if c.DEBUGGING:
        log_message(
            f"[CAPTURE PERF] "
            f"bbox={(bbox_end - bbox_start) * 1000:.1f}ms | "
            f"grab={(grab_end - grab_start) * 1000:.1f}ms | "
            f"ocr={(ocr_end - ocr_start) * 1000:.1f}ms | "
            f"write={(write_end - write_start) * 1000:.1f}ms | "
            f"total={(total_end - total_start) * 1000:.1f}ms"
        )


def capture_snippet(root, on_done):
    validate_attempt(c.capturing_prompt)
    system = platform.system().lower()

    if system == "windows":
        pyperclip.copy("")

        subprocess.Popen(["explorer", "ms-screenclip:"])

        log_message("[INFO] Waiting for user to complete snip...")

        img = None
        for _ in range(60):  # up to 30 seconds
            time.sleep(0.5)
            try:
                img = ImageGrab.grabclipboard()
            except Exception:
                # If grabclipboard fails or returns invalid content, treat as cancel
                img = None
            if img:
                break

        # User canceled or Snipping Tool closed
        if img is None or not hasattr(img, "size") or img.size == 0:
            log_message("Snippet cancelled or failed.")
            return

        screenshot_np = np.array(img)
        full_text, _ = ocr_from_image(screenshot_np)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        os.makedirs(c.saves_dir, exist_ok=True)
        write_entry(root, full_text, timestamp, allow_dupes=True)

        if on_done:
            on_done(parsed_items)

    else:
        bbox = get_poe_bbox()
        if not bbox:
            return

        overlay = tk.Toplevel()
        overlay.attributes("-alpha", 0.3)
        overlay.attributes("-fullscreen", True)
        overlay.attributes("-topmost", True)
        overlay.configure(background='black')

        start_x = start_y = end_x = end_y = 0
        rect_id = None

        canvas = tk.Canvas(overlay, cursor="cross", bg='gray')
        canvas.pack(fill=tk.BOTH, expand=True)

        def on_mouse_down(event):
            nonlocal start_x, start_y
            start_x, start_y = event.x, event.y

        def on_mouse_drag(event):
            nonlocal rect_id
            if rect_id:
                canvas.delete(rect_id)
            rect_id = canvas.create_rectangle(start_x, start_y, event.x, event.y,
                                              outline='red', width=2)

        def on_mouse_up(event):
            nonlocal end_x, end_y
            end_x, end_y = event.x, event.y
            overlay.destroy()  # only close overlay

            x1, y1 = min(start_x, end_x), min(start_y, end_y)
            x2, y2 = max(start_x, end_x), max(start_y, end_y)
            if x2 - x1 < 5 or y2 - y1 < 5:
                log_message(c.snippet_txt_too_small)
                return

            bbox = (x1, y1, x2, y2)
            screenshot_np = np.array(ImageGrab.grab(bbox))
            if screenshot_np is None or screenshot_np.size == 0:
                log_message(c.snippet_txt_failed)
                return

            full_text, filtered = ocr_from_image(screenshot_np, scale=2)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            os.makedirs(c.saves_dir, exist_ok=True)
            write_entry(root, full_text, timestamp, allow_dupes=True)

            if on_done:
                on_done(filtered)

        canvas.bind("<Button-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)


#####################################################
# Captures the a snippet of the top right corner of #
# the screen, afterwards OCR reads the texts and    #
# checks for matches between layouts and saves the  #
# monster level as area level                       #
#####################################################
def capture_layout(root):
    global blueprint_area_level, blueprint_layout, attempt

    validate_attempt(c.layout_prompt)

    screenshot = pyautogui.screenshot()
    full_width, full_height = screenshot.size

    cropped = screenshot.crop(utils.get_top_right_layout(full_width, full_height))

    # Run OCR on the cropped region
    text = utils.smart_title_case(pytesseract.image_to_string(cropped, config=r'--oem 3 --psm 6'))
    if c.DEBUGGING:
        log_message("OCR Text:\n", text)
        if c.OCR_DEBUGGING:
            cropped.show()

    # Search for layout keyword
    found_layout = None
    for keyword in c.layout_keywords:
        if utils.smart_title_case(keyword) in text:
            found_layout = keyword
            break

    # Search for monster level using regex
    match = re.search(r"Monster Level[: ]+(\d+)", text, re.IGNORECASE)
    area_level = match.group(1) if match else c.default_bp_lvl

    # Report results
    if found_layout and area_level:
        blueprint_area_level = area_level
        blueprint_layout = found_layout
        result_layout = f"Blueprint Layout: {blueprint_layout}"
        result_area_level = f"Area Level: {blueprint_area_level}"
        toasts.show_message(root, result_layout + "\n" + result_area_level)
        log_message(result_layout + " | " + result_area_level)
        attempt = 1
    else:
        status = f"Couldn't capture layout, try again. Attempt: #{attempt}"
        toasts.show_message(root, status)
        log_message(status)
        attempt += 1


def set_duplicate_duration(duration: int):
    from settings import set_setting
    global duplicate_duration_time
    duplicate_duration_time = duration
    set_setting('Application', 'time_last_dupe_check_seconds', duration)
    log_message(f"Time between-duplicates check set to: {duration}s")


def validate_attempt(print_text):
    global attempt
    if attempt == 1:
        log_message(print_text)


if __name__ == "__main__":
    pass
