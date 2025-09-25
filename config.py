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
        'poe_user': 'sokratis12GR',
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


def initialize_settings():
    global capture_key, exit_key, layout_capture_key, snippet_key, enable_debugging_key
    global pytesseract_path, time_last_dupe_check_seconds
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
    time_last_dupe_check_seconds = int(get_setting('DEFAULT', 'time_last_dupe_check_seconds', '60'))
    info_show_keys_capture = "Press {} to capture all curios on screen no duplicates.".format(str(capture_key).upper())
    info_show_keys_snippet = "Press {} to snippet a region to capture allows duplicates.".format(
        str(snippet_key).upper())
    info_show_keys_layout = "Press {} to set current layout.".format(str(layout_capture_key).upper())
    info_show_keys_exit = "Press {} to exit the script.".format(str(exit_key).upper())


settings = DEFAULT_SETTINGS

# Enable DEBUGGING
DEBUGGING = False
OCR_DEBUGGING = False
CSV_DEBUGGING = False
ENABLE_LOGGING = True

LEAGUE = "Mercenaries"
poe_league = "3.26"
poe_user = "sokratis12GR"

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
time_options = [
    "All", "Last hour", "Last 2 hours", "Last 12 hours", "Today", "Last 24 hours",
    "Last week", "Last 2 weeks", "Last month", "Last year", "Custom..."
]
TOP_RIGHT_CUT_WIDTH = 170
TOP_RIGHT_CUT_HEIGHT = 100

IMAGE_COL_WIDTH = 200
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

csv_type_header = "Type"
csv_value_header = "Value"

### Input Value fo "Trinket/Replacement/Replica/Experimental/Weapon Enchants/Armor Enchants/Scarab/Currency"
trinket_data_name = "Thief's Trinket"
file_all_valid_heist_terms = "all_valid_heist_terms.csv"
file_body_armors = "body_armors.txt"
file_experimental_items = "experimental_items.csv"
target_application = "Path of Exile"
not_found_target_txt = "❌ Path of Exile window not found."
not_found_target_snippet_txt = "❌ Path of Exile window not found. Exiting snippet."
snippet_txt_too_small = "⚠️ Selected region is too small or invalid."
snippet_txt_failed = "⚠️ Screenshot capture failed."
listening_keybinds_txt = "Listening for keybinds... Press your exit key to stop."

## Matches Info
matches_found = "✅ Matches found: "
stack_size_found = " - Stack Size: {}"
matches_not_found = "❌ No matches found."

capturing_prompt = "Capturing screen..."
layout_prompt = "Capturing layout..."
exiting_prompt = "👋 Exiting."

# Time Duplicate values checker:
time_column_index = 16  # 17th column of the .csv file contains the time var

# HSV thresholds (Hue, Saturation, Value) split to lower and upper values

## Replica / Unique: #AF6025
### Lower
replica_l_hue = 5
replica_l_sat = 100
replica_l_val = 80  # 100
### Upper
replica_u_hue = 25
replica_u_sat = 255
replica_u_val = 255

## Rare / Experimental: #D9C850
### Lower
rare_l_hue = 20  # 20
rare_l_sat = 50  # 80
rare_l_val = 160  # 150
### Upper
rare_u_hue = 40  # 40
rare_u_sat = 255  # 255
rare_u_val = 255  # 255

## Currency Item: #AA9E82
### Lower
currency_l_hue = 15
currency_l_sat = 0  # 20
currency_l_val = 90
### Upper
currency_u_hue = 45
currency_u_sat = 100
currency_u_val = 220

## Scarabs (new gray): #B7B8B8
### Lower
scarab_l_hue = 0
scarab_l_sat = 0
scarab_l_val = 150
### Upper
scarab_u_hue = 180
scarab_u_sat = 10
scarab_u_val = 255

## Enchants (blue-gray): #5C7E9D
### Lower
enchant_l_hue = 95  # 95
enchant_l_sat = 15  # 15
enchant_l_val = 70  # 70
### Upper
enchant_u_hue = 130  # 130
enchant_u_sat = 90  # 90
enchant_u_val = 255  # 240
