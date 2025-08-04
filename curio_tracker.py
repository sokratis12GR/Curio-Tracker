import threading
import tkinter as tk
import keyboard
import pyautogui
import cv2
import numpy as np
import pytesseract
from PIL import ImageGrab
import pygetwindow as gw
import re
import string
import csv
import time
from difflib import get_close_matches
import os
from datetime import datetime, timedelta
import config as c
from datetime import datetime
from termcolor import colored
import user_settings as user

# Set path to tesseract executable (Check README)
pytesseract.pytesseract.tesseract_cmd = user.tesseract_path

os.makedirs(c.logs_dir, exist_ok=True)
os.makedirs(c.saves_dir, exist_ok=True)

csv_file_path = c.csv_file_path

# default values in case they only run area lvl 83 blueprints
blueprint_area_level = c.default_bp_lvl
blueprint_layout = c.default_bp_area

stack_sizes = {}

non_dup_count = 0

####################################################################
# Fixes title case issues like checking for items with apostrophes #
####################################################################
def smart_title_case(text):
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    text = re.sub(r"(')S\b", r"\1s", text)

    def fix_word(word):
        if word.lower().endswith("'s") and len(word) > 2:
            base = word[:-2]
            suffix = word[-2:]
            # Capitalize first letter of base, lowercase rest, suffix lowercase
            return base[:1].upper() + base[1:].lower() + suffix.lower()
        else:
            return word[:1].upper() + word[1:].lower()

    # Apply smart title casing to each word
    return re.sub(r"\b\w+'?s?\b", lambda m: fix_word(m.group(0)), text)


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
                term_key = smart_title_case(raw_term)
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

def get_poe_bbox():
    windows = [w for w in gw.getWindowsWithTitle(c.target_application) if w.visible]
    if not windows:
        print(c.not_found_target_txt)
        return None
    win = windows[0]
    return (win.left, win.top, win.left + win.width, win.top + win.height)
#############################################################
# Saves the information on the screen based on colors       #
# which is afterwards extracted as text                     #
#############################################################
def filter_item_text(image_np):
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


    return cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2RGB)


#####################################
# helpers for body armour ordering  # 
#####################################
def normalize_for_search(s: str) -> str:
    s = s.replace("—", " ").replace("“", " ").replace("”", " ")
    s = re.sub(r"[^\w\s%';]", " ", s)  # keep %, ', ; for precise matching
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()

def build_body_armor_regex(body_armors):
    normalized = []
    for a in body_armors:
        norm = normalize_for_search(smart_title_case(a))
        if norm:
            normalized.append(re.escape(norm))
    if not normalized:
        return None
    normalized.sort(key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(normalized) + r")\b", re.IGNORECASE)

body_armor_regex = build_body_armor_regex(body_armors)

def find_first_body_armor_pos(text):
    norm_text = normalize_for_search(text) 
    # 1. exact via regex
    if body_armor_regex:
        match = body_armor_regex.search(norm_text)
        if match:
            if c.DEBUGGING:
                print(f"[BodyArmor] Exact match '{match.group(1)}' at {match.start()} in normalized text: {norm_text!r}")
            return match.start()

    # 2. fuzzy fallback: try multi-word body armours first, then single-word
    tokens = [(tok.group(0), tok.start()) for tok in re.finditer(r"\b[\w%']+\b", norm_text)]
    token_words = [tok.lower() for tok, _ in tokens]
    earliest = None
    for raw in body_armors:
        armour_title = smart_title_case(raw).strip()
        norm_name = normalize_for_search(armour_title)
        parts = norm_name.split()
        if not parts:
            continue

        if len(parts) == 1:
            # single-word fuzzy: match against tokens
            close = get_close_matches(parts[0], token_words, n=1, cutoff=0.8)
            if close:
                best = close[0]
                for tok, pos in tokens:
                    if tok.lower() == best:
                        if earliest is None or pos < earliest:
                            earliest = pos
                            if c.DEBUGGING:
                                print(f"[BodyArmor] Fuzzy single-word match '{armour_title}' ≈ '{tok}' at {pos}")
                        break
        else:
            # multi-word: find a sequence where each part fuzzily matches successive tokens
            for i in range(len(tokens) - len(parts) + 1):
                match = True
                for offset, part in enumerate(parts):
                    tok = tokens[i + offset][0].lower()
                    if not get_close_matches(part, [tok], n=1, cutoff=0.7):
                        match = False
                        break
                if match:
                    pos = tokens[i][1]
                    if earliest is None or pos < earliest:
                        earliest = pos
                        if c.DEBUGGING:
                            seq = " ".join(tokens[i + j][0] for j in range(len(parts)))
                            print(f"[BodyArmor] Fuzzy multi-word match '{armour_title}' ≈ '{seq}' at {pos}")
                    break  # stop after first sequence for this armour
    return earliest

def find_first_enchant_piece_pos(term_title, text):
    # take the part before ';'
    part1 = term_title.split(";", 1)[0].strip()
    # normalize both piece and text the same way
    norm_piece = normalize_for_search(smart_title_case(part1))
    norm_text = normalize_for_search(text)
    # simple whole-word search
    pattern = rf"\b{re.escape(norm_piece)}\b"
    m = re.search(pattern, norm_text, re.IGNORECASE)
    return m.start() if m else None

MAX_DISTANCE = 200 # To play around and see if body armors would need more positions

def is_armor_enchant_by_body_armor_order(term_title, text):
    first_body = find_first_body_armor_pos(text)
    first_enchant = find_first_enchant_piece_pos(term_title, text)
    if c.DEBUGGING:
        print(f"[OrderCheck] body_pos={first_body}, enchant_pos={first_enchant}, term='{term_title}'")
    if first_body is not None and first_enchant is not None:
        distance = first_enchant - first_body
        return 0 <= distance <= MAX_DISTANCE
    return False

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

    # Try to find "x/y" in current and next 2 lines
    for j in range(idx, min(idx + 3, len(lines))):
        match = re.search(r"\b(\d+)\s*/\s*(\d+)\b", lines[j])
        if match:
            raw_current = match.group(1)
            raw_maximum = match.group(2)

            try:
                current = int(raw_current)
                maximum = int(raw_maximum)
            except ValueError:
                continue  # skip invalid number strings

            # Accept valid values like 19/20
            if 0 < current <= maximum <= 20:
                return (current, maximum)

            # Try to correct OCR errors (e.g. 419/20 → 9/20)
            if maximum == 20:
                current = int(str(current)[-1])  # take last digit
                if current <= 20:
                    return (current, 20)

            return None  # invalid even after fix

    # Fallback: pattern not found at all
    return (1, 20)

#################################################
# Check if a term or combo term is in the text. # 
#################################################
def is_term_match(term, text, use_fuzzy=False):
    def normalize_lines(text):
        return [normalize_for_search(line) for line in text.splitlines()]

    raw_term = next((k for k in term_types if smart_title_case(k) == term), None)
    term_type = term_types.get(raw_term, "")
    term_type_cmp = smart_title_case(term_type) if isinstance(term_type, str) else ""

    # Handle enchant combo terms
    if ";" in term and term_type_cmp in (c.ARMOR_ENCHANT_TYPE, c.WEAPON_ENCHANT_TYPE):
        part1, part2 = [normalize_for_search(p.strip()) for p in term.split(";", 1)]
        norm_lines = normalize_lines(text)

        # Try to find part1 followed by part2 within N lines
        for i in range(len(norm_lines)):
            if part1 in norm_lines[i]:
                for j in range(1, 3):  # allow match across next 2 lines
                    if i + j < len(norm_lines) and part2 in norm_lines[i + j]:
                        if c.DEBUGGING:
                            print(f"[EnchantCombo] Found '{part1}' then '{part2}' on lines {i} and {i+j}")
                        return True
        return False

    # Standard term matching
    def find_piece_positions(piece):
        piece_title = smart_title_case(piece)
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
                    if smart_title_case(tok) == smart_title_case(best):
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
        term_title = smart_title_case(term)
        if is_term_match(term_title, text, use_fuzzy=use_fuzzy):
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
            part1, part2 = [smart_title_case(p.strip()) for p in term_title.split(";", 1)]
            suppress_parts.add(part1)
            suppress_parts.add(part2)
            full_enchant_terms.add(term_title)

    if c.DEBUGGING and term_title in suppress_parts and term_title not in full_enchant_terms:
        print(f"[Suppress] Skipping sub-part match: {term_title}")
    
    matched = []
    for term_title, duplicate in all_candidates:
        if term_title in suppress_parts and term_title not in full_enchant_terms:
            continue 

        if allow_dupes or not duplicate:
            matched.append((term_title, duplicate))
            if not duplicate or allow_dupes:
                non_dup_count += 1
        else:
            matched.append((term_title, True))  # keep the duplicate flag
    return matched

def process_text(text, allow_dupes=False, matched_terms=None):
    global stack_sizes
    results = []

    if matched_terms is None:
        matched_terms = get_matched_terms(text, allow_dupes=allow_dupes)

    for term_title, duplicate in matched_terms:
        ratio = extract_currency_value(smart_title_case(text), term_title, term_types)
        if ratio:
            stack_size = f"{ratio[0]}"
            stack_sizes[term_title] = stack_size
            if c.DEBUGGING:
                print(f"Ratio for {term_title}: {ratio[0]}/{ratio[1]}")
        else:
            stack_size = 0
            stack_sizes[term_title] = stack_size  # Save 0 if no ratio found
            if c.DEBUGGING:
                print("[Currency Ratio] None found.")

    #### DUPE CHECKING 
    for term_title, duplicate in matched_terms:
        stack_size = int(stack_sizes.get(term_title))
        stack_size_txt = (c.stack_size_found.format(stack_size) if stack_size > 0 else "")
        if duplicate and not allow_dupes:
            results.append(f"{term_title} (Duplicate - Skipping)" + stack_size_txt)
        else:
            results.append(term_title + stack_size_txt)

    if c.DEBUGGING:
        highlighted = smart_title_case(text)
        for term in sorted(all_terms, key=len, reverse=True):
            pattern = rf"(?i)\b({re.escape(smart_title_case(term))})\b"
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
    else:
        print(c.matches_not_found)



def write_csv_entry(text, timestamp, allow_dupes=False):
    global stack_sizes, body_armors
    write_header = not os.path.isfile(csv_file_path)

    matched_terms = get_matched_terms(text, allow_dupes=allow_dupes, use_fuzzy=False)

    process_text(text, allow_dupes, matched_terms)


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

        for term_title, duplicate in matched_terms:
            item_type = term_types.get(smart_title_case(term_title)) 
            stack_size = stack_sizes.get(term_title)

            weapon_enchant_flag = ""
            armor_enchant_flag = ""

            is_enchant_combo = item_type in (c.ARMOR_ENCHANT_TYPE, c.WEAPON_ENCHANT_TYPE)


            if is_enchant_combo:
                if is_armor_enchant_by_body_armor_order(term_title, text):
                    armor_enchant_flag = term_title
                else:
                    weapon_enchant_flag = term_title
            else:
                weapon_enchant_flag = addIfWeaponEnchant(term_title, item_type)
                armor_enchant_flag = addIfArmorEnchant(term_title, item_type)

            if allow_dupes or not duplicate:
                if c.DEBUGGING:
                    print(f"[WriteCSV] Writing row for term: {term_title}")
                writer.writerow([
                    user.poe_league, user.poe_user,
                    blueprint_layout, blueprint_area_level,
                    addIfTrinket(term_title, item_type),
                    addIfReplacement(term_title, item_type),
                    addIfReplica(term_title, item_type),
                    addIfExperimental(term_title, item_type),
                    weapon_enchant_flag,
                    armor_enchant_flag,
                    addIfScarab(term_title, item_type),
                    addIfCurrency(term_title, item_type),
                    stack_size if (int(stack_size) > 0 and isCurrencyOrScarab(term_title, item_type)) else "",
                    "",
                    False,
                    timestamp
                ])
            if c.DEBUGGING and c.CSV_DEBUGGING and (allow_dupes or not duplicate):
                writer.writerow([
                    user.poe_league, user.poe_user,
                    blueprint_layout, blueprint_area_level,
                    "Trinket: " + addIfTrinket(term_title, item_type),
                    "Replacement: " + addIfReplacement(term_title, item_type),
                    "Replica: " + addIfReplica(term_title, item_type),
                    "Experimental: " + addIfExperimental(term_title, item_type),
                    "WeaponEnchant: " + weapon_enchant_flag,
                    "ArmorEnchant: " + armor_enchant_flag,
                    "Scarab: " + addIfScarab(term_title, item_type),
                    "Currency: " + addIfCurrency(term_title, item_type),
                    stack_size if (int(stack_size) > 0 and isCurrencyOrScarab(term_title, item_type)) else "",
                    "",
                    False,
                    timestamp
                ])


#####################################################
# Captures the entire screen, afterwards using      #
# OCR reads the texts and checks for matches.       #
# If a match is found, it will save it in the .csv  #
#####################################################

def capture_once():
    bbox = get_poe_bbox()
    if not bbox:
        return
    screenshot = ImageGrab.grab(bbox=bbox)
    screenshot_np = np.array(screenshot)
    filtered = filter_item_text(screenshot_np)
    text = smart_title_case(pytesseract.image_to_string(filtered, config="--psm 6", lang="eng"))

    if c.DEBUGGING:
        cv2.imshow("Filtered Mask", filtered)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if c.DEBUGGING:
        os.makedirs(c.logs_dir, exist_ok=True)
        with open(f"{c.logs_dir}/ocr_poe_{timestamp}.txt", "w", encoding="utf-8") as f:
            f.write(text)

    os.makedirs(c.saves_dir, exist_ok=True)
    write_csv_entry(text, timestamp)
  

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
        screenshot = ImageGrab.grab(bbox)
        screenshot_np = np.array(screenshot)

        if screenshot_np is None or screenshot_np.size == 0:
            print(c.snippet_txt_failed)
            return

        filtered = filter_item_text(screenshot_np)
        text = smart_title_case(pytesseract.image_to_string(filtered, config="--psm 6", lang="eng"))
        
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
                f.write(text)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        write_csv_entry(text, timestamp, allow_dupes=True)

    canvas.bind("<Button-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_drag)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)

    root.mainloop()

def addIfTrinket(term, type):
    return term if type == c.TRINKET_TYPE else ""

def addIfReplacement(term, type):
    return term if type == c.REPLACEMENT_TYPE else ""

def addIfReplica(term, type):
    return term if type == c.REPLICA_TYPE else ""

def addIfExperimental(term, type):
    return term if type == c.EXPERIMENTAL_TYPE else ""

def addIfWeaponEnchant(term, type):
    return term if type == c.ARMOR_ENCHANT_TYPE else ""

def addIfArmorEnchant(term, type):
    return term if type == c.WEAPON_ENCHANT_TYPE else ""

def addIfScarab(term, type):
    return term if type == c.SCARAB_TYPE else ""

def addIfCurrency(term, type):
    return term if type == c.CURRENCY_TYPE else ""

def isCurrencyOrScarab(term, type):
    return type == c.CURRENCY_TYPE or type == c.SCARAB_TYPE

def capture_layout():
    global blueprint_area_level
    global blueprint_layout
    screenshot = pyautogui.screenshot()
    full_width, full_height = screenshot.size

    # Define the top-right crop region
    left = full_width - c.TOP_RIGHT_CUT_WIDTH
    top = 0
    right = full_width
    bottom = c.TOP_RIGHT_CUT_HEIGHT

    cropped = screenshot.crop((left, top, right, bottom))

    # Run OCR on the cropped region
    text = smart_title_case(pytesseract.image_to_string(cropped, config=r'--oem 3 --psm 6'))
    if c.DEBUGGING:
        print("OCR Text:\n", text)
        cropped.show()

    # Search for layout keyword
    found_layout = None
    for keyword in c.layout_keywords:
        if smart_title_case(keyword) in text:
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
        print("========== Result ==========")
        print(f"Layout: {found_layout}")
        print(f"Area Level: {area_level}")
        print("="*27)
    else:
        print("❌ Not found, try again.")


# HOTKEY/KEYBIND HANDLING
def main():
    print(c.info_show_keys_capture)
    print(c.info_show_keys_snippet)
    print(c.info_show_keys_layout)
    print(c.info_show_keys_exit)
    exit_event = threading.Event()

    def handle_capture():
        print(c.capturing_prompt)
        capture_once()

    def handle_snippet():
        print(c.capturing_prompt)
        capture_snippet()

    def handle_layout_capture():
        print(c.layout_prompt)
        capture_layout()

    def handle_exit():
        print(c.exiting_prompt)
        exit_event.set()
        keyboard.unhook_all_hotkeys()

    def handle_debugging():
        c.DEBUGGING = not c.DEBUGGING
        print("Debugging: {}".format("Enabled" if c.DEBUGGING else "Disabled"))

    # Register global hotkeys
    keyboard.add_hotkey(user.capture_key, handle_capture)
    keyboard.add_hotkey(user.layout_capture_key, handle_layout_capture)
    keyboard.add_hotkey(user.exit_key, handle_exit)
    keyboard.add_hotkey(user.snippet_key, handle_snippet)
    keyboard.add_hotkey(user.enable_debugging_key, handle_debugging)

    # Keep the program running
    print("Listening for keybinds... Press your exit key to stop.")
    try:
        while not exit_event.is_set():
            # Keep looping to allow hotkeys to run in background
            exit_event.wait(0.1)
    except KeyboardInterrupt:
        print("Interrupted by user. Exiting.")
        keyboard.unhook_all_hotkeys()


if __name__ == "__main__":
    main()
