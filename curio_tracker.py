import threading
import tkinter as tk
from pynput import keyboard
import pyautogui
import cv2
import numpy as np
import pytesseract
from PIL import ImageGrab
import pygetwindow as gw
import re
import string
import csv
import ctypes
import time
import math
import sys
from difflib import get_close_matches
import os
from datetime import datetime, timedelta
import config as c
from termcolor import colored
import shutil
import ocr_utils as utils
from collections import defaultdict


utils.set_tesseract_path()

os.makedirs(c.logs_dir, exist_ok=True)
os.makedirs(c.saves_dir, exist_ok=True)

csv_file_path = c.csv_file_path

# default values in case they only run area lvl 83 blueprints
blueprint_area_level = c.default_bp_lvl
blueprint_layout = c.default_bp_area

stack_sizes = {}

non_dup_count = 0
attempt = 1
listener_ref = None


def get_resource_path(filename):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, filename)

# Loads all of the item types and items that can be found in heists.
def load_csv_with_types(file_path):
    term_types = {}
    with open(file_path, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile)
        next(reader, None)
        for row in reader:
            if len(row) >= 2:
                raw_term, type_name = row[0].strip(), row[1].strip()
                term_key = utils.smart_title_case(raw_term)
                term_types[term_key] = type_name
    return term_types

def load_body_armors(file_path):
    body_armors = []
    with open(file_path, "r", encoding="utf-8") as f:
        body_armors = f.readlines()
    return body_armors

term_types = load_csv_with_types(get_resource_path(c.file_name))
all_terms = set(term_types.keys())
seen_matches = set()
body_armors = load_body_armors(get_resource_path(c.file_body_armors))


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
        print(c.not_found_target_txt)
        return None
    win = windows[0]
    return (win.left, win.top, win.left + win.width, win.top + win.height)
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

    # Unique: #AF6025
    lower_orange = np.array([c.replica_l_hue, c.replica_l_sat, c.replica_l_val])
    upper_orange = np.array([c.replica_u_hue, c.replica_u_sat, c.replica_u_val])

    # Rare: #D9C850
    lower_yellow = np.array([c.rare_l_hue, c.rare_l_sat, c.rare_l_val])
    upper_yellow = np.array([c.rare_u_hue, c.rare_u_sat, c.rare_u_val])


    # Currency: #AA9E82
    lower_currency = np.array([c.currency_l_hue, c.currency_l_sat, c.currency_l_val])
    upper_currency = np.array([c.currency_u_hue, c.currency_u_sat, c.currency_u_val])

    # Scarabs (new gray): #B7B8B8
    lower_scarab = np.array([c.scarab_l_hue, c.scarab_l_sat, c.scarab_l_val])
    upper_scarab = np.array([c.scarab_u_hue, c.scarab_u_sat, c.scarab_u_val])

    # Enchants (blue-gray): #5C7E9D
    lower_enchant = np.array([c.enchant_l_hue, c.enchant_l_sat, c.enchant_l_val])
    upper_enchant = np.array([c.enchant_u_hue, c.enchant_u_sat, c.enchant_u_val])
    
    # Create individual masks
    mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)
    mask_currency = cv2.inRange(hsv, lower_currency, upper_currency)
    mask_scarab = cv2.inRange(hsv, lower_scarab, upper_scarab)
    mask_enchant = cv2.inRange(hsv, lower_enchant, upper_enchant)

    # Combine masks
    combined_mask = (
        mask_orange |
        mask_yellow |
        mask_currency |
        mask_scarab |
        mask_enchant
    )

    kernel = np.ones((1, 1), np.uint8)
    combined_mask = cv2.dilate(combined_mask, kernel, iterations=1)
    combined_mask = cv2.erode(combined_mask, kernel, iterations=1)

    if c.DEBUGGING:
        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        debug_image = cv2.bitwise_and(img_bgr, img_bgr, mask=combined_mask)
        cv2.drawContours(debug_image, contours, -1, (0, 0, 255), 1)  # Red outline        
        cv2.imwrite('ocr_debug_highlighted.png', debug_image)

    filtered = cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2RGB)

    return filtered


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
                    return (current_last, maximum)

    return (1, 20)




#################################################
# Check if a term or combo term is in the text. # 
#################################################
def is_term_match(term, text, use_fuzzy=False):
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
                                print(f"[EnchantCombo] Found '{p1}' then '{p2}' on lines {i} and {i+j}")
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

        if use_fuzzy:
            word_pattern = r"\b[\w%']+\b"
            tokens = [(m.group(0), m.start()) for m in re.finditer(word_pattern, text)]
            max_len_diff = 2
            candidates = [w for w, _ in tokens if abs(len(w) - len(piece_title)) <= max_len_diff]
            close = get_close_matches(piece_title, candidates, n=1, cutoff=0.83)
            if close:
                best = close[0]
                for tok, pos in tokens:
                    if utils.smart_title_case(tok) == utils.smart_title_case(best):
                        if c.DEBUGGING:
                            print(f"[Fuzzy match] Term piece: '{piece}' ≈ '{tok}'")
                        positions.append(pos)
        return positions

    return bool(find_piece_positions(term))


def is_duplicate_recent_entry(value,path=csv_file_path):
    current_time = datetime.now()
    if not os.path.exists(path):
        return False
    with open(path, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) <= c.time_column_index:
                continue  # skip rows with missing timestamp
            try:
                entry_time = datetime.strptime(row[c.time_column_index], "%Y-%m-%d_%H-%M-%S")
                if (current_time - entry_time) < timedelta(seconds=c.time_last_dupe_check_seconds):
                    if value in row:
                        return True  # Found a duplicate in recent entry
            except ValueError:
                continue  # invalid timestamp format
    return False

#################################################
# Gets all matched terms from the list          # 
#################################################
def get_matched_terms(text, allow_dupes=False, use_fuzzy=False):
    global non_dup_count

    all_candidates = []
    terms_source = term_types.keys() if use_fuzzy else all_terms

    for term in terms_source:
        term_title = utils.smart_title_case(term)
        if is_term_match(term_title, text, use_fuzzy):
            duplicate = is_duplicate_recent_entry(term_title)
            all_candidates.append((term_title, duplicate))

    #########################################################################################
    # SPECIFICALLY FOR ENCHANTS TO NOT COUNT TWICE FOR MATCHES i.e                          #
    # "8% Increased Explicit Ailment Modifier Magnitudes" and                               #
    # "8% Increased Explicit Ailment Modifier Magnitudes; Has 1 White Socket"               #
    # if it contains "Has 1 White Socket" it will write it/save it as the 2nd one instead   #
    #########################################################################################
    suppress_parts = set()
    full_enchant_terms = set()
    for term_title, _ in all_candidates:
        if ";" in term_title and ((term_types.get(term_title) in (c.ARMOR_ENCHANT_TYPE, c.WEAPON_ENCHANT_TYPE))):
            part1, part2 = [utils.smart_title_case(p.strip()) for p in term_title.split(";", 1)]
            suppress_parts.add(part1)
            suppress_parts.add(part2)
            full_enchant_terms.add(term_title)

    if c.DEBUGGING and term_title in suppress_parts and term_title not in full_enchant_terms:
        print(f"[Suppress] Skipping sub-part match: {term_title}")
    
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
            if not duplicate or allow_dupes:
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

def process_text(text, allow_dupes=False, matched_terms=None):
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
            if int(stack_size) > 0 and utils.is_currency_or_scarab(term_title, item_type)
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
        print(c.matches_found, results)
        if non_dup_count % 5 == 0:
            print("=" * 27)
        attempt = 1
    else:
        status = f"{c.matches_not_found} Attempt: #{attempt}"
        sys.stdout.write('\r' + status + ' ' * 10)  # clear leftover chars
        sys.stdout.flush()
        attempt += 1

def write_csv_entry(text, timestamp, allow_dupes=False):
    global stack_sizes, body_armors
    write_header = not os.path.isfile(csv_file_path)

    matched_terms = get_matched_terms(text, allow_dupes)
    process_text(text, allow_dupes, matched_terms)

    def format_row(term_title, item_type, stack_size, prefix=""):
        # Helper to format each field with optional prefix (for debug)
        def maybe_add(fn):
            val = fn(term_title, item_type)
            return f"{prefix}{val}" if val else ""

        return [
            c.poe_league, c.poe_user,
            blueprint_layout, blueprint_area_level,
            maybe_add(utils.add_if_trinket),
            maybe_add(utils.add_if_replacement),
            maybe_add(utils.add_if_replica),
            maybe_add(utils.add_if_experimental),
            maybe_add(utils.add_if_weapon_enchant),
            maybe_add(utils.add_if_armor_enchant),
            maybe_add(utils.add_if_scarab),
            maybe_add(utils.add_if_currency),
            stack_size if (int(stack_size) > 0 and utils.is_currency_or_scarab(term_title, item_type)) else "",
            "",
            False,
            timestamp
        ]

    with open(csv_file_path, "a", newline='', encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        if write_header:
            writer.writerow([
                c.csv_league_header, c.csv_loggedby_header,
                c.csv_blueprint_header, c.csv_area_level_header,
                c.csv_trinket_header, c.csv_replacement_header,
                c.csv_replica_header, c.csv_experimented_header,
                c.csv_weapon_enchant_header, c.csv_armor_enchant_trinket_header,
                c.csv_scarab_trinket_header, c.csv_currency_trinket_header,
                c.csv_stack_size_trinket_header, c.csv_variant_trinket_header,
                c.csv_flag_trinket_header, c.csv_time_header
            ])

        for match in matched_terms:
            term_title = match["term"]
            duplicate = match["duplicate"]

            item_type = term_types.get(utils.smart_title_case(term_title))
            stack_size = stack_sizes.get(term_title)

            if allow_dupes or not duplicate:
                if c.DEBUGGING:
                    print(f"[WriteCSV] Writing row for term: {term_title}")

                # Write main CSV row
                writer.writerow(format_row(term_title, item_type, stack_size))

                # Write debug row if enabled
                if c.DEBUGGING and c.CSV_DEBUGGING:
                    writer.writerow(format_row(term_title, item_type, stack_size, prefix=lambda v: f"{v}: "))


#####################################################
# Captures the entire screen, afterwards using      #
# OCR reads the texts and checks for matches.       #
# If a match is found, it will save it in the .csv  #
#####################################################

def capture_once():
    bbox = get_poe_bbox()
    if not bbox:
        return
    
    screenshot_np = np.array(ImageGrab.grab(bbox=bbox))
    full_text, filtered = ocr_from_image(screenshot_np)



    os.makedirs(c.saves_dir, exist_ok=True)
    write_csv_entry(full_text, utils.now_timestamp(), allow_dupes=False)
    if c.ALWAYS_SHOW_CONSOLE:
        utils.bring_console_to_front()
  

#####################################################
# Captures the a snippet of the screen, afterwards  #
# using OCR reads the texts and checks for matches. #
# If a match is found, it will save it in the .csv  #
#####################################################

def capture_snippet():
    bbox = get_poe_bbox()
    if bbox is None:
        print(c.not_found_target_snippet_txt)
        exit()

    root = tk.Tk()
    root.attributes("-alpha", 0.3)
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.configure(background='black')

    start_x = start_y = end_x = end_y = 0
    rect_id = None

    canvas = tk.Canvas(root, cursor="cross", bg='gray')
    canvas.pack(fill=tk.BOTH, expand=True)

    def on_mouse_down(event):
        nonlocal start_x, start_y
        start_x, start_y = event.x, event.y

    def on_mouse_drag(event):
        nonlocal rect_id
        canvas.delete(rect_id)
        rect_id = canvas.create_rectangle(start_x, start_y, event.x, event.y, outline='red', width=2)

    def on_mouse_up(event):
        nonlocal end_x, end_y
        end_x, end_y = event.x, event.y
        root.quit()
        root.destroy()

        x1, y1 = min(start_x, end_x), min(start_y, end_y)
        x2, y2 = max(start_x, end_x), max(start_y, end_y)

        if x2 - x1 < 5 or y2 - y1 < 5:
            print(c.snippet_txt_too_small)
            return

        bbox = (x1, y1, x2, y2)
        screenshot_np = np.array(ImageGrab.grab(bbox))

        if screenshot_np is None or screenshot_np.size == 0:
            print(c.snippet_txt_failed)
            return

        full_text, filtered = ocr_from_image(screenshot_np, scale=2)

        
        h, w, _ = filtered.shape


        if c.DEBUGGING:
            boxes = pytesseract.image_to_boxes(filtered)
            for b in boxes.splitlines():
                b = b.split()
                char, x1, y1, x2, y2 = b[0], int(b[1]), int(b[2]), int(b[3]), int(b[4])
                
                cv2.rectangle(filtered, (x1, h - y1), (x2, h - y2), (0, 255, 0), 1)
                cv2.putText(filtered, char, (x1, h - y1 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            cv2.imshow("Filtered Snippet", filtered)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        os.makedirs(c.saves_dir, exist_ok=True)
        if c.DEBUGGING:
            os.makedirs(c.logs_dir, exist_ok=True)
            with open(f"{c.logs_dir}/ocr_snippet_{timestamp}.txt", "w", encoding="utf-8") as f:
                f.write(full_text)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        write_csv_entry(full_text, timestamp, allow_dupes=True)

    canvas.bind("<Button-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_drag)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)

    root.mainloop()
    if c.ALWAYS_SHOW_CONSOLE:
        utils.bring_console_to_front()

#####################################################
# Captures the a snippet of the top right corner of #
# the screen, afterwards OCR reads the texts and    #
# checks for matches between layouts and saves the  #
# monster level as area level                       #
#####################################################
def capture_layout():
    global blueprint_area_level, blueprint_layout, attempt
    
    screenshot = pyautogui.screenshot()
    full_width, full_height = screenshot.size

    cropped = screenshot.crop(utils.get_top_right_layout(full_width, full_height))

    # Run OCR on the cropped region
    text = utils.smart_title_case(pytesseract.image_to_string(cropped, config=r'--oem 3 --psm 6'))
    if c.DEBUGGING:
        print("OCR Text:\n", text)
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
    # if c.DEBUGGING:

    if found_layout and area_level:
        blueprint_area_level = area_level
        blueprint_layout = found_layout
        print("\n========== Result ==========")
        print(f"Layout: {found_layout}")
        print(f"Area Level: {area_level}")
        print("="*28)
        attempt = 1
    else:
        status = f"❌ Not found, try again. Attempt: #{attempt}"
        sys.stdout.write('\r' + status + ' ' * 20)
        sys.stdout.flush()
        attempt += 1

    if c.ALWAYS_SHOW_CONSOLE:
        utils.bring_console_to_front()

###############################################
# HOTKEY/KEYBIND HANDLING                     #
###############################################
def parse_hotkey(hotkey_str):
    keys = set()
    for part in hotkey_str.lower().split('+'):
        part = part.strip()

        # Modifiers
        if part == 'ctrl':
            keys.add(keyboard.Key.ctrl)
        elif part == 'shift':
            keys.add(keyboard.Key.shift)
        elif part == 'alt':
            keys.add(keyboard.Key.alt)

        # Function keys (f1..f12)
        elif part.startswith('f') and part[1:].isdigit():
            try:
                keys.add(getattr(keyboard.Key, part))
            except AttributeError:
                raise ValueError(f"Unsupported function key: {part}")

        # Single printable key (letters, numbers, symbols)
        elif len(part) == 1:
            keys.add(part.lower())

        else:
            raise ValueError(f"Unknown key: {part}")

    combo = frozenset(keys)
    if not combo:
        raise ValueError(f"Hotkey '{hotkey_str}' parsed to an empty set!")
    return combo

hotkeys = {
    'capture': parse_hotkey(c.capture_key),
    'layout_capture': parse_hotkey(c.layout_capture_key),
    'snippet': parse_hotkey(c.snippet_key),
    'exit': parse_hotkey(c.exit_key),
    'debug': parse_hotkey(c.enable_debugging_key),
}


hotkey_sets = list(hotkeys.values())
if len(hotkey_sets) != len(set(hotkey_sets)):
    raise ValueError("Duplicate hotkeys found in configuration. Please ensure all hotkeys are unique.")

def main():
    global listener_ref
    
    print(c.info_show_keys_capture)
    print(c.info_show_keys_snippet)
    print(c.info_show_keys_layout)
    print(c.info_show_keys_exit)
    exit_event = threading.Event()

    def handle_capture():
        validateAttempt(c.capturing_prompt)
        capture_once()

    def handle_snippet():
        validateAttempt(c.capturing_prompt)
        capture_snippet()

    def handle_layout_capture():
        validateAttempt(c.layout_prompt)
        capture_layout()

    def handle_exit():
        print(c.exiting_prompt)
        exit_event.set()
        if listener_ref:
            listener_ref.stop()  # stops pynput listener

    def handle_debugging():
        c.DEBUGGING = not c.DEBUGGING
        print("Debugging: {}".format("Enabled" if c.DEBUGGING else "Disabled"))

    # Hotkey -> action mapping
    actions = {
        'capture': handle_capture,
        'layout_capture': handle_layout_capture,
        'snippet': handle_snippet,
        'exit': handle_exit,
        'debug': handle_debugging
    }


    # Listener functions
    pressed_keys = set()
    fired_combos = set()

    def on_press(key):
        before_count = len(pressed_keys)

        if isinstance(key, keyboard.Key):
            pressed_keys.add(key)
        else:
            try:
                pressed_keys.add(key.char.lower())
            except AttributeError:
                return

        for name, combo in hotkeys.items():
            if combo.issubset(pressed_keys) and name not in fired_combos:
                if len(pressed_keys) > before_count:
                    fired_combos.add(name)
                    # Run handler in a separate thread
                    threading.Thread(target=actions[name], daemon=True).start()

    def on_release(key):
        if isinstance(key, keyboard.Key):
            pressed_keys.discard(key)
        else:
            try:
                pressed_keys.remove(key.char.lower())
            except (AttributeError, KeyError):
                pass

        # Reset combos when any key in them is released
        to_remove = {n for n, combo in hotkeys.items() if not combo.issubset(pressed_keys)}
        fired_combos.difference_update(to_remove)
    
    
    print(c.listening_keybinds_txt)
    listener_ref = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener_ref.start()

    try:
        while not exit_event.is_set():
            exit_event.wait(0.1)
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting.")
        listener_ref.stop()


def validateAttempt(print_text):
    global attempt
    if attempt == 1:
        print(print_text)


if __name__ == "__main__":
    main()
