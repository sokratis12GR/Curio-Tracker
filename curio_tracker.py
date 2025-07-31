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

stack_size = 0

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

# Updated category imports
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

term_types = load_csv_with_types(c.file_name)
all_terms = set(term_types.keys())

seen_matches = set()

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

def extract_currency_value(text, matched_term, term_types):
    if term_types.get(matched_term) != "Currency":
        return None

    # Split text into lines
    lines = text.splitlines()

    # Find the line index where matched_term appears (case insensitive)
    idx = None
    for i, line in enumerate(lines):
        if matched_term.lower() in line.lower():
            idx = i
            break

    if idx is None:
        return None  # term not found in text lines

    # Look for ratio pattern in next few lines (say next 2 lines)
    for j in range(idx + 1, min(idx + 3, len(lines))):
        match = re.search(r"\b(\d+)\s*/\s*(\d+)\b", lines[j])
        if match:
            current = int(match.group(1))
            maximum = int(match.group(2))
            return (current, maximum)

    return None

#################################################
# Check if a term or combo term is in the text. # 
#################################################

def is_term_match(term, text, use_fuzzy=True):
    def clean_word(word):
        return smart_title_case(word.strip(string.punctuation))

    if ";" in term:
        part1, part2 = [p.strip() for p in term.split(";", 1)]
        pattern = rf"(?i){re.escape(part1)}[\s\S]{{0,100}}?{re.escape(part2)}"
        return bool(re.search(pattern, text))
    else:
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, text, re.IGNORECASE):
            return True
        if use_fuzzy:
            words = [clean_word(w) for w in text.split()]
            term_clean = smart_title_case(term)
            max_len_diff = 2
            candidates = [w for w in words if abs(len(w) - len(term_clean)) <= max_len_diff]
            close = get_close_matches(term_clean, candidates, n=1, cutoff=0.83)
            if close:
                print(f"[Fuzzy match] Term: '{term}' ≈ '{close[0]}'")
                return True
    return False


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

    matched = []
    global non_dup_count

    terms_source = term_types.keys() if use_fuzzy else all_terms

    for term in terms_source:
        term_title = smart_title_case(term)
        if is_term_match(term_title, text, use_fuzzy=use_fuzzy):
            duplicate = is_duplicate_recent_entry(term_title)
            if allow_dupes or not duplicate:
                matched.append((term_title, duplicate))
                if not duplicate or allow_dupes:
                    non_dup_count += 1
            else:
                # If duplicates not allowed and duplicate found, still append with flag
                matched.append((term_title, True))
    return matched

def process_text(text, allow_dupes=False):
    results = []
    matched_terms = get_matched_terms(text, allow_dupes=allow_dupes)

    for term_title, duplicate in matched_terms:
        if duplicate and not allow_dupes:
            results.append(f"{term_title} (Duplicate - Skipping)")
        else:
            results.append(term_title)

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
    global stack_size
    write_header = not os.path.isfile(csv_file_path)

    matched_terms = get_matched_terms(text, allow_dupes=allow_dupes, use_fuzzy=True)
    
    for matched_term, duplicate in matched_terms:
        ratio = extract_currency_value(smart_title_case(text), matched_term, term_types)
        if ratio:
            stack_size = f"{ratio[0]}"
            if c.DEBUGGING:
                print(f"Ratio for {matched_term}: {ratio[0]}/{ratio[1]}")
        else:
            stack_size = 0
            if c.DEBUGGING:
                print("[Currency Ratio] None found.")

    process_text(text, allow_dupes)


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
            item_type = term_types.get(smart_title_case(term_title))  # assuming keys lowercase
            # Only write if allow_dupes or not duplicate
            if allow_dupes or not duplicate:
                writer.writerow([
                    user.poe_league, user.poe_user,
                    blueprint_layout, blueprint_area_level,
                    addIfTrinket(term_title, item_type),
                    addIfReplacement(term_title, item_type),
                    addIfReplica(term_title, item_type),
                    addIfExperimental(term_title, item_type),
                    addIfEnchant(term_title, item_type),
                    addIfEnchant(term_title, item_type),
                    addIfScarab(term_title, item_type),
                    addIfCurrency(term_title, item_type),
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
    global stack_size

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
    global stack_size

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

        if c.DEBUGGING:
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
    return term if type == "Trinket" else ""

def addIfReplacement(term, type):
    return term if type == "Replacement" else ""

def addIfReplica(term, type):
    return term if type == "Replica" else ""

def addIfExperimental(term, type):
    return term if type == "Experimental" else ""

def addIfEnchant(term, type):
    return term if type == "Enchants" else ""

def addIfScarab(term, type):
    return term if type == "Scarab" else ""

def addIfCurrency(term, type):
    return term if type == "Currency" else ""

def isCurrencyOrScarab(term, type):
    return type == "Currency" or type == "Scarab"

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

    # Search for layout keyword
    found_layout = None
    for keyword in c.layout_keywords:
        if smart_title_case(keyword) in text:
            found_layout = keyword
            blueprint_layout = keyword
            break

    # Search for monster level using regex
    match = re.search(r"Monster Level[: ]+(\d+)", text, re.IGNORECASE)
    area_level = match.group(1) if match else "Not found"

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


# If you dislike F2 and F3 to be capture/exit feel free to change them in (config.py)
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
