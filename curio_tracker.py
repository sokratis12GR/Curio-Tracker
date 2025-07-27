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
from datetime import datetime
from termcolor import colored

# Set path to tesseract executable (Check README)
pytesseract.pytesseract.tesseract_cmd = r"D:\Dev\Tesseract-OCR\tesseract.exe"

# Enable if you want extra information and a popup of the screenshot
DEBUGGING = False

os.makedirs("logs", exist_ok=True)
os.makedirs("saved", exist_ok=True)

csv_file_path = "saved/matches.csv"

def check_file_exists():
    return not os.path.isfile(csv_file_path)

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

term_types = load_csv_with_types("AllValid.csv")
all_terms = set(term_types.keys())

seen_matches = set()

def get_poe_bbox():
    windows = [w for w in gw.getWindowsWithTitle("Path of Exile") if w.visible]
    if not windows:
        print("❌ Path of Exile window not found.")
        return None
    win = windows[0]
    return (win.left, win.top, win.left + win.width, win.top + win.height)



def filter_item_text(image_np):
    img_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    # Unique: #AF6025
    lower_orange = np.array([5, 100, 100])
    upper_orange = np.array([25, 255, 255])

    # Rare: #D9C850
    lower_yellow = np.array([20, 80, 150])
    upper_yellow = np.array([40, 255, 255])

    # Currency: #AA9E82
    lower_currency = np.array([15, 20, 90])
    upper_currency = np.array([45, 100, 220])

    # Scarabs (new gray): #B7B8B8 → HSV(0, 3, 184)
    lower_scarab = np.array([0, 0, 150])
    upper_scarab = np.array([180, 10, 255])

    # Enchants (blue-gray): #5C7E9D
    lower_enchant = np.array([95, 15, 70])
    upper_enchant = np.array([130, 90, 240])
    
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
        print("✅ Matches found:", matches)
    else:
        print("❌ No matches found.")


def capture_once():
    bbox = get_poe_bbox()
    if not bbox:
        return
    screenshot = ImageGrab.grab(bbox=bbox)
    screenshot_np = np.array(screenshot)
    filtered = filter_item_text(screenshot_np)
    text = pytesseract.image_to_string(filtered, config="--psm 6", lang="eng")
    if DEBUGGING:
        cv2.imshow("Filtered Mask", filtered)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if DEBUGGING:
        os.makedirs("logs", exist_ok=True)
        with open(f"logs/ocr_poe_{timestamp}.txt", "w", encoding="utf-8") as f:
            f.write(text)

    os.makedirs("saved", exist_ok=True)
    text_upper = text.upper()
    matched_terms_this_run = set()

    write_header = not os.path.isfile(csv_file_path)

    with open(csv_file_path, "a", newline='', encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)

        if write_header:
            writer.writerow(["Time", "Type", "Value"])
        
        for term_upper, item_type in term_types.items():
            if term_upper in text_upper and term_upper not in matched_terms_this_run:
                writer.writerow([timestamp, item_type, term_upper])
                matched_terms_this_run.add(term_upper)

    write_header = not os.path.isfile(csv_file_path)

    process_text(text)

# If you dislike F2 and F3 to be capture/exit feel free to change them here
def main():
    print("🖼️ Press F2 to capture Path of Exile window.")
    print("❌ Press F3 to exit the script.\n")

    while True:
        if keyboard.is_pressed("f2"):
            print("📸 Capturing screen...")
            capture_once()
            time.sleep(0.5)

        if keyboard.is_pressed("f3"):
            print("👋 Exiting.")
            break

        time.sleep(0.1)

if __name__ == "__main__":
    main()
