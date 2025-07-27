# Enable DEBUGGING
DEBUGGING = False

# HSV thresholds (Hue, Saturation, Value) split to lower and upper values

## Replica / Unique: #AF6025
### Lower
replica_l_hue = 5
replica_l_sat = 100
replica_l_val = 255
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
currency_l_sat = 20
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


# Tesseract Executatble Location (README.MD)
tesseract_path = r"D:\Dev\Tesseract-OCR\tesseract.exe"

# Keys / Strings / Locations / Texts

## Logging
logs_dir = "logs"
saves_dir = "saved"
csv_file_path = "saved/matches.csv"
csv_time_header = "Time"
csv_type_header = "Type"
csv_value_header = "Value"

file_name = "AllValid.csv"
target_application = "Path of Exile"
not_found_target_txt = "❌ Path of Exile window not found."


## Matches Info
matches_found = "✅ Matches found:"
matches_not_found = "❌ No matches found."


## Capturing / Exiting
info_show_keys_1 = "🖼️ Press F2 to capture Path of Exile window."
info_show_keys_2 = "❌ Press F3 to exit the script.\n"
capture_key = "f2"
exit_key = "f3"
capturing_prompt = "📸 Capturing screen..."
exiting_prompt = "👋 Exiting."
