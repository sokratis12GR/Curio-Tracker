import configparser
import os
import threading

from config import DEFAULT_SETTINGS
from load_utils import get_data_path
from thread_utils import atomic_write

SETTINGS_PATH = get_data_path("user_settings.ini")

settings = configparser.ConfigParser()
if os.path.exists(SETTINGS_PATH):
    settings.read(SETTINGS_PATH)

# Ensure default sections exist
for section in ("Hotkeys", "User", "Application"):
    if section not in settings:
        settings[section] = {}


# Settings are written from the UI, hotkey and fetch threads.
_settings_lock = threading.RLock()


def write_settings():
    try:
        with _settings_lock:
            # Atomic: a crash mid-write can't leave a truncated ini.
            atomic_write(SETTINGS_PATH, settings.write, encoding=None)
    except Exception as e:
        print("[ERROR] Failed to write settings:", e)


def set_setting(section: str, key: str, value):
    # Convert value to string
    if isinstance(value, bool):
        value_str = "True" if value else "False"
    else:
        value_str = str(value)

    with _settings_lock:
        if section not in settings:
            settings[section] = {}
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
    # Fill missing defaults in memory, then write the file once.
    with _settings_lock:
        for section, keys in DEFAULT_SETTINGS.items():
            for key, value in keys.items():
                if get_setting(section, key) is None:
                    if section not in settings:
                        settings[section] = {}
                    settings[section][key] = ("True" if value else "False") if isinstance(value, bool) else str(value)
        write_settings()  # persist any new defaults
