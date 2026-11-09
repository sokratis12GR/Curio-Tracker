import json
import os
import platform
import re
import subprocess
import time
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

import numpy as np
import pyautogui
import pyperclip
import pytesseract
from termcolor import colored

import config as c
import currency_utils
import ocr_utils as utils
import platform_compat
import toasts
from config import data_file_base
from csv_manager import CSVManager
from data_manager import BaseDataManager
from json_manager import JSONManager
from load_utils import get_datasets
from logger import log_message
from ocr_utils import build_parsed_item
from settings import get_setting, set_setting
from tracking.ocr_capture import extract_currency_value, get_ocr_bbox, ocr_from_image
from tracking.recent_terms import (
    clear_recent_terms,
    is_duplicate_recent_entry,
    mark_term_as_captured,
    populate_recent_terms as _populate_recent_terms,
    remove_recent_term,
    set_duplicate_duration,
)
from tracking.term_matching import (
    all_terms,
    body_armors,
    experimental_items,
    get_matched_terms,
    get_review_fuzzy_matches,
    term_types,
)
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

stack_sizes = {}

attempt = 1
listener_ref = None
parsed_items = []


def populate_recent_terms(within_seconds: int = None, max_items: int = None):
    _populate_recent_terms(data_mgr, within_seconds=within_seconds, max_items=max_items)


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
owned_items = {}


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


def write_entry(root, text, timestamp, allow_dupes=False, matched_terms=None) -> None:
    global stack_sizes, parsed_items, data_mgr
    parsed_items = []

    t0 = time.perf_counter()

    if matched_terms is None:
        matched_terms = get_matched_terms(
            text,
            allow_dupes
        )

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


def insert_item(root, term_title, item_type=None, data_manager=None):
    global parsed_items

    term_title = utils.smart_title_case(
        term_title.strip()
    )

    if not term_title:
        return None

    # ---------------------------------------------------------
    # Validate term against the actual terms dataset
    # ---------------------------------------------------------
    actual_type = term_types.get(term_title)

    if not actual_type:
        log_message(f"[WARN] Manual insert rejected: unknown term '{term_title}'")
        return None

    # Always trust the dataset over whatever came from the UI.
    item_type = actual_type

    mgr = data_manager or data_mgr

    # ---------------------------------------------------------
    # Current runtime/settings values
    # ---------------------------------------------------------
    current_user = get_setting("User", "poe_user", poe_user)

    current_layout = get_setting("Blueprint", "layout", blueprint_layout)

    current_area_level = get_setting("Blueprint", "area_level", blueprint_area_level)

    current_bp_enchantment = get_setting("Blueprint", "bp_enchantment", bp_enchantment)

    timestamp = utils.now_timestamp()

    # Manual Currency / Scarab starts at stack size 1.
    # It can still be edited from the tree afterwards.
    stack_size = 1

    # ---------------------------------------------------------
    # Get next record #
    # ---------------------------------------------------------
    record_number = mgr.get_next_record_number(
        force=True
    )

    # ---------------------------------------------------------
    # Dataset metadata
    # ---------------------------------------------------------
    currency_data = CURRENCY_DATASET.get(
        term_title,
        {}
    )

    tier_data = TIERS_DATASET.get(
        term_title,
        {}
    )

    owned = COLLECTION_DATASET_ACTIVE.get(
        term_title,
        False
    )

    # ---------------------------------------------------------
    # Build ParsedItem for TreeManager
    # ---------------------------------------------------------
    item = build_parsed_item(
        record=record_number,
        term_title=term_title,
        item_type=item_type,
        duplicate=False,
        timestamp=timestamp,
        experimental_items=experimental_items,
        stack_size=stack_size,
        area_level=current_area_level,
        blueprint_type=current_layout,
        logged_by=current_user,
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
        bp_enchantment=current_bp_enchantment
    )

    # ---------------------------------------------------------
    # Build CSV / JSON row
    # ---------------------------------------------------------
    row_dict = {
        c.csv_record_header: record_number,
        c.csv_league_header: league_version,
        c.csv_loggedby_header: current_user,
        c.csv_blueprint_header: current_layout,
        c.csv_area_level_header: current_area_level,

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
        c.csv_enchantment_header: current_bp_enchantment
    }

    try:
        mgr.ensure_data_file()

        mgr.append_rows([row_dict], root)

    except Exception as e:
        log_message(f"[ERROR] Failed writing manual item '{term_title}': {e}")
        return None

    # Keep the recent duplicate buffer consistent with OCR.
    mark_term_as_captured(term_title)
    parsed_items = [item]
    mgr.last_record_number = record_number

    log_message(
        f"[INFO] Manually inserted "
        f"Record #{record_number}: "
        f"{item_type}: {term_title}"
    )

    return item


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
        platform_compat.grab_screen(bbox=bbox)
    )

    grab_end = time.perf_counter()

    ocr_start = time.perf_counter()

    full_text, filtered = ocr_from_image(screenshot_np)

    ocr_end = time.perf_counter()

    match_start = time.perf_counter()

    matched_terms = get_matched_terms(full_text, allow_dupes=False)

    match_end = time.perf_counter()

    review_start = time.perf_counter()

    if not matched_terms:
        full_text, matched_terms = review_failed_capture(screenshot_np, scale=2, allow_dupes=False)

    review_end = time.perf_counter()

    write_start = time.perf_counter()

    os.makedirs(c.saves_dir, exist_ok=True)

    write_entry(
        root,
        full_text,
        utils.now_timestamp(),
        allow_dupes=False,
        matched_terms=matched_terms
    )

    write_end = time.perf_counter()

    total_end = time.perf_counter()

    if c.DEBUGGING:
        log_message(
            f"[CAPTURE PERF] "
            f"bbox={(bbox_end - bbox_start) * 1000:.1f}ms | "
            f"grab={(grab_end - grab_start) * 1000:.1f}ms | "
            f"ocr={(ocr_end - ocr_start) * 1000:.1f}ms | "
            f"matching={(match_end - match_start) * 1000:.1f}ms | "
            f"review={(review_end - review_start) * 1000:.1f}ms | "
            f"write={(write_end - write_start) * 1000:.1f}ms | "
            f"total={(total_end - total_start) * 1000:.1f}ms"
        )


def capture_snippet(root, on_done):
    validate_attempt(c.capturing_prompt)
    system = platform.system().lower()

    is_win11 = False

    if system == "windows":
        try:
            build = int(platform.version().split(".")[-1])
            is_win11 = build >= 22000
        except (ValueError, IndexError):
            pass

    if is_win11:
        pyperclip.copy("")

        subprocess.Popen(["explorer", "ms-screenclip:"])

        log_message("[INFO] Waiting for user to complete snip...")

        img = None
        for _ in range(60):  # up to 30 seconds
            time.sleep(0.5)
            try:
                img = platform_compat.grab_clipboard_image()
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
            screenshot_np = np.array(platform_compat.grab_screen(bbox))
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

    try:
        screenshot = pyautogui.screenshot()
    except Exception as e:
        if not platform_compat.IS_WINDOWS:
            log_message(f"[ERROR] Screenshot failed: {e}. On Linux, install a screenshot "
                        f"backend such as 'scrot' or 'gnome-screenshot' and try again.")
        else:
            log_message(f"[ERROR] Screenshot failed: {e}")
        return

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


def validate_attempt(print_text):
    global attempt
    if attempt == 1:
        log_message(print_text)


if __name__ == "__main__":
    pass
