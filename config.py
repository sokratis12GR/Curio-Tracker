import os
import sys

######################################################################
# LOADS THE SETTINGS VALUES SET IN USER_SETTINGS.INI                 #
######################################################################
# -------------------- Paths --------------------
APP_NAME = "HeistCurioTracker"
if getattr(sys, 'frozen', False):
    # Running as bundled exe
    base_path = os.path.join(os.getenv('APPDATA'), APP_NAME)
else:
    # Running normally
    base_path = os.path.join(os.path.expanduser("~"), f".{APP_NAME}")

os.makedirs(base_path, exist_ok=True)

SETTINGS_PATH = os.path.join(base_path, "user_settings.ini")

# -------------------- Default Settings --------------------
DEFAULT_SETTINGS = {
    'User': {
        'poe_league': '3.26',
        'poe_user': 'sokratis12GR#6608',
    },
    'Hotkeys': {
        'capture_key': 'f2',
        'exit_key': 'f3',
        'layout_capture_key': 'f5',
        'snippet_key': 'f4',
        'debug_key': 'alt+d'
    },
    'DEFAULT': {
        'pytesseract_path': r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    },
    'Application': {
        'time_last_dupe_check_seconds': '60'
    }
}

capture_key = None
exit_key = None
layout_capture_key = None
snippet_key = None
enable_debugging_key = None
pytesseract_path = None
time_last_dupe_check_seconds = None
info_show_keys_capture = None
info_show_keys_snippet = None
info_show_keys_layout = None
info_show_keys_exit = None

LEAGUE = "Mercenaries"

def initialize_settings():
    global capture_key, exit_key, layout_capture_key, snippet_key, enable_debugging_key
    global pytesseract_path, time_last_dupe_check_seconds, LEAGUE
    from settings import get_setting, set_setting, write_settings

    # Ensure defaults exist
    for section, keys in DEFAULT_SETTINGS.items():
        for key, value in keys.items():
            if get_setting(section, key) is None:
                set_setting(section, key, str(value))
    write_settings()

    # Assign module-level variables
    capture_key = get_setting('Hotkeys', 'capture_key')
    exit_key = get_setting('Hotkeys', 'exit_key')
    layout_capture_key = get_setting('Hotkeys', 'layout_capture_key')
    snippet_key = get_setting('Hotkeys', 'snippet_key')
    enable_debugging_key = get_setting('Hotkeys', 'debug_key')
    pytesseract_path = get_setting('DEFAULT', 'pytesseract_path')
    time_last_dupe_check_seconds = int(get_setting('Application', 'time_last_dupe_check_seconds', 60))
    LEAGUE = get_setting('Application', 'data_league')


settings = DEFAULT_SETTINGS

# Enable DEBUGGING
DEBUGGING = False
OCR_DEBUGGING = False
CSV_DEBUGGING = False
ENABLE_LOGGING = True

# Update these every league.
FIXED_LADDER_IDENTIFIER = "Mercenaries_of_Trarthus"
LEAGUES_TO_FETCH = [
    LEAGUE,
    f"Hardcore {LEAGUE}",
    "Standard"
]
IS_SSF = False
ENABLE_POELADDER = False

POELADDER_LADDERS = {
    "SSF Standard": "SSF_Standard",
    "SSF Mercenaries": "SSF_Mercenaries_of_Trarthus",
    "Mercenaries": "Mercenaries_of_Trarthus",
    "Standard": "Standard",
    "SSF Hardcore Mercenaries": "SSF_Mercenaries_of_Trarthus_HC",
    "SSF Hardcore": "SSF_Hardcore",
}


poe_league = "3.26"
poe_user = "sokratis12GR#6608"

# Default values of blueprint layouts
default_bp_lvl = "83"
default_bp_area = "Prohibited Library"

layout_keywords = [
    "Bunker", "Records Office", "Mansion", "Smuggler's Den", "Underbelly",
    "Laboratory", "Prohibited Library", "Repository", "Tunnels"
]
league_versions = [
    "3.26", "3.25", "3.24", "3.23", "3.22", "3.21",
    "3.20", "3.19", "3.18", "3.17", "3.16", "3.15",
    "3.14", "3.13", "3.12"
]
theme_modes = [
    "LIGHT", "DARK"
]
time_options = [
    "All", "Last hour", "Last 2 hours", "Last 12 hours", "Today", "Last 24 hours",
    "Last week", "Last 2 weeks", "Last month", "Last year", "Custom..."
]

TREE_COLUMNS = [
    {"id": "record", "label": "Record", "width": 100, "sort_reverse": True, "visible": True},
    {"id": "item", "label": "Item / Enchant", "width": 420, "sort_reverse": False, "visible": True},
    {"id": "value", "label": "Estimated Value", "width": 140, "sort_reverse": False, "visible": True},
    {"id": "numeric_value", "label": "Numeric Value", "width": 100, "sort_reverse": False, "visible": False},
    {"id": "stack_size", "label": "Stack Size", "width": 100, "sort_reverse": False, "visible": True},
    {"id": "tier", "label": "Tier", "width": 100, "sort_reverse": False, "visible": True},
    {"id": "type", "label": "Type", "width": 120, "sort_reverse": True, "visible": True},
    {"id": "owned", "label": "Owned", "width": 140, "sort_reverse": False, "visible": True},
    {"id": "picked", "label": "Picked", "width": 140, "sort_reverse": False, "visible": True},
    {"id": "area_level", "label": "Area Level", "width": 100, "sort_reverse": False, "visible": True},
    {"id": "layout", "label": "BP Layout", "width": 200, "sort_reverse": False, "visible": True},
    {"id": "player", "label": "Found by", "width": 120, "sort_reverse": False, "visible": True},
    {"id": "league", "label": "League", "width": 100, "sort_reverse": False, "visible": True},
    {"id": "time", "label": "Time", "width": 150, "sort_reverse": True, "visible": True},
]

COLOR = {
    "enchant": "#b4b4ff",
    "currency": "#aa9e82",
    "scarab": "#aa9e82",
    "rare": "#ffff77",
    "experimental": "#ffff77",
    "replica": "#af6025",
    "replacement": "#af6025",
}

DEFAULT_THEME_MODE = "DARK"
MIN_DUPE_DURATION = 30
MAX_DUPE_DURATION = 240
TOP_RIGHT_CUT_WIDTH = 170
TOP_RIGHT_CUT_HEIGHT = 100

IMAGE_COL_WIDTH = 265
ROW_HEIGHT = 40

# Type constants
TRINKET_TYPE = "Trinket"
REPLACEMENT_TYPE = "Replacement"
REPLICA_TYPE = "Replica"
EXPERIMENTAL_TYPE = "Experimental"
WEAPON_ENCHANT_TYPE = "Weapon Enchants"
ARMOR_ENCHANT_TYPE = "Armor Enchants"
SCARAB_TYPE = "Scarab"
CURRENCY_TYPE = "Currency"

# Keys / Strings / Locations / Texts

## Logging
logs_dir = "logs"
saves_dir = "saved"
csv_file_path = "saved/matches.csv"

## File paths
logs_file_name = "logs/tracker.log"
settings_file_name = "user_settings.ini"
lock_file_name = "fetch/last_run.lock"
currency_fetch_file_name = "fetch/heist_item_currency_values.csv"
tiers_fetch_file_name = "fetch/heist_item_tiers_data.csv"
collection_fetch_file_name = "fetch/heist_item_collection_data.csv"

### CSV Header Format -- Adjusted to support the format of the "PoE Curio Case Rates" Project: https://docs.google.com/spreadsheets/d/1dDDMRc3GAE4G0X-lJeLXSHaGtLLNf612nrFiOyCo0Vs/edit?gid=710775455#gid=710775455
csv_record_header = "Record #"

csv_league_header = "League"
csv_loggedby_header = "Logged By"
csv_blueprint_header = "Blueprint Type"
csv_area_level_header = "Area Level"

csv_trinket_header = "Trinket"
csv_replacement_header = "Replacement"
csv_replica_header = "Replica"
csv_experimented_header = "Experimented Base Type"
csv_weapon_enchant_header = "Weapon Enchantment"
csv_armor_enchant_header = "Armor Enchantment"
csv_scarab_header = "Scarab"
csv_currency_header = "Currency"
csv_stack_size_header = "Stack Size"
csv_variant_header = "Variant"
csv_flag_header = "Flag?"
csv_time_header = "Time"
csv_tier_header = "Tier"
csv_picked_header = "Picked"
csv_owned_header = "Owned"

csv_type_header = "Type"
csv_value_header = "Value"

### Input Value fo "Trinket/Replacement/Replica/Experimental/Weapon Enchants/Armor Enchants/Scarab/Currency"
trinket_data_name = "Thief's Trinket"
file_all_valid_heist_terms = "all_valid_heist_terms.csv"
file_body_armors = "body_armors.txt"
file_experimental_items = "experimental_items.csv"
target_application = "Path of Exile"
not_found_target_txt = "Path of Exile window not found."
not_found_target_snippet_txt = "Path of Exile window not found. Exiting snippet."
snippet_txt_too_small = "Selected region is too small or invalid."
snippet_txt_failed = "Screenshot capture failed."
listening_keybinds_txt = "Listening for keybinds... Press your exit key to stop."

## Matches Info
matches_found = "Matches found: "
stack_size_found = " - Stack Size: {}"
matches_not_found = "No matches found."

capturing_prompt = "Capturing screen..."
layout_prompt = "Capturing layout..."
exiting_prompt = "👋 Exiting."

# Time Duplicate values checker:
time_column_index = 16  # 17th column of the .csv file contains the time var

# HSV thresholds (Hue, Saturation, Value) split to lower and upper values

## Replica / Unique: #AF6025
replica_l_hsv = [5, 100, 80]
replica_u_hsv = [25, 255, 255]

## Rare / Experimental: #D9C850
rare_l_hsv = [20, 50, 160]
rare_u_hsv = [40, 255, 255]

## Currency Item: #AA9E82
currency_l_hsv = [15, 0, 90]
currency_u_hsv = [45, 100, 220]

## Scarabs (new gray): #B7B8B8
scarab_l_hsv = [0, 0, 150]
scarab_u_hsv = [180, 10, 255]

## Enchants (blue-gray): #5C7E9D
enchant_l_hsv = [95, 15, 70]
enchant_u_hsv = [130, 90, 255]
