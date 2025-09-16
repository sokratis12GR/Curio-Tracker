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

settings = configparser.ConfigParser()
if os.path.exists(SETTINGS_PATH):
    settings.read(SETTINGS_PATH)

# Ensure default sections exist
if 'Hotkeys' not in settings:
    settings['Hotkeys'] = {}
if 'User' not in settings:
    settings['User'] = {}

def write_settings():
    try:
        with open(SETTINGS_PATH, 'w') as f:
            settings.write(f)
    except Exception as e:
        print("[ERROR] Failed to write settings:", e)

def set_setting(section: str, key: str, value: str):
    if section not in settings:
        settings[section] = {}
    settings[section][key] = value
    write_settings()

def get_setting(section: str, key: str, default=None):
    if section not in settings:
        return default
    return settings[section].get(key, default)


def initialize_settings():
    # Ensure defaults exist
    for section, keys in DEFAULT_SETTINGS.items():
        for key, value in keys.items():
            if get_setting(section, key) is None:
                set_setting(section, key, str(value))
    write_settings()  # persist any new defaults