import os
import threading
import configparser
from pynput import keyboard
import traceback
from config import DEFAULT_SETTINGS
from ocr_utils import get_setting, set_setting, write_settings

# ---------------- Keybinds ----------------
def hotkey_default(name):
    ini_name = f"{name}_key" if name != "debug" else "debug_key"
    return get_setting('Hotkeys', ini_name, DEFAULT_SETTINGS['Hotkeys'][ini_name])

keybinds = [
    ("Capture Screen", hotkey_default('capture'), 'capture'),
    ("Capture Layout", hotkey_default('layout_capture'), 'layout_capture'),
    ("Capture Snippet", hotkey_default('snippet'), 'snippet'),
    ("Exit", hotkey_default('exit'), 'exit'),
    ("Debugging", hotkey_default('debug'), 'debug'),
]

# ---------------- Runtime storage ----------------
handlers = {}
hotkeys = {}
_recording_listener = None
_global_listener = None
_recording_index = None
_current_keys = []
_lock = threading.Lock()

# ---------------- Persistence ----------------
def update_keybind(name, combo_str):
    try:
        parsed = parse_hotkey(combo_str)
        hotkeys[name] = parsed
        ini_name = f"{name}_key" if name != "debug" else "debug_key"
        set_setting('Hotkeys', ini_name, combo_str)
        write_settings()
        print(f"[INFO] Assigned '{name}' → {combo_str}")
        return True
    except Exception:
        print(f"[ERROR] Failed to assign '{name}':")
        print(traceback.format_exc())
        return False

def get_display_hotkey(name):
    ini_name = f"{name}_key" if name != "debug" else "debug_key"
    default = next((d for (_, d, n) in keybinds if n == name), "")
    return get_setting('Hotkeys', ini_name, default)

# ---------------- Hotkey parsing ----------------
def normalize_key(evt_key):
    if isinstance(evt_key, keyboard.Key):
        return evt_key
    elif hasattr(evt_key, 'char') and evt_key.char is not None:
        return evt_key.char.lower()
    return None

def parse_hotkey(hotkey_str):
    # Ensure the input is always a string
    hotkey_str = str(hotkey_str)

    parts = [p.strip().lower() for p in hotkey_str.split('+') if p.strip()]
    keys = set()
    for p in parts:
        try:
            if p in ('ctrl', 'ctrl_l', 'ctrl_r'):
                keys.add(keyboard.Key.ctrl)
            elif p in ('shift', 'shift_l', 'shift_r'):
                keys.add(keyboard.Key.shift)
            elif p in ('alt', 'alt_l', 'alt_r'):
                keys.add(keyboard.Key.alt)
            elif p.startswith('f') and p[1:].isdigit():
                keys.add(getattr(keyboard.Key, p))
            elif len(p) == 1 and p.isprintable(): 
                keys.add(p)
            else:
                keys.add(getattr(keyboard.Key, p))
        except Exception:
            print(f"[WARN] Unknown key part: {p}")
    return frozenset(keys)

def format_key(k):
    if isinstance(k, keyboard.Key):
        name = str(k).split('.')[-1].lower()
        return {'alt_l':'alt','alt_r':'alt','ctrl_l':'ctrl','ctrl_r':'ctrl',
                'shift_l':'shift','shift_r':'shift'}.get(name, name)
    return str(k).lower()

# ---------------- Initialize runtime hotkeys ----------------
def init_from_settings():
    for (_, default, name) in keybinds:
        try:
            combo_str = get_display_hotkey(name)
            hotkeys[name] = parse_hotkey(combo_str)
        except Exception:
            print(f"[ERROR] Failed to load hotkey '{name}':")
            print(traceback.format_exc())
    print("[INFO] Keybinds loaded from settings.")

# ---------------- Recording listener ----------------
def start_recording_popup(index, button_list, root, update_info_labels):
    global _recording_listener, _recording_index, _current_keys, _global_listener
    with _lock:
        if _recording_index is not None:
            print("[WARN] Already recording a keybind.")
            return
        if _global_listener:
            _global_listener.stop()
            _global_listener = None
        _recording_index = index
        _current_keys = []

    def on_press(key):
        try:
            k = normalize_key(key)
            if k and k not in _current_keys and len(_current_keys) < 3:
                _current_keys.append(k)
            if key == keyboard.Key.esc:
                cancel_recording_popup(button_list)
                return False
        except Exception:
            print(traceback.format_exc())

    def on_release(key):
        global _recording_index, _current_keys
        try:
            if len(_current_keys) >= 1:
                combo_str = '+'.join(format_key(k) for k in _current_keys)
                btn = button_list[_recording_index]
                btn.after(0, lambda b=btn, t=combo_str: b.config(text=t))
                update_keybind(keybinds[_recording_index][2], combo_str)
                update_info_labels()
            _current_keys.clear()
            _recording_index = None
            start_global_listener()
        except Exception:
            print(traceback.format_exc())
        return False

    _recording_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    _recording_listener.start()
    print("[INFO] Recording keys... Press combo, then release. ESC to cancel.")

def cancel_recording_popup(button_list=None):
    global _recording_listener, _recording_index, _current_keys
    try:
        if _recording_listener:
            _recording_listener.stop()
            _recording_listener = None
        if button_list is not None and _recording_index is not None:
            name = keybinds[_recording_index][2]
            btn = button_list[_recording_index]
            combo = get_display_hotkey(name)
            btn.after(0, lambda b=btn, t=combo: b.config(text=t))
        print("[INFO] Recording cancelled.")
    except Exception:
        print(traceback.format_exc())
    finally:
        _recording_index = None
        _current_keys = []

# ---------------- Global listener ----------------
def start_global_listener():
    global _global_listener, _current_keys
    with _lock:
        if _global_listener:
            try:
                _global_listener.stop()
            except Exception:
                print(traceback.format_exc())
            _global_listener = None
        _current_keys = []

        def on_press(key):
            try:
                k = normalize_key(key)
                if k and k not in _current_keys and len(_current_keys) < 3:
                    _current_keys.append(k)
            except Exception:
                print(traceback.format_exc())

        def on_release(key):
            try:
                pressed = frozenset(_current_keys)
                for name, combo in hotkeys.items():
                    if combo == pressed:
                        handler = handlers.get(name)
                        if handler:
                            try:
                                handler()
                            except Exception:
                                print(f"[ERROR] handler '{name}' threw:")
                                print(traceback.format_exc())
                        break
                _current_keys.clear()
            except Exception:
                print(traceback.format_exc())

        _global_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        _global_listener.start()
        print("[INFO] Global listener started.")

def stop_global_listener():
    global _global_listener, _current_keys
    with _lock:
        try:
            if _global_listener:
                _global_listener.stop()
                _global_listener = None
        except Exception:
            print(traceback.format_exc())
        _current_keys = []

# ---------------- Initialize ----------------

init_from_settings()
