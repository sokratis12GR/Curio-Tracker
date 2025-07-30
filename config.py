# Enable DEBUGGING
DEBUGGING = False

# Char Info (for logging)
poe_league = "3.26"
poe_user = "sokratis12GR"
default_bp_lvl = "83"
default_bp_area = "Prohibited Library"

layout_keywords = [
    "Bunker", "Records Office", "Mansion", "Smuggler's Den", "Underbelly",
    "Laboratory", "Prohibited Library", "Repository", "Tunnels"
]
TOP_RIGHT_CUT_WIDTH = 366
TOP_RIGHT_CUT_HEIGHT = 210

# Tesseract Executatble Location (README.MD)
tesseract_path = r"D:\Dev\Tesseract-OCR\tesseract.exe"

# Keys / Strings / Locations / Texts

## Logging
logs_dir = "logs"
saves_dir = "saved"
csv_file_path = "saved/matches.csv"

### CSV Header Format -- TODO: Adjust to support the format of the "PoE Curio Case Rates" Project: https://docs.google.com/spreadsheets/d/1dDDMRc3GAE4G0X-lJeLXSHaGtLLNf612nrFiOyCo0Vs/edit?gid=710775455#gid=710775455
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

### Input Value fo "Valid Experimental/Replicas/Scarabs/Currencies/Enchants/Replacements"
file_name = "AllValid.csv"
target_application = "Path of Exile"
not_found_target_txt = "❌ Path of Exile window not found."


## Matches Info
matches_found = "✅ Matches found:"
matches_not_found = "❌ No matches found."


## Capturing / Exiting
info_show_keys_capture = "🖼️ Press F2 to capture All Curios on Screen w/o duplicates."
info_show_keys_snippet = "✂️ Press F4 to snippet a region to capture w/ duplicates."
info_show_keys_layout = "🗺️ Press F5 to set current layout (type, alvl) data."
info_show_keys_exit = "❌ Press F3 to exit the script.\n"

capture_key = "f2"
exit_key = "f3"
snippet_key = "f4"
layout_capture_key = "f5"

capturing_prompt = "📸 Capturing screen..."
layout_prompt = "📸 Capturing layout..."
exiting_prompt = "👋 Exiting."


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
rare_l_hue = 20
rare_l_sat = 80
rare_l_val = 150
### Upper
rare_u_hue = 40
rare_u_sat = 255
rare_u_val = 255

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
enchant_l_hue = 95
enchant_l_sat = 15
enchant_l_val = 70
### Upper
enchant_u_hue = 130
enchant_u_sat = 90
enchant_u_val = 240
