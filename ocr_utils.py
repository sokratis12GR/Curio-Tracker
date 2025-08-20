import re
import os
import sys
import math
import ctypes
import pytesseract
import shutil
from datetime import datetime
from difflib import get_close_matches
import config as c


################################################################################
# Sets the Tesseract OCR location to either PATH, Bundled or User Set Location #
################################################################################
def set_tesseract_path():
    tesseract_bin = None

    # 1. Attempt to find from PATH
    path_from_system = shutil.which("tesseract")
    if path_from_system and os.path.isfile(path_from_system):
        tesseract_bin = path_from_system

    # 2. If not in PATH, attempt PyInstaller bundled executable
    if not tesseract_bin and hasattr(sys, "_MEIPASS"):
        bundled_path = os.path.join(sys._MEIPASS, "tesseract", "tesseract.exe")
        if os.path.isfile(bundled_path):
            tesseract_bin = bundled_path

    # 3. Local dev fallback
    if not tesseract_bin:
        dev_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "tesseract",
            "tesseract.exe"
        )
        if os.path.isfile(dev_path):
            tesseract_bin = dev_path

    # 4. Last fallback: hardcoded/config path
    if not tesseract_bin or not os.path.isfile(tesseract_bin):
        tesseract_bin = os.path.normpath(c.pytesseract_path)

    # --- Apply and verify ---
    pytesseract.pytesseract.tesseract_cmd = tesseract_bin
    print("[DEBUG] Tesseract binary set to:", tesseract_bin)

    tesseract_dir = os.path.dirname(tesseract_bin)
    tessdata_dir = os.path.join(tesseract_dir, "tessdata")

    if os.path.isdir(tessdata_dir):
        os.environ["TESSDATA_PREFIX"] = tessdata_dir
        print("[DEBUG] TESSDATA_PREFIX set to:", tessdata_dir)
        eng_path = os.path.join(tessdata_dir, "eng.traineddata")
        if os.path.isfile(eng_path):
            print("[DEBUG] eng.traineddata found:", eng_path)
        else:
            print("[ERROR] eng.traineddata NOT found in tessdata!")
    else:
        print("[ERROR] tessdata directory not found at:", tessdata_dir)

######################################################################
# Get console window handle. As well as a helper to bring it forward #
######################################################################
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9

def bring_console_to_front():
    hwnd = kernel32.GetConsoleWindow()
    if hwnd == 0:
        print("No console window found.")
        return False

    # Get thread IDs
    foreground_hwnd = user32.GetForegroundWindow()
    current_thread_id = kernel32.GetCurrentThreadId()
    foreground_thread_id = user32.GetWindowThreadProcessId(foreground_hwnd, 0)

    # Attach input threads so SetForegroundWindow works
    user32.AttachThreadInput(foreground_thread_id, current_thread_id, True)
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    user32.AttachThreadInput(foreground_thread_id, current_thread_id, False)

    return True




####################################################################
# Fixes title case issues like checking for items with apostrophes #
####################################################################
def smart_title_case(text):
    text = str(text)
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
    
def normalize_for_search(s: str) -> str:
    s = s.replace("—", " ").replace("“", " ").replace("”", " ")
    s = re.sub(r"[^\w\s%';]", " ", s)  # keep %, ', ; for precise matching
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


#####################################
# helpers for body armour ordering  # 
#####################################
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

def find_first_body_armor_pos(text, body_armors):
    norm_text = normalize_for_search(text) 
    body_armor_regex = build_body_armor_regex(body_armors)
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

def is_armor_enchant_by_body_armor_order(term_title, text, body_armors, enchant_type_lookup):
    base_part = term_title.split(";", 1)[0].strip()
    norm_key = normalize_for_search(smart_title_case(base_part))
    types = enchant_type_lookup.get(norm_key, [])

    # Force Armor if ONLY armor types found
    if types and all(t == c.ARMOR_ENCHANT_TYPE for t in types):
        if c.DEBUGGING:
            print(f"[TypeCheck] '{term_title}' only in armor types → Armor Enchant")
        return True

    # Force Weapon if ONLY weapon types found
    if types and all(t == c.WEAPON_ENCHANT_TYPE for t in types):
        if c.DEBUGGING:
            print(f"[TypeCheck] '{term_title}' only in weapon types → Weapon Enchant")
        return False

    # If ambiguous (both types), fallback to proximity check
    first_body = find_first_body_armor_pos(text, body_armors)
    first_enchant = find_first_enchant_piece_pos(term_title, text)

    if c.DEBUGGING:
        print(f"[OrderCheck] Ambiguous types for '{term_title}'. body_pos={first_body}, enchant_pos={first_enchant}")

    if first_body is not None and first_enchant is not None:
        return 0 <= (first_enchant - first_body) <= MAX_DISTANCE

    # Default fallback, treat as weapon if unclear
    if c.DEBUGGING:
        print(f"[Fallback] '{term_title}' ambiguous and no body armor nearby, treating as Weapon Enchant")
    
    # print(f"Checking term: '{term_title}'")
    # print(f"Base part: '{base_part}'")
    # print(f"Normalized key: '{norm_key}'")
    # print(f"Types from lookup: {types}")

    return False
    

def now_timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


#####################################################################
# Utility functions for confirming type, used for the csv recording #
#####################################################################
def add_if_trinket(term, type_):
    return c.trinket_data_name if type_ == c.TRINKET_TYPE else ""

def add_if_replacement(term, type_):
    return term if type_ == c.REPLACEMENT_TYPE else ""

def add_if_replica(term, type_):
    return term if type_ == c.REPLICA_TYPE else ""

def add_if_experimental(term, type_):
    return term if type_ == c.EXPERIMENTAL_TYPE else ""

def add_if_weapon_enchant(term, type_):
    return term if type_ == c.WEAPON_ENCHANT_TYPE else ""

def add_if_armor_enchant(term, type_):
    return term if type_ == c.ARMOR_ENCHANT_TYPE else ""

def add_if_scarab(term, type_):
    return term if type_ == c.SCARAB_TYPE else ""

def add_if_currency(term, type_):
    return term if type_ == c.CURRENCY_TYPE else ""

def is_currency_or_scarab(term, type_):
    return type_ == c.CURRENCY_TYPE or type_ == c.SCARAB_TYPE

#########################################################################
# Attempts to get the top right part of the screenshot which contains 	#
# Area Layout, Area Level dynamically for different display types 		#
# 1% of the overall screen 												#
#########################################################################
def get_top_right_layout(screen_width, screen_height):
    aspect_ratio = c.TOP_RIGHT_CUT_WIDTH / c.TOP_RIGHT_CUT_HEIGHT
    total_area = screen_width * screen_height
    target_area = total_area * 0.01  # 1% of screen

    region_height = math.sqrt(target_area / aspect_ratio)
    region_width = region_height * aspect_ratio

    region_width = int(region_width)
    region_height = int(region_height)

    left = screen_width - region_width
    top = 0
    right = screen_width
    bottom = region_height

    return (left, top, right, bottom)
