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

    # Optional morphology
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
            writer.writerow([c.csv_time_header, c.csv_type_header, c.csv_value_header])
        
        for term_upper, item_type in term_types.items():
            if term_upper in text_upper and term_upper not in matched_terms_this_run:
                writer.writerow([timestamp, item_type, term_upper])
                matched_terms_this_run.add(term_upper)

    write_header = not os.path.isfile(csv_file_path)

    process_text(text)

# If you dislike F2 and F3 to be capture/exit feel free to change them here
def main():
    print(c.info_show_keys_1)
    print(c.info_show_keys_2)

    while True:
        if keyboard.is_pressed(c.capture_key):
            print(c.capturing_prompt)
            capture_once()
            time.sleep(0.5)

        if keyboard.is_pressed(c.exit_key):
            print(c.exiting_prompt)
            break

        time.sleep(0.1)

if __name__ == "__main__":
    main()