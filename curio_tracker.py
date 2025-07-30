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
import csv
import time
import os
import config as c
from datetime import datetime
from termcolor import colored

# Set path to tesseract executable (Check README)
pytesseract.pytesseract.tesseract_cmd = c.tesseract_path

os.makedirs(c.logs_dir, exist_ok=True)
os.makedirs(c.saves_dir, exist_ok=True)

csv_file_path = c.csv_file_path

# default values in case they only run area lvl 83 blueprints
blueprint_area_level = c.default_bp_lvl
blueprint_layout = c.default_bp_area
stack_size = 0

# Updated category imports
def load_csv_with_types(file_path):
    term_types = {}
    with open(file_path, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if len(row) >= 2:
                term, type_name = row[0].strip(), row[1].strip()
                term_types[term.upper()] = type_name
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

    return cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2RGB)

def process_text(text):
    matches = [term for term in all_terms if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE)]
    highlighted = text
    for term in sorted(all_terms, key=len, reverse=True):
        highlighted = re.sub(
            rf"(?i)\b({re.escape(term)})\b",
            lambda m: colored(m.group(1), "green", attrs=["bold"]),
            highlighted
        )

    if matches:
        print(c.matches_found, matches)
    else:
        print(c.matches_not_found)


def capture_once():
    bbox = get_poe_bbox()
    if not bbox:
        return
    screenshot = ImageGrab.grab(bbox=bbox)
    screenshot_np = np.array(screenshot)
    filtered = filter_item_text(screenshot_np)
    text = pytesseract.image_to_string(filtered, config="--psm 6", lang="eng")
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
    text_upper = text.upper()
    matched_terms_this_run = set()

    write_header = not os.path.isfile(csv_file_path)

    with open(csv_file_path, "a", newline='', encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        if write_header:
            writer.writerow([c.csv_league_header, c.csv_loggedby_header, # Static Values (Determined by config.py)
                c.csv_blueprint_header, c.csv_area_level_header,
                c.csv_trinket_header,
                c.csv_replacement_header,
                c.csv_replica_header,
                c.csv_experimented_header,
                c.csv_weapon_enchant_header,
                c.csv_armor_enchant_trinket_header,
                c.csv_scarab_trinket_header,
                c.csv_currency_trinket_header,
                c.csv_stack_size_trinket_header,
                c.csv_variant_trinket_header,
                c.csv_flag_trinket_header,
                c.csv_time_header # Extra Row for Time validation, should be excluded when importing the data.
                ])
        
        for term_upper, item_type in term_types.items(): # Term_Upper is the matching word in the csv file for valid entries/terms.
            if term_upper in text_upper and term_upper not in matched_terms_this_run:
                term_title = term_upper.title()
                writer.writerow([c.poe_league, c.poe_user, 
                    blueprint_layout, blueprint_area_level, # Should persist for same blueprint curio checks, updates per keybind press on start of heist.
                    isTrinket(term_title, item_type),
                    isReplacement(term_title, item_type),
                    isReplica(term_title, item_type),
                    isExperimental(term_title, item_type),
                    isEnchant(term_title, item_type),  # Armor and Weapon Enchants will be saved together as one, will review a better solution
                    isEnchant(term_title, item_type), # Armor and Weapon Enchants will be saved together as one, will review a better solution
                    isScarab(term_title, item_type),
                    isCurrency(term_title, item_type),
                    "" if stack_size == 0 else stack_size,
                    "",
                    False,
                    timestamp])
                matched_terms_this_run.add(term_title)

    write_header = not os.path.isfile(csv_file_path)

    process_text(text)

def isTrinket(term, type):
    return term if type == "Trinket" else ""

def isReplacement(term, type):
    return term if type == "Replacement" else ""

def isReplica(term, type):
    return term if type == "Replica" else ""

def isExperimental(term, type):
    return term if type == "Experimental" else ""

def isEnchant(term, type):
    return term if type == "Enchants" else ""

def isScarab(term, type):
    return term if type == "Scarab" else ""

def isCurrency(term, type):
    return term if type == "Currency" else ""

def capture_layout():
    screenshot = pyautogui.screenshot()
    full_width, full_height = screenshot.size

    # Define the top-right crop region
    left = full_width - c.TOP_RIGHT_CUT_WIDTH
    top = 0
    right = full_width
    bottom = c.TOP_RIGHT_CUT_HEIGHT

    cropped = screenshot.crop((left, top, right, bottom))

    # Run OCR on the cropped region
    text = pytesseract.image_to_string(cropped)
    if c.DEBUGGING:
        print("OCR Text:\n", text)

    # Search for layout keyword
    found_layout = None
    for keyword in c.layout_keywords:
        if keyword.lower() in text.lower():
            found_layout = keyword
            blueprint_layout = keyword
            break

    # Search for monster level using regex
    match = re.search(r"Monster Level[: ]+(\d+)", text, re.IGNORECASE)
    area_level = match.group(1) if match else "Not found"

    # Report results
    # if c.DEBUGGING:
    if found_layout and area_level:
        print("========== Result ==========")
        print(f"Layout: {found_layout}")
        print(f"Area Level: {area_level}")
        print("============================")
    else:
        print("❌ Not found, try again.")


# If you dislike F2 and F3 to be capture/exit feel free to change them in (config.py)
def main():
    print(c.info_show_keys_capture)
    # print(c.info_show_keys_snippet) STILL WIP NOT ENABLED, added support for it in the config but that's it.
    print(c.info_show_keys_layout)
    print(c.info_show_keys_exit)

    while True:
        if keyboard.is_pressed(c.capture_key):
            print(c.capturing_prompt)
            capture_once()
            time.sleep(0.5)

        if keyboard.is_pressed(c.layout_capture_key):
            print(c.layout_prompt)
            capture_layout()
            time.sleep(0.5)

        if keyboard.is_pressed(c.exit_key):
            print(c.exiting_prompt)
            break

        time.sleep(0.1)

if __name__ == "__main__":
    main()
