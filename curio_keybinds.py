import threading
import time
import traceback

import inputs
from pynput import keyboard

from config import DEFAULT_SETTINGS, DEBUGGING
from settings import get_setting, set_setting, write_settings

# ---------------- Controller map ----------------
CONTROLLER_MAP = {
    "BTN_SOUTH": "pad_a",
    "BTN_EAST": "pad_b",
    "BTN_NORTH": "pad_y",
    "BTN_WEST": "pad_x",
    "BTN_TL": "pad_lb",
    "BTN_TR": "pad_rb",
    "BTN_SELECT": "pad_back",
    "BTN_START": "pad_start",
    "BTN_THUMBL": "pad_ls",
    "BTN_THUMBR": "pad_rs",
}


# ---------------- Keybinds ----------------
def hotkey_default(name) -> str:
    ini_name = f"{name}_key" if name != "debug" else "debug_key"
    return get_setting('Hotkeys', ini_name, DEFAULT_SETTINGS['Hotkeys'][ini_name])


keybinds = [
    ("Capture Screen", hotkey_default('capture'), 'capture'),
    ("Capture Layout", hotkey_default('layout_capture'), 'layout_capture'),
    ("Capture Snippet", hotkey_default('snippet'), 'snippet'),
    ("Exit", hotkey_default('exit'), 'exit'),
    ("Duplicate Latest", hotkey_default('duplicate_latest'), 'duplicate_latest'),
    ("Delete Latest", hotkey_default('delete_latest'), 'delete_latest'),
    ("Debugging", hotkey_default('debug'), 'debug'),
]

DEFAULT_KEYBINDS = [
    ("Capture Screen", 'f2', 'capture'),
    ("Capture Layout", 'f5', 'layout_capture'),
    ("Capture Snippet", 'f4', 'snippet'),
    ("Exit", 'f3', 'exit'),
    ("Duplicate Latest", 'alt+1', 'duplicate_latest'),
    ("Delete Latest", 'alt+2', 'delete_latest'),
    ("Debugging", 'alt+d', 'debug'),
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
        if DEBUGGING:
            print(f"[INFO] Assigned '{name}' → {combo_str}")
        return True
    except Exception:
        if DEBUGGING:
            print(f"[ERROR] Failed to assign '{name}':")
            print(traceback.format_exc())
        return False


def get_display_hotkey(name):
    ini_name = f"{name}_key" if name != "debug" else "debug_key"
    default = next((d for (_, d, n) in keybinds if n == name), "")
    return get_setting('Hotkeys', ini_name, default)


# ---------------- Hotkey parsing ----------------
def normalize_key(evt_key):
    try:
        if isinstance(evt_key, keyboard.Key):
            if evt_key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.ctrl):
                return keyboard.Key.ctrl
            elif evt_key in (keyboard.Key.shift_l, keyboard.Key.shift_r, keyboard.Key.shift):
                return keyboard.Key.shift
            elif evt_key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt):
                return keyboard.Key.alt
            elif evt_key in (keyboard.Key.cmd_l, keyboard.Key.cmd_r, keyboard.Key.cmd):
                return keyboard.Key.cmd
            else:
                return evt_key

        elif hasattr(evt_key, 'char') and evt_key.char:
            ch = evt_key.char
            if len(ch) == 1 and not ch.isprintable():
                code = ord(ch)
                if 1 <= code <= 26:
                    return chr(code + 96)
            return ch.lower()

        elif isinstance(evt_key, str):
            if len(evt_key) == 1 and not evt_key.isprintable():
                code = ord(evt_key)
                if 1 <= code <= 26:
                    return chr(code + 96)
            return evt_key.lower()

    except Exception as e:
        if DEBUGGING:
            print(f"[WARN] normalize_key failed for {evt_key}: {e}")
    return None


def normalize_button(event_code):
    return CONTROLLER_MAP.get(event_code)


def parse_hotkey(hotkey_str):
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
            elif p in ('cmd', 'cmd_l', 'cmd_r', 'win'):
                keys.add(keyboard.Key.cmd)
            elif p.startswith('f') and p[1:].isdigit():
                keys.add(getattr(keyboard.Key, p))
            elif len(p) == 1 and p.isprintable():
                keys.add(p)
            elif p in CONTROLLER_MAP.values():
                keys.add(p)
            else:
                keys.add(getattr(keyboard.Key, p))
        except Exception:
            if DEBUGGING:
                print(f"[WARN] Unknown key part: {p}")
    return frozenset(keys)


def format_key(k):
    if isinstance(k, keyboard.Key):
        name = str(k).split('.')[-1].lower()
        return {
            'alt_l': 'alt', 'alt_r': 'alt',
            'ctrl_l': 'ctrl', 'ctrl_r': 'ctrl',
            'shift_l': 'shift', 'shift_r': 'shift',
            'cmd_l': 'cmd', 'cmd_r': 'cmd'
        }.get(name, name)

    elif isinstance(k, str):
        if len(k) == 1 and not k.isprintable():
            code = ord(k)
            if 1 <= code <= 26:
                return chr(code + 96)
        return k.lower()

    else:
        return str(k).lower()



# ---------------- Initialize runtime hotkeys ----------------
def init_from_settings():
    for (_, default, name) in keybinds:
        try:
            combo_str = get_display_hotkey(name)
            hotkeys[name] = parse_hotkey(combo_str)
        except Exception:
            if DEBUGGING:
                print(f"[ERROR] Failed to load hotkey '{name}':")
                print(traceback.format_exc())
    if DEBUGGING:
        print("[INFO] Keybinds loaded from settings.")


# ---------------- Controller listener ----------------
def controller_listener():
    if DEBUGGING:
        print("[INFO] Controller listener started.")

    gamepads = inputs.devices.gamepads
    if not gamepads:
        if DEBUGGING:
            print("[WARN] No controller detected.")
        return

    gamepad = gamepads[0]

    while True:
        try:
            events = gamepad.read()
            for event in events:
                if event.ev_type == "Key" and event.state == 1:
                    btn = normalize_button(event.code)
                    if not btn:
                        continue
                    pressed = frozenset([btn])
                    for name, combo in hotkeys.items():
                        if combo.issubset(pressed):
                            handler = handlers.get(name)
                            if handler:
                                if DEBUGGING:
                                    print(f"[INFO] Triggering handler '{name}' from controller")
                                handler()
                            break
        except inputs.UnpluggedError:
            if DEBUGGING:
                print("[WARN] Controller unplugged.")
            return
        except Exception:
            if DEBUGGING:
                print(traceback.format_exc())
        time.sleep(0.01)


# ---------------- Recording listener ----------------
def start_recording_popup(index, button_list, root, update_info_labels):
    global _recording_listener, _recording_index, _current_keys, _global_listener
    with _lock:
        if _recording_index is not None:
            if DEBUGGING:
                print("[WARN] Already recording a keybind.")
            return
        if _global_listener:
            _global_listener.stop()
            _global_listener = None
        _recording_index = index
        _current_keys = []

    def finish_recording():
        global _recording_index, _current_keys
        if _recording_index is None:
            return  # already finished/cancelled

        if len(_current_keys) >= 1:
            combo_str = '+'.join(format_key(k) for k in _current_keys)
            btn = button_list[_recording_index]
            btn.after(0, lambda b=btn, t=combo_str: b.configure(text=t))
            update_keybind(keybinds[_recording_index][2], combo_str)
            update_info_labels()

        _current_keys.clear()
        _recording_index = None
        start_global_listener()

    def on_press(key):
        try:
            k = normalize_key(key)
            if k and k not in _current_keys and len(_current_keys) < 3:
                _current_keys.append(k)
            if key == keyboard.Key.esc:
                cancel_recording_popup(button_list)
                return False
        except Exception:
            if DEBUGGING:
                print(traceback.format_exc())

    def on_release(key):
        finish_recording()
        return False

    _recording_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    _recording_listener.start()

    def controller_record_loop():
        global _recording_index, _current_keys
        if DEBUGGING:
            print("[INFO] Recording controller input...")
        if not inputs.devices.gamepads:
            if DEBUGGING:
                print("[WARN] No controller detected.")
            return
        gamepad = inputs.devices.gamepads[0]

        while _recording_index is not None:
            try:
                for event in gamepad.read():
                    if event.ev_type == "Key" and event.state == 1:
                        btn = normalize_button(event.code)
                        if btn:
                            _current_keys.append(btn)
                            finish_recording()
                            return
            except inputs.UnpluggedError:
                if DEBUGGING:
                    print("[WARN] Controller unplugged.")
                return
            except Exception:
                if DEBUGGING:
                    print(traceback.format_exc())
            time.sleep(0.01)

    threading.Thread(target=controller_record_loop, daemon=True).start()

    if DEBUGGING:
        print("[INFO] Recording keys or controller buttons... ESC to cancel.")


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
            btn.after(0, lambda b=btn, t=combo: b.configure(text=t))
        if DEBUGGING:
            print("[INFO] Recording cancelled.")
    except Exception:
        if DEBUGGING:
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
                if DEBUGGING:
                    print(traceback.format_exc())

        def on_release(key):
            try:
                pressed = frozenset(_current_keys)
                for name, combo in hotkeys.items():
                    if combo.issubset(pressed):
                        handler = handlers.get(name)
                        if handler:
                            try:
                                if DEBUGGING:
                                    print(f"[INFO] Triggering handler '{name}' from keyboard")
                                handler()
                            except Exception:
                                if DEBUGGING:
                                    print(f"[ERROR] handler '{name}' threw:")
                                    print(traceback.format_exc())
                        break
                _current_keys.clear()
            except Exception:
                if DEBUGGING:
                    print(traceback.format_exc())

        _global_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        _global_listener.start()
        if DEBUGGING:
            print("[INFO] Global keyboard listener started.")


def stop_global_listener():
    global _global_listener, _current_keys
    with _lock:
        try:
            if _global_listener:
                _global_listener.stop()
                _global_listener = None
        except Exception:
            if DEBUGGING:
                print(traceback.format_exc())
        _current_keys = []


# ---------------- Initialize ----------------
init_from_settings()


def start_controller_thread():
    t = threading.Thread(target=controller_listener, daemon=True)
    t.start()
    return t
