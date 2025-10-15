import csv
import json
import os
import platform
import re
import subprocess
import time
import tkinter as tk
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict

import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
import pyperclip
import pytesseract
from PIL import ImageGrab
from termcolor import colored

import config as c
import ocr_utils as utils
import toasts
from config import csv_file_path
from load_utils import get_datasets
from logger import log_message
from ocr_utils import build_parsed_item

datasets = get_datasets(force_reload=True)

# default values in case they only run area lvl 83 blueprints
blueprint_area_level = c.default_bp_lvl
blueprint_layout = c.default_bp_area
poe_user = c.poe_user
league_version = c.poe_league
duplicate_duration_time = c.time_last_dupe_check_seconds

stack_sizes = {}

non_dup_count = 0
attempt = 1
listener_ref = None
parsed_items = []

full_currency = datasets.get("currency") or {}
collection_dataset = datasets.get("collection") or {}


def on_league_change(new_league: str):
    global CURRENCY_DATASET, COLLECTION_DATASET_ACTIVE
    CURRENCY_DATASET = full_currency.get(new_league, {})

    league_collection = collection_dataset.get(new_league, {})
    COLLECTION_DATASET_ACTIVE = {term: data.get("owned", False) for term, data in league_collection.items()}
    log_message(f"League changed to {new_league}, loaded {len(COLLECTION_DATASET_ACTIVE)} curios")

    if c.DEBUGGING:
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


def build_enchant_type_lookup(term_types):
    lookup = defaultdict(set)
    for raw_term, type_name in term_types.items():
        norm = utils.normalize_for_search(utils.smart_title_case(raw_term))  # full term
        lookup[norm].add(type_name)
    return lookup


enchant_type_lookup = build_enchant_type_lookup(term_types)


def get_poe_bbox():
    windows = [w for w in gw.getWindowsWithTitle(c.target_application) if w.visible]
    if not windows:
        log_message(c.not_found_target_txt)
        return None
    win = windows[0]
    return win.left, win.top, win.left + win.width, win.top + win.height


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
    if apply_filter:
        image_np_filtered = filter_item_text(image_np)
    else:
        image_np_filtered = image_np

    if scale != 1:
        image_np_filtered = cv2.resize(
            image_np_filtered,
            (int(image_np_filtered.shape[1]) * scale, int(image_np_filtered.shape[0]) * scale),
            interpolation=cv2.INTER_LANCZOS4
        )

    text = pytesseract.image_to_string(
        image_np_filtered,
        config=f"--psm {psm}",
        lang=lang
    )

    if c.DEBUGGING:
        print("Filtered image stats:", image_np_filtered.min(), image_np_filtered.max())
        if c.OCR_DEBUGGING:
            cv2.namedWindow("Filtered Mask", cv2.WINDOW_NORMAL)
            cv2.imshow("Filtered Mask", image_np_filtered)
            cv2.moveWindow("Filtered Mask", 100, 100)  # Put window at x=100, y=100 on screen
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    return utils.smart_title_case(text), image_np


#############################################################
# Saves the information on the screen based on colors       #
# which is afterwards extracted as text                     #
#############################################################
def filter_item_text(image_np, fullscreen=False):
    img_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    color_ranges = {
        "unique": (c.replica_l_hsv, c.replica_u_hsv),
        "rare": (c.rare_l_hsv, c.rare_u_hsv),
        "currency": (c.currency_l_hsv, c.currency_u_hsv),
        "scarab": (c.scarab_l_hsv, c.scarab_u_hsv),
        "enchant": (c.enchant_l_hsv, c.enchant_u_hsv),
    }

    # Create combined mask
    combined_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in color_ranges.values():
        combined_mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))

    # Morphological operations
    kernel = np.ones((1, 1), np.uint8)
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)

    # Debugging overlay
    if c.DEBUGGING:
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        debug_image = cv2.bitwise_and(img_bgr, img_bgr, mask=combined_mask)
        cv2.drawContours(debug_image, contours, -1, (0, 0, 255), 1)
        cv2.imwrite("ocr_debug_highlighted.png", debug_image)

    return cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2RGB)


####################################################################
# Checks for a match of x/y and if currency applies the stack size #
####################################################################
def extract_currency_value(text, matched_term, term_types):
    if term_types.get(matched_term) not in {c.CURRENCY_TYPE, c.SCARAB_TYPE}:
        return None

    lines = text.splitlines()
    idx = next((i for i, line in enumerate(lines) if matched_term.title() in line.title()), None)
    if idx is None:
        return None

    valid_max_values = {20, 30, 40}

    # OCR digit normalizer
    def normalize_ocr_text(text):
        replace_map = {
            'O': '0', 'o': '0',
            'I': '1', 'l': '1', '!': '1', 'i': '1',
            'B': '8',
            'S': '5', 's': '5',
            'g': '9', 'q': '9',
            '\\': '/', '-': '/', '|': '/',
        }
        return ''.join(replace_map.get(c, c) for c in text)

    # Search current and next 2 lines
    for j in range(idx, min(idx + 3, len(lines))):
        line = lines[j]
        line = normalize_ocr_text(line)

        # Match flexible patterns like 19/20, 19 / 20, 19|20, etc.
        match = re.search(r"\b(\d{1,3})\s*[/|\\\-]\s*(\d{2})\b", line)
        if match:
            raw_current, raw_max = match.groups()

            try:
                current = int(raw_current)
                maximum = int(raw_max)
            except ValueError:
                continue

            if maximum in valid_max_values and 0 <= current <= maximum:
                return (current, maximum)

            # Fallback fix: take last digit of current if it's obviously wrong
            if maximum in valid_max_values:
                current_last = int(str(current)[-1])
                if current_last <= maximum:
                    return current_last, maximum

    return 1, 20


#################################################
# Check if a term or combo term is in the text. #
#################################################
def is_term_match(term, text) -> bool:
    def normalize_lines(text):
        return [utils.normalize_for_search(line) for line in text.splitlines()]

    raw_term = next((k for k in term_types if utils.smart_title_case(k) == term), None)
    term_type = term_types.get(raw_term, "")
    term_type_cmp = utils.smart_title_case(term_type) if isinstance(term_type, str) else ""

    # Handle enchant combo terms
    if ";" in term and term_type_cmp in (c.ARMOR_ENCHANT_TYPE, c.WEAPON_ENCHANT_TYPE):
        part1_raw, part2_raw = [p.strip() for p in term.split(";", 1)]
        part1 = utils.normalize_for_search(utils.smart_title_case(part1_raw))
        part2 = utils.normalize_for_search(utils.smart_title_case(part2_raw))
        norm_lines = normalize_lines(text)

        def find_combo(p1, p2):
            for i in range(len(norm_lines)):
                if p1 in norm_lines[i]:
                    for j in range(1, 3):  # allow match across next 2 lines
                        if i + j < len(norm_lines) and p2 in norm_lines[i + j]:
                            if c.DEBUGGING:
                                print(f"[EnchantCombo] Found '{p1}' then '{p2}' on lines {i} and {i + j}")
                            return True
            return False

        # Try original and flipped order
        return find_combo(part1, part2) or find_combo(part2, part1)

    # Standard term matching
    def find_piece_positions(piece):
        piece_title = utils.smart_title_case(piece)
        positions = []

        pattern = rf"\b{re.escape(piece_title)}\b"
        for m in re.finditer(pattern, text, re.IGNORECASE):
            positions.append(m.start())

        return positions

    return bool(find_piece_positions(term))


recent_terms = []


def is_duplicate_recent_entry(value, path=csv_file_path):
    current_time = datetime.now()
    dupe_duration = int(duplicate_duration_time or 60)
    # Check in-memory recent terms first
    for term, ts in recent_terms:
        if term == value and (current_time - ts).total_seconds() < dupe_duration:
            return True

    # Check CSV for older duplicates
    if os.path.exists(path):
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row.get(c.csv_time_header)
                if not ts_str:
                    continue
                try:
                    entry_time = datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S")
                    if (current_time - entry_time).total_seconds() < dupe_duration:
                        if value in row.values():  # Check if value exists anywhere in the row
                            return True
                except ValueError:
                    continue

    return False


def mark_term_as_captured(value):
    recent_terms.append((value, datetime.now()))


#################################################
# Gets all matched terms from the list          #
#################################################
def get_matched_terms(text, allow_dupes=False) -> List[Dict]:
    global non_dup_count

    all_candidates = []
    original_terms_source = all_terms
    original_text = text

    terms_source = [utils.remove_possessive_s(t) for t in original_terms_source]
    text_clean = utils.remove_possessive_s(text)

    for original_term, cleaned_term in zip(original_terms_source, terms_source):
        term_title = utils.smart_title_case(cleaned_term)
        if is_term_match(term_title, text_clean):
            duplicate = is_duplicate_recent_entry(term_title)
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

    if term_title in suppress_parts and term_title not in full_enchant_terms:
        log_message(f"[Suppress] Skipping sub-part match: {term_title}")

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

    for match in matched_terms:
        term_title = match["term"]
        duplicate = match["duplicate"]
        armor_flag = match["armor_enchant_flag"]
        weapon_flag = match["weapon_enchant_flag"]

        item_type = term_types.get(utils.smart_title_case(term_title))

        # Extract stack size / currency ratio
        ratio = extract_currency_value(text, term_title, term_types)
        if ratio:
            stack_size = f"{ratio[0]}"
            stack_sizes[term_title] = stack_size
            if c.DEBUGGING:
                print(f"Ratio for {term_title}: {ratio[0]}/{ratio[1]}")
        else:
            stack_size = 1
            stack_sizes[term_title] = stack_size
            if c.DEBUGGING:
                print("[Currency Ratio] None found.")

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
        print(highlighted)

    if results:
        log_message(c.matches_found, results)
        attempt = 1
    else:
        status = f"{c.matches_not_found} Attempt: #{attempt}"
        toasts.show_message(root, status)
        log_message(status)  # clear leftover chars
        attempt += 1


def write_csv_entry(root, text, timestamp, allow_dupes=False) -> None:
    global stack_sizes, body_armors, experimental_items, parsed_items
    write_header = not os.path.isfile(csv_file_path)

    parsed_items = []
    matched_terms = get_matched_terms(text, allow_dupes)
    process_text(root, text, allow_dupes, matched_terms)

    def format_row(record_number, term_title, item_type, stack_size, prefix=""):
        def maybe_add(fn):
            val = fn(term_title, item_type)
            return f"{prefix}{val}" if val else ""

        return [
            record_number,
            league_version, poe_user,
            blueprint_layout, blueprint_area_level,
            maybe_add(utils.add_if_trinket),
            maybe_add(utils.add_if_replacement),
            maybe_add(utils.add_if_replica),
            maybe_add(utils.add_if_experimental),
            maybe_add(utils.add_if_weapon_enchant),
            maybe_add(utils.add_if_armor_enchant),
            maybe_add(utils.add_if_scarab),
            maybe_add(utils.add_if_currency),
            stack_size if (int(stack_size) > 0 and utils.is_currency_or_scarab(item_type)) else "",
            "",
            False,
            timestamp,
            False,
            False,
        ]

    try:
        with open(csv_file_path, "a", newline='', encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            if write_header:
                writer.writerow([
                    c.csv_record_header,
                    c.csv_league_header, c.csv_loggedby_header,
                    c.csv_blueprint_header, c.csv_area_level_header,
                    c.csv_trinket_header, c.csv_replacement_header,
                    c.csv_replica_header, c.csv_experimented_header,
                    c.csv_weapon_enchant_header, c.csv_armor_enchant_header,
                    c.csv_scarab_header, c.csv_currency_header,
                    c.csv_stack_size_header, c.csv_variant_header,
                    c.csv_flag_header, c.csv_time_header,
                    c.csv_picked_header, c.csv_owned_header
                ])

            for match in matched_terms:

                term_title = match["term"]
                duplicate = match["duplicate"]
                term_smart_title = utils.smart_title_case(term_title)

                item_type = term_types.get(term_smart_title)
                stack_size = stack_sizes.get(term_title, 1)
                estimated_value = CURRENCY_DATASET.get(term_title, {})
                chaos_est = estimated_value.get("chaos")
                divine_est = estimated_value.get("divine")
                tier = TIERS_DATASET.get(term_title, {}).get("tier", "")
                owned = COLLECTION_DATASET_ACTIVE.get(term_title, False)

                if allow_dupes or not duplicate:
                    record_number = get_next_record_number()
                    mark_term_as_captured(term_title)

                    item = build_parsed_item(
                        record=record_number,
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
                        chaos_value=chaos_est,
                        divine_value=divine_est,
                        tier=tier,
                        picked=False,
                        owned=owned
                    )
                    parsed_items.append(item)

                    log_message(f"[WriteCSV] Writing row for term: {term_title} (Record {record_number})")

                    writer.writerow(format_row(record_number, term_title, item_type, stack_size))

                    if c.DEBUGGING and c.CSV_DEBUGGING:
                        writer.writerow(
                            format_row(record_number, term_title, item_type, stack_size, prefix=lambda v: f"{v}: "))
    except PermissionError as e:
        toasts.show_message(root, "!!! Unable to write to CSV (file may be open) !!!", duration=5000)
        log_message(f"[ERROR] PermissionError: {e}")
    except OSError as e:
        log_message(f"[ERROR] CSV write failed: {e}")


LAST_RECORD_NUMBER = 0


def get_next_record_number():
    global LAST_RECORD_NUMBER
    if LAST_RECORD_NUMBER == 0:
        try:
            with open(csv_file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                if len(rows) <= 1:
                    LAST_RECORD_NUMBER = 0
                else:
                    last_row = rows[-1]
                    try:
                        LAST_RECORD_NUMBER = int(last_row[0]) if last_row[0].isdigit() else 0
                    except ValueError as e:
                        LAST_RECORD_NUMBER = 0
        except FileNotFoundError:
            LAST_RECORD_NUMBER = 0
    LAST_RECORD_NUMBER += 1
    return LAST_RECORD_NUMBER


def _parse_rows_from_csv(csv_file_path):
    try:
        with open(csv_file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except FileNotFoundError:
        log_message(f"[DEBUG] CSV file '{csv_file_path}' not found.")
        return []

    if not rows:
        log_message("[DEBUG] CSV file is empty.")
        return []

    # Ensure every row has a Record #
    if "Record #" not in rows[0]:
        log_message("[DEBUG] Adding missing 'Record #' column to rows")
        for i, row in enumerate(rows, start=1):
            row["Record #"] = str(i)

    return rows


def upgrade_csv_with_record_numbers(file_path):
    if not os.path.exists(file_path):
        log_message(f"[INFO] CSV file '{file_path}' not found. Skipping upgrade.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
    if not reader:
        return

    header = reader[0]

    # Case 1: No "Record #" column → add it
    if c.csv_record_header not in header:
        header = [c.csv_record_header] + header
        upgraded_rows = [header]
        for i, row in enumerate(reader[1:], start=1):
            upgraded_rows.append([str(i)] + row)

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(upgraded_rows)

        log_message(f"[INFO] Added 'Record #' column and generated IDs → {file_path}")
        return

    # Case 2: "Record #" exists → check for missing/empty values
    record_index = header.index(c.csv_record_header)
    rows = reader[1:]

    needs_update = any(
        len(row) <= record_index or row[record_index].strip() == ""
        for row in rows
    )

    if not needs_update:
        log_message(f"[INFO] '{c.csv_record_header}' column already complete. No changes made.")
        return

    # Case 3: Regenerate Record # column
    upgraded_rows = [header]
    for i, row in enumerate(rows, start=1):
        row = row[:]  # copy
        if len(row) <= record_index:
            row.extend([""] * (record_index - len(row) + 1))
        row[record_index] = str(i)
        upgraded_rows.append(row)

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(upgraded_rows)

    log_message(f"[INFO] Refreshed missing '{c.csv_record_header}' values → {file_path}")


def init_csv():
    log_message("Starting Heist Curio Tracker...")
    upgrade_csv_with_record_numbers(c.csv_file_path)


def _parse_items_from_rows(rows):
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
            print(f"[DEBUG] Processing row {row_idx}: {row}")

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
        picked = row.get(c.csv_picked_header, "")
        # owned = row.get(c.csv_owned_header, "")

        for col_name, inferred_type in column_to_type.items():
            value = row.get(col_name)
            if not value or not value.strip():
                continue

            term_title = utils.smart_title_case(value)
            item_type = term_types.get(term_title, inferred_type)
            estimated_value = CURRENCY_DATASET.get(term_title, {})
            chaos_est = estimated_value.get("chaos")
            divine_est = estimated_value.get("divine")
            owned = COLLECTION_DATASET_ACTIVE.get(term_title, False)

            tier = TIERS_DATASET.get(term_title, {}).get("tier", "")
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
                picked=picked,
                owned=owned
            )
            parsed_items.append(item)

            if debug:
                print(f"[DEBUG] Added item: {item.itemName.lines[0]}, "
                      f"duplicate={duplicate}, rarity={item.itemRarity}")

    return parsed_items


def load_recent_parsed_items_from_csv(within_seconds=120, max_items=5):
    rows = _parse_rows_from_csv(c.csv_file_path)
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
        return _parse_items_from_rows(last_rows)

    newest_ts = max(t for t in timestamps if t is not None)
    recent_rows = [
        row for row, ts in zip(last_rows, timestamps)
        if ts and (newest_ts - ts) <= timedelta(seconds=within_seconds)
    ]

    recent_rows = recent_rows[-max_items:]

    return _parse_items_from_rows(recent_rows)


# ---------- Load All Items ----------
def load_all_parsed_items_from_csv():
    rows = _parse_rows_from_csv(c.csv_file_path)
    return _parse_items_from_rows(rows)


#####################################################
# Captures the entire screen, afterwards using      #
# OCR reads the texts and checks for matches.       #
# If a match is found, it will save it in the .csv  #
#####################################################
def capture_once(root):
    validate_attempt(c.capturing_prompt)
    bbox = get_poe_bbox()
    if not bbox:
        return

    screenshot_np = np.array(ImageGrab.grab(bbox=bbox))
    full_text, filtered = ocr_from_image(screenshot_np)

    os.makedirs(c.saves_dir, exist_ok=True)
    write_csv_entry(root, full_text, utils.now_timestamp(), allow_dupes=False)


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
            img = ImageGrab.grabclipboard()
            if img:
                break

        if img is None:
            log_message(c.snippet_txt_failed)
            return

        screenshot_np = np.array(img)
        full_text, _ = ocr_from_image(screenshot_np)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        os.makedirs(c.saves_dir, exist_ok=True)
        write_csv_entry(root, full_text, timestamp, allow_dupes=True)

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
            write_csv_entry(root, full_text, timestamp, allow_dupes=True)

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
        print("OCR Text:\n", text)
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
    print("Run GUI instead: python gui.py")
