import os
import configparser
from config import DEFAULT_SETTINGS

def get_data_path(filename: str) -> str:
    appdata = os.getenv('APPDATA') or os.path.expanduser('~')
    base = os.path.join(appdata, "HeistCurioTracker")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, filename)

SETTINGS_PATH = get_data_path("user_settings.ini")
LOCK_FILE = get_data_path("last_run.lock")
OUTPUT_CURRENCY_CSV = get_data_path("heist_item_currency_values.csv")
OUTPUT_TIERS_CSV = get_data_path("heist_item_tiers_data.csv")

settings = configparser.ConfigParser()
if os.path.exists(SETTINGS_PATH):
    settings.read(SETTINGS_PATH)

# Ensure default sections exist
for section in ("Hotkeys", "User", "Application"):
    if section not in settings:
        settings[section] = {}


def write_settings():
    try:
        with open(SETTINGS_PATH, 'w') as f:
            settings.write(f)
    except Exception as e:
        print("[ERROR] Failed to write settings:", e)

def set_setting(section: str, key: str, value):
    if section not in settings:
        settings[section] = {}

    # Convert value to string
    if isinstance(value, bool):
        value_str = "True" if value else "False"
    elif isinstance(value, (int, float)):
        value_str = str(value)
    else:
        value_str = str(value)

    settings[section][key] = value_str
    write_settings()


def get_setting(section: str, key: str, default=None):
    if section not in settings or key not in settings[section]:
        return default

    val_str = settings[section][key]

    # Try to detect type
    if val_str.lower() in ("true", "false"):
        return val_str.lower() == "true"
    try:
        if "." in val_str:
            return float(val_str)
        else:
            return int(val_str)
    except ValueError:
        return val_str  # fallback to string


def initialize_settings():
    # Ensure defaults exist
    for section, keys in DEFAULT_SETTINGS.items():
        for key, value in keys.items():
            if get_setting(section, key) is None:
                set_setting(section, key, value)
    write_settings()  # persist any new defaults
