import os
import sys
import configparser

######################################################################
# LOADS THE SETTINGS VALUES SET IN USER_SETTINGS.INI                 #
######################################################################
def load_settings():
    if getattr(sys, 'frozen', False):
        # Running as a bundled exe
        base_path = os.path.dirname(sys.executable)
    else:
        # Running normally
        base_path = os.path.abspath(".")

    settings_path = os.path.join(base_path, "user_settings.ini")

    if not os.path.exists(settings_path):
        raise FileNotFoundError(f"Settings file not found at {settings_path}")

    settings = configparser.ConfigParser()
    settings.read(settings_path)
    return settings

settings = load_settings()

poe_league = settings['DEFAULT'].get('poe_league')
poe_user = settings['DEFAULT'].get('poe_user')
capture_key = settings['DEFAULT'].get('capture_key')
exit_key = settings['DEFAULT'].get('exit_key')
layout_capture_key = settings['DEFAULT'].get('layout_capture_key')
snippet_key = settings['DEFAULT'].get('snippet_key')
enable_debugging_key = settings['DEFAULT'].get('enable_debugging_key')

# Enable DEBUGGING
DEBUGGING = False
CSV_DEBUGGING = False

# Defaykt values of blueprint layouts
default_bp_lvl = "83"
default_bp_area = "Prohibited Library"

layout_keywords = [
    "Bunker", "Records Office", "Mansion", "Smuggler's Den", "Underbelly",
    "Laboratory", "Prohibited Library", "Repository", "Tunnels"
]
TOP_RIGHT_CUT_WIDTH = 170
TOP_RIGHT_CUT_HEIGHT = 100

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

### CSV Header Format -- Adjusted to support the format of the "PoE Curio Case Rates" Project: https://docs.google.com/spreadsheets/d/1dDDMRc3GAE4G0X-lJeLXSHaGtLLNf612nrFiOyCo0Vs/edit?gid=710775455#gid=710775455
csv_league_header = "League"
csv_loggedby_header = "Logged By"
csv_blueprint_header = "Blueprint Type"
csv_area_level_header = "Area Level"

csv_trinket_header = "Trinket"
csv_replacement_header = "Replacement"
csv_replica_header = "Replica"
csv_experimented_header = "Experimented Base Type"
csv_weapon_enchant_header = "Weapon Enchantment"
csv_armor_enchant_trinket_header = "Armor Enchantment"
csv_scarab_trinket_header = "Scarab"
csv_currency_trinket_header = "Currency"
csv_stack_size_trinket_header = "Stack Size"
csv_variant_trinket_header = "Variant"
csv_flag_trinket_header = "Flag?"

csv_time_header = "Time"
csv_type_header = "Type"
csv_value_header = "Value"

### Input Value fo "Trinket/Replacement/Replica/Experimental/Weapon Enchants/Armor Enchants/Scarab/Currency"
file_name = "all_valid_heist_terms.csv"
trinket_data_name = "Thief's Trinket"
file_body_armors = "body_armors.txt"
target_application = "Path of Exile"
not_found_target_txt = "❌ Path of Exile window not found."
not_found_target_snippet_txt = "❌ Path of Exile window not found. Exiting snippet."
snippet_txt_too_small = "⚠️ Selected region is too small or invalid."
snippet_txt_failed = "⚠️ Screenshot capture failed."

## Matches Info
matches_found = "\n✅ Matches found: "
stack_size_found = " - Stack Size: {}"
matches_not_found = "❌ No matches found."


## Capturing / Exiting


info_show_keys_capture = "🖼️ Press {} to capture All Curios on Screen w/o duplicates.".format(capture_key.upper())
info_show_keys_snippet = "✂️ Press {} to snippet a region to capture w/ duplicates.".format(snippet_key.upper())
info_show_keys_layout = "🗺️ Press {} to set current layout (type, alvl) data.".format(layout_capture_key.upper())
info_show_keys_exit = "❌ Press {} to exit the script.\n".format(exit_key.upper())


capturing_prompt = "\n📸 Capturing screen..."
layout_prompt = "\n📸 Capturing layout..."
exiting_prompt = "\n👋 Exiting."

# Time Duplicate values checker:
time_column_index = 15 # 16th column of the .csv file contains the time var
time_last_dupe_check_seconds = 60

# HSV thresholds (Hue, Saturation, Value) split to lower and upper values

## Replica / Unique: #AF6025
### Lower
replica_l_hue = 5
replica_l_sat = 100
replica_l_val = 80 #100
### Upper
replica_u_hue = 25
replica_u_sat = 255
replica_u_val = 255

## Rare / Experimental: #D9C850
### Lower
rare_l_hue = 20 # 20
rare_l_sat = 50 # 80
rare_l_val = 160 # 150
### Upper
rare_u_hue = 40 # 40
rare_u_sat = 255 #255
rare_u_val = 255 #255

## Currency Item: #AA9E82
### Lower
currency_l_hue = 15
currency_l_sat = 0 # 20
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
enchant_l_hue = 95 # 95
enchant_l_sat = 15 # 15
enchant_l_val = 70 # 70
### Upper
enchant_u_hue = 130 #130
enchant_u_sat = 90 #90
enchant_u_val = 255 #240
