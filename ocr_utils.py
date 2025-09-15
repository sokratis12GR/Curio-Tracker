import os
import re
import sys
import math
import csv
import shutil
import ctypes
from datetime import datetime
from difflib import get_close_matches
from types import SimpleNamespace
import pytesseract
import config as c
import configparser

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
    if c.DEBUGGING:
        print("[DEBUG] Tesseract binary set to:", tesseract_bin)

    tesseract_dir = os.path.dirname(tesseract_bin)
    tessdata_dir = os.path.join(tesseract_dir, "tessdata")

    if os.path.isdir(tessdata_dir):
        os.environ["TESSDATA_PREFIX"] = tessdata_dir
        if c.DEBUGGING:
            print("[DEBUG] TESSDATA_PREFIX set to:", tessdata_dir)
        eng_path = os.path.join(tessdata_dir, "eng.traineddata")
        if os.path.isfile(eng_path):
            if c.DEBUGGING:
                print("[DEBUG] eng.traineddata found:", eng_path)
        else:
            if c.DEBUGGING:
                print("[ERROR] eng.traineddata NOT found in tessdata!")
    else:
        print("[ERROR] tessdata directory not found at:", tessdata_dir)


######################################################################
# Settings file path under %APPDATA%/HeistCurioTracker/              #
######################################################################
def get_settings_path():
    appdata = os.getenv('APPDATA') or os.path.expanduser('~')
    base = os.path.join(appdata, "HeistCurioTracker")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "user_settings.ini")

settings_path = get_settings_path()
settings = configparser.ConfigParser()
if os.path.exists(settings_path):
    settings.read(settings_path)

# Ensure default sections exist
if 'Hotkeys' not in settings:
    settings['Hotkeys'] = {}
if 'User' not in settings:
    settings['User'] = {}

# ---------------- Persistence ----------------
def write_settings():
    try:
        with open(settings_path, 'w') as f:
            settings.write(f)
    except Exception:
        print("[ERROR] Failed to write settings:")
        print(traceback.format_exc())

def set_setting(section: str, key: str, value: str):
    if section not in settings:
        settings[section] = {}
    settings[section][key] = value
    write_settings()

def get_setting(section: str, key: str, default=None):
    if section not in settings:
        return default
    return settings[section].get(key, default)

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

def is_currency_or_scarab(type_):
    return type_ == c.CURRENCY_TYPE or type_ == c.SCARAB_TYPE

def is_unique(type_):
    return type_ == c.REPLACEMENT_TYPE or type_ == c.REPLICA_TYPE

def is_rare(type_):
    return type_ == c.TRINKET_TYPE or type_ == c.EXPERIMENTAL_TYPE or type_ == c.ARMOR_ENCHANT_TYPE or type_ == c.WEAPON_ENCHANT_TYPE

def is_enchant(type_):
    return type_ == c.ARMOR_ENCHANT_TYPE or type_ == c.WEAPON_ENCHANT_TYPE


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

#########################################################################
#                                                                       #
#        Builds the Item for the Image Rendering via CSV / OCR          #
#                                                                       #
#########################################################################
def parse_timestamp(ts_str, fallback_now=True):
    if not ts_str:
        return datetime.now() if fallback_now else None
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S")
    except Exception:
        return datetime.now() if fallback_now else None

def load_csv(file_path, row_parser=None, skip_header=True):
    results = []
    with open(file_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        if skip_header:
            next(reader, None)
        for row in reader:
            results.append(row_parser(row) if row_parser else row)
    return results

def build_parsed_item(
    term_title,
    item_type,
    duplicate,
    timestamp,
    experimental_items,
    rarity=None,
    league="",
    logged_by="",
    blueprint_type="",
    area_level="",
    stack_size=""
):
    ts = parse_timestamp(timestamp)

    corrected_name = (
        "Replica " + term_title if item_type == c.REPLICA_TYPE else
        "Enchanted Item" if item_type in (c.WEAPON_ENCHANT_TYPE, c.ARMOR_ENCHANT_TYPE) else
        term_title
    )
    corrected_type = (
        "Replica" if item_type == c.REPLICA_TYPE else
        "Enchant" if item_type in (c.WEAPON_ENCHANT_TYPE, c.ARMOR_ENCHANT_TYPE) else
        item_type
    )

    enchants = []
    if ";" in term_title and item_type in (c.WEAPON_ENCHANT_TYPE, c.ARMOR_ENCHANT_TYPE):
        part1, part2 = [smart_title_case(p.strip()) for p in term_title.split(";", 1)]
        enchants.extend([part1, part2])
    elif item_type in (c.WEAPON_ENCHANT_TYPE, c.ARMOR_ENCHANT_TYPE):
        enchants.append(term_title)

    rarity = (
        rarity or
        ("Unique" if is_unique(item_type) else
         "rare" if is_rare(item_type) else
         "currency" if is_currency_or_scarab(item_type) else
         "normal")
    )

    stack_size_str = (
        stack_size if stack_size and str(stack_size).isdigit() and
        int(stack_size) > 0 and is_currency_or_scarab(item_type)
        else ""
    )

    item_dict = SimpleNamespace(
        itemClass="",
        itemRarity=rarity,
        itemName=SimpleNamespace(lines=[corrected_name]),
        flavorText={"lines": []},
        itemLevel=0,
        affixes=[],
        runes=[],
        implicits=[],
        enchants=enchants,
        quality=0,
        type=corrected_type,
        corrupted=False,
        stack_size=stack_size_str,
        duplicate=duplicate,
        time=ts,
        league=league,
        logged_by=logged_by,
        blueprint_type=blueprint_type,
        area_level=area_level,
    )

    if item_type == c.EXPERIMENTAL_TYPE:
        implicits_lines = experimental_items.get(term_title, [])
        if implicits_lines:
            item_dict.implicits.extend(implicits_lines)

    return item_dict
