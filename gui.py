import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from pynput import keyboard
import threading
import time
import configparser
import os
import sys
import curio_tracker as tracker
import config as c
import contextlib
from types import SimpleNamespace
from renderer import render_item
from datetime import datetime, timedelta
from functools import partial
import bisect
import curio_keybinds
import ocr_utils as utils

is_dark_mode = True 
images_visible = True
IMAGE_COL_WIDTH = 200
ROW_HEIGHT = 40
original_image_col_width = IMAGE_COL_WIDTH

c.initialize_settings()

def apply_theme():
    global style, header_widgets, item_rows, canvas, content_frame, menu_indices, menu_btn
    if is_dark_mode:
        app_bg = "#2f3136"
        panel_bg = "#36393f"
        widget_bg = "#40444b"
        accent = "#5865f2"
        fg = "#dcddde"
        row_colors = ("#2f3136", "#36393f")
    else:
        app_bg = "#f4f6f8"
        panel_bg = "#f4f6f8"
        widget_bg = "white"
        accent = "#0078d7"
        fg = "black"
        row_colors = ("#f4f6f8", "#e8eaed")

    # ----- App background -----
    root.configure(bg=app_bg)

    # ----- Frames & Labels -----
    style.configure("TFrame", background=panel_bg)
    style.configure("TLabel", background=panel_bg, foreground=fg)
    style.configure("Header.TLabel", background=panel_bg, foreground=fg)
    
    # ----- LabelFrame (Info panel) -----
    style.configure("Info.TLabelframe",
                    background=panel_bg,
                    borderwidth=1,
                    relief="groove")

    style.configure("Info.TLabelframe.Label",
                    background=panel_bg,
                    foreground=fg)      

    # ----- Menu Button -----
    menu_btn.configure(style="MenuButton.TMenubutton")
    style.configure("MenuButton.TMenubutton",
                    background=widget_bg,
                    foreground=fg)
    style.map("MenuButton.TMenubutton",
              background=[("active", accent)],
              foreground=[("active", "white")])

    # ----- Buttons -----
    style.configure("TButton",
                    background=widget_bg,
                    foreground=fg,
                    relief="flat",
                    padding=4)
    style.map("TButton",
              background=[("active", accent)],
              foreground=[("active", "white")])

    # ----- Entry fields -----
    style.configure("TEntry",
                    fieldbackground=widget_bg,
                    foreground=fg,
                    borderwidth=0,
                    insertcolor=fg)

    # ----- Combobox -----
    style.configure("TCombobox",
                    fieldbackground=widget_bg,
                    background=widget_bg,
                    foreground=fg,
                    arrowcolor=fg)
    style.map("TCombobox",
              fieldbackground=[("readonly", widget_bg), ("!disabled", widget_bg)],
              foreground=[("readonly", fg), ("!disabled", fg)],
              selectbackground=[("readonly", accent), ("!disabled", accent)],
              selectforeground=[("readonly", "white"), ("!disabled", "white")])

    # ----- Treeview -----
    style.configure("Treeview",
                    background=widget_bg,
                    fieldbackground=widget_bg,
                    foreground=fg,
                    bordercolor=panel_bg,
                    borderwidth=0,
                    rowheight=40)
    style.map("Treeview",
              background=[("selected", accent)],
              foreground=[("selected", "white")])
    style.configure("Treeview.Heading",
                    background=panel_bg if is_dark_mode else "#e0e0e0",
                    foreground=fg,
                    relief="flat")
    style.map("Treeview.Heading",
              background=[("active", accent), ("!active", panel_bg if is_dark_mode else "#e0e0e0")],
              foreground=[("active", "white"), ("!active", fg)])
    # ----- Console -----
    console_output.config(bg=widget_bg, fg=fg, insertbackground=fg,
                          highlightthickness=0 if is_dark_mode else 1,
                          relief="flat" if is_dark_mode else "solid")

    # ----- Headers -----  
    if 'header_widgets' in globals():
        for lbl in header_widgets:
            lbl.configure(background=panel_bg, foreground=fg)
            # If headers are clickable, bind hover effect
            lbl.bind("<Enter>", lambda e, w=lbl: w.configure(background=accent))
            lbl.bind("<Leave>", lambda e, w=lbl: w.configure(background=panel_bg))

    # ----- Update Menu Checkbuttons colors -----
    if menu_indices:
        for col, index in menu_indices.items():
            menu.entryconfig(index,
                             background=widget_bg,
                             foreground=fg,
                             activebackground=accent,
                             activeforeground="white")


# ----- Listener Functions -----
exit_event = threading.Event()

def handle_capture():
    with redirect_to_capture_console():
        tracker.validateAttempt(c.capturing_prompt)
        tracker.capture_once()
    for item in tracker.parsed_items:
        if not item.duplicate:
            add_item_to_tree(item)

def handle_snippet():
    def process_items(items):
        for item in items:
            if not item.duplicate:
                add_item_to_tree(item)

    def run_capture():
        tracker.validateAttempt(c.capturing_prompt)
        tracker.capture_snippet(root, on_done=lambda items: (
        print(f"[DEBUG] Snippet captured: {len(items)} items"),
        process_items(items)
    ))

    root.after(0, run_capture)

def handle_layout_capture():
    with redirect_to_capture_console():
        tracker.validateAttempt(c.layout_prompt)
        tracker.capture_layout()
        update_blueprint_info()


def handle_exit():
    print(c.exiting_prompt)
    exit_event.set()

    # Immediately destroy root window
    try:
        root.quit()
        root.destroy()
    except Exception:
        pass

    sys.exit(0)


def handle_debugging_toggle():
    c.DEBUGGING = True

handlers = {
    'capture': handle_capture,
    'snippet': handle_snippet,
    'layout_capture': handle_layout_capture,
    'exit': handle_exit,
    'debug': handle_debugging_toggle
}
# --- Helper function to normalize keys consistently ---
def normalize_key(key):
    if isinstance(key, keyboard.Key):
        return key
    elif hasattr(key, 'char') and key.char is not None:
        return key.char.lower()
    else:
        return None  # Ignore unknown key types


@contextlib.contextmanager
def redirect_to_capture_console():
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = capture_console
    sys.stderr = capture_console
    try:
        yield
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr


class TextRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, s):
        self.text_widget.config(state='normal')
        self.text_widget.insert(tk.END, s)
        self.text_widget.see(tk.END)
        self.text_widget.config(state='disabled')

    def flush(self):
        pass

def log_to_console(text):
    if c.DEBUGGING:
        print(text)




# ----- Global State -----
recording_index = None
current_keys = []
listener = None
hotkeys = {}
record_buttons = []

# ----- GUI Setup -----
root = tk.Tk()

tracker.root = root
root.title("Heist Curio Tracker")

# Set PNG icon
icon_img = tk.PhotoImage(file=tracker.get_resource_path("assets/icon.png"))
root.iconphoto(True, icon_img)
root.geometry("1020x650")
root.protocol("WM_DELETE_WINDOW", handle_exit)
root.resizable(True, True)

# ----- Menu Setup -----
menubar = tk.Menu(root)
root.config(menu=menubar)


KEYBIND_STARTING_INDEX = 0
EXTRA_BUTTON_INDEX = KEYBIND_STARTING_INDEX

settings_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Settings", menu=settings_menu)
settings_menu.add_command(label="Keybinds", command=lambda: open_keybinds_popup())

def open_keybinds_popup():
    popup = tk.Toplevel(root)
    popup.title("Keybind Settings")
    popup.geometry("320x300")
    popup.resizable(False, False)
    popup.grab_set()  # make modal

    frame = ttk.Frame(popup, padding=10)
    frame.pack(fill="both", expand=True)

    popup_buttons = []

    for i, (label_text, default_value, hotkey_name) in enumerate(curio_keybinds.keybinds):
        ttk.Label(frame, text=label_text + ":").grid(row=i, column=0, sticky="w", pady=(5,2))

        # get current hotkey display
        current_label = curio_keybinds.get_display_hotkey(hotkey_name)

        # create the button
        btn = ttk.Button(frame,
                         text=current_label,
                         width=16,
                         command=lambda idx=i, b_list=popup_buttons: start_recording(idx, b_list, popup))
        btn.grid(row=i, column=1, padx=5, pady=2, sticky="w")
        popup_buttons.append(btn)

    # Reset All Button
    def reset_all():
        for i, (_, default_value, name) in enumerate(curio_keybinds.keybinds):
            btn = popup_buttons[i]
            btn.config(text=default_value)
            curio_keybinds.update_keybind(name, default_value)
            update_info_labels()
        print("[INFO] Keybinds reset to defaults.")

    reset_btn = ttk.Button(frame, text="Reset All Keybinds", command=reset_all)
    reset_btn.grid(row=len(curio_keybinds.keybinds), column=0, columnspan=2, pady=(10,0))


def start_recording(index, button_list, popup):
    # Stop any existing recording listener
    curio_keybinds.cancel_recording_popup(button_list)

    # Start a new recording popup
    curio_keybinds.start_recording_popup(index, button_list, popup, update_info_labels)

def toggle_theme_menu():
    toggle_theme()  # reuse your existing function
settings_menu.add_separator() 

settings_menu.add_command(label="Toggle Theme (Light/Dark)", command=toggle_theme_menu)

style = ttk.Style(root)
try:
    style.theme_use('clam')
except Exception:
    pass
style.configure('TFrame', background='#f4f6f8')
style.configure('TLabel', background='#f4f6f8', font=('Segoe UI', 10))
style.configure('Header.TLabel', font=('Segoe UI', 11, 'bold'))
style.configure('TButton', padding=6)
style.configure('Small.TLabel', font=('Segoe UI', 9))
style.configure("Treeview", rowheight=ROW_HEIGHT, padding=0)

# Add padding for buttons and frames
PAD_X = 10
PAD_Y = 10

# ---------- Layout Control ----------

root.grid_columnconfigure(0, weight=0, minsize=280)  # Left panel (Keybinds)
root.grid_columnconfigure(1, weight=1)               # Right panel (Tree/Image)
# ---------- Capture Console (Bottom) ----------
# Make sure the window can handle two rows
root.grid_rowconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=0)
# Make the right frame expandable
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(2, weight=1)

# ---------- Frames ----------
left_frame = ttk.Frame(root)
left_frame.grid(row=0, column=0, padx=(5, 10), pady=10, sticky="nw")

right_frame = ttk.Frame(root)
right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

# Make right_frame expandable
right_frame.grid_rowconfigure(0, weight=1)  # tree_frame row grows
right_frame.grid_rowconfigure(1, weight=0)  # toggle_frame row fixed
right_frame.grid_columnconfigure(0, weight=1)

# --- Inner frame for Treeview + Scrollbars ---
tree_frame = ttk.Frame(right_frame)
tree_frame.grid(row=0, column=0, sticky="nsew")
tree_frame.grid_rowconfigure(0, weight=1)
tree_frame.grid_columnconfigure(0, weight=1)

# ---------- Virtualized Treeview Globals ----------
VISIBLE_ROW_BUFFER = 50   # Number of rows rendered at once
all_items_data = []       # Full list of items to display
rendered_iids = []        # Currently rendered Treeview row IDs

columns = ("item", "value", "numeric_value", "type", "stack_size", "area_level", 
           "layout", "player", "league", "time")
tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings")
tree["displaycolumns"] = ("item", "value", "type", "stack_size", "area_level",
                          "layout", "player", "league", "time")
# Headings
tree.heading("#0", text="Image")
tree.heading("item", text="Item / Enchant", command=lambda: sort_tree("item"))
tree.heading("value", text="Estimated Value", command=lambda: sort_tree("value"))
tree.heading("type", text="Type", command=lambda: sort_tree("type"))
tree.heading("stack_size", text="Stack Size", command=lambda: sort_tree("stack_size"))
tree.heading("area_level", text="Area Level", command=lambda: sort_tree("area_level"))
tree.heading("layout", text="BP Layout", command=lambda: sort_tree("layout"))
tree.heading("player", text="Found by", command=lambda: sort_tree("player"))
tree.heading("league", text="League", command=lambda: sort_tree("league"))
tree.heading("time", text="Time", command=lambda: sort_tree("time"))

# Column widths
tree.column("#0", width=IMAGE_COL_WIDTH, anchor="center", stretch=False) 
tree.column("item", width=400, anchor="center", stretch=True)
tree.column("value", width=120, anchor="center", stretch=True)
tree.column("type", width=120, anchor="center", stretch=True)
tree.column("stack_size", width=100, anchor="center", stretch=True)
tree.column("area_level", width=100, anchor="center", stretch=True)
tree.column("layout", width=120, anchor="center", stretch=True)
tree.column("player", width=120, anchor="center", stretch=True)
tree.column("league", width=100, anchor="center", stretch=True)
tree.column("time", width=150, anchor="center", stretch=True)

# Scrollbars inside tree_frame
v_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
h_scrollbar = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

# Grid placement
tree.grid(row=0, column=0, sticky="nsew")
v_scrollbar.grid(row=0, column=1, sticky="ns")
h_scrollbar.grid(row=1, column=0, sticky="ew", ipady=2)

# --- Toggle buttons frame below tree_frame ---
toggle_frame = ttk.Frame(right_frame)
toggle_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))

# Make sure toggle_frame does not expand vertically
right_frame.grid_rowconfigure(1, weight=0)

# ---------- Image cache ----------
original_img_cache = {}  # key -> original PIL.Image
image_cache = {}         # key -> PhotoImage for Treeview

# Row tags for alternating colors
tree.tag_configure("odd", background="#2f3136", foreground="#dcddde")
tree.tag_configure("even", background="#36393f", foreground="#dcddde")
tree.tag_configure("light_odd", background="#f4f6f8", foreground="black")
tree.tag_configure("light_even", background="#e8eaed", foreground="black")

# ---------- Add Item ----------
item_counters = {}  # global dict to track counts per item name

def get_item_name_str(item):
    name = getattr(item, 'itemName', 'Unknown')
    if hasattr(name, 'lines'):
        # join lines into a plain string
        return "_".join([str(line) for line in name.lines])
    elif isinstance(name, str):
        return name
    else:
        return str(name)

def generate_item_id(item):
    item_name = getattr(item, "itemName", "Unknown")

    # Make sure the key is a string
    item_name_str = str(item_name)

    count = item_counters.get(item_name_str, 0) + 1
    item_counters[item_name_str] = count
    
    return f"{item_name_str}_{count}"

# Keep global structures
sorted_item_keys = []  # list of (timestamp, key)
item_time_map = {}     # key -> datetime
all_item_iids = set(tree.get_children())  # initially loaded items

def format_chaos_value(value: str) -> str:
    if not value or value.strip() == "":
        return "" 
    
    try:
        f = float(value)
    except ValueError:
        return ""  
    
    # Round to 1 decimal
    f_rounded = round(f, 1)
    
    # Convert to string
    if f_rounded.is_integer():
        return str(int(f_rounded))  # drop .0
    return str(f_rounded)

# Track last visible rows
_last_visible_iids = set()

_last_update = 0
def update_visible_images(event=None):
    global _last_visible_iids, _last_update
    now = time.time()
    if now - _last_update < 0.1:  # 100ms throttle
        return
    _last_update = now

    if not images_visible:
        return

    first_frac, last_frac = tree.yview()
    children = tree.get_children()
    total = len(children)
    if total == 0:
        return

    first_idx = int(first_frac * total)
    last_idx = int(last_frac * total) + 1
    current_visible = set(children[first_idx:last_idx])

    # Remove images for rows no longer visible
    for iid in _last_visible_iids - current_visible:
        if tree.exists(iid):
            tree.item(iid, image="")
            image_cache.pop(iid, None)

    # Add images for newly visible rows
    for iid in current_visible - _last_visible_iids:
        if iid not in image_cache and tree.exists(iid):
            pil_img = original_img_cache.get(iid)
            if pil_img:
                # Only create PhotoImage now
                image_cache[iid] = ImageTk.PhotoImage(pil_img)
                tree.item(iid, image=image_cache[iid])

    _last_visible_iids = current_visible


def add_item_to_tree(item, historical_counter=None, render_image=False):
    global sorted_item_keys, item_time_map

    item_name_str = get_item_name_str(item)
    if historical_counter is not None:
        item_key = f"{item_name_str}_{historical_counter}"
    else:
        item_key = generate_item_id(item)  # unique for live items

    # ---- Render image ----
    if item_key not in original_img_cache:
        img = render_item(item)
        img = img.resize((IMAGE_COL_WIDTH - 4, ROW_HEIGHT), Image.LANCZOS)
        img = pad_image(img, left_pad=-20, top_pad=0,
                        target_width=IMAGE_COL_WIDTH, target_height=ROW_HEIGHT)
        original_img_cache[item_key] = img.copy()

    # ---- Item text ----
    if getattr(item, "enchants", None) and len(item.enchants) > 0:
        item_text = "\n".join([str(e) for e in item.enchants])
    else:
        item_text = getattr(item, "itemName", "Unknown")
        if hasattr(item_text, "lines"):
            item_text = "\n".join([str(line) for line in item_text.lines])

    # ---- Parse timestamp ----
    item_time_obj = getattr(item, "time", None)
    if isinstance(item_time_obj, str):
        try:
            current_year = datetime.now().year
            item_time_obj = datetime.strptime(
                f"{item_time_obj} {current_year}", "%b %d %H:%M %Y"
            )
        except Exception:
            item_time_obj = None
    elif not isinstance(item_time_obj, datetime):
        item_time_obj = None

    item_time_map[item_key] = item_time_obj
    display_time = (
        item_time_obj.strftime("%d %b %Y - %H:%M") if item_time_obj else "Unknown"
    )

    # ---- Sorting ----
    if item_time_obj:
        entry = (item_time_obj, item_key)
        if sort_reverse.get("time"):
            index = len(sorted_item_keys) - bisect.bisect_left(
                list(reversed([t for t, _ in sorted_item_keys])),
                item_time_obj
            )
        else:
            index = bisect.bisect_left([t for t, _ in sorted_item_keys], item_time_obj)
        sorted_item_keys.insert(index, entry)
    else:
        index = "end"
        sorted_item_keys.append((datetime.min, item_key))

    # ---- Row styling ----
    row_index = index if isinstance(index, int) else len(tree.get_children())
    tag = "odd" if row_index % 2 == 0 else "even"
    if not is_dark_mode:
        tag = "light_odd" if row_index % 2 == 0 else "light_even"

    chaosValue = getattr(item, "chaos_value", "")
    divineValue = getattr(item, "divine_value", "")
    stack_size = getattr(item, "stack_size", "")

    item_type = getattr(item, "type", "N/A")

    # Convert to floats safely
    try:
        chaos_float = float(chaosValue)
    except (ValueError, TypeError):
        chaos_float = 0

    try:
        divine_float = float(divineValue)
    except (ValueError, TypeError):
        divine_float = 0

    try:
        stack_size = int(stack_size)
    except (ValueError, TypeError):
        stack_size = 1

    # Multiply by stack size if more than 1
    if stack_size > 1:
        chaos_float *= stack_size
        divine_float *= stack_size

    # Helper to format numbers: drop .0 for integers
    def format_value(f):
        if f.is_integer():
            return str(int(f))
        return str(round(f, 1))  # keep 1 decimal

    # Determine display value
    if divine_float >= 0.5:
        display_value = f"{format_value(divine_float)} Divines"
    elif chaos_float > 0:
        display_value = f"{format_value(chaos_float)} Chaos"
    else:
        display_value = ""  # show nothing if both are 0 or invalid

    numeric_value = chaos_float
    stack_size_txt = (
            stack_size
            if int(stack_size) > 0 and utils.is_currency_or_scarab(item_type)
            else ""
        )

    # ---- Insert into Treeview ----
    iid = item_key
    tree.insert(
        "", index,
        iid=iid,
        image="",  
        values=(item_text,
                display_value,
                numeric_value,
                item_type,
                stack_size_txt,
                getattr(item, "area_level", "83"),
                getattr(item, "blueprint_type", "Prohibited Library"),
                getattr(item, "logged_by", ""),
                getattr(item, "league", "3.26"),
                display_time),
        tags=(tag,)
    )
    all_item_iids.add(iid)

    if render_image:
        update_visible_images()


_last_visible_range = (0, 0)

def render_visible_window():
    global _last_visible_range
    if not all_items_data:
        return

    first_frac, last_frac = tree.yview()
    total = len(all_items_data)
    first_idx = int(first_frac * total)
    last_idx = int(last_frac * total) + 1

    # Only update if the visible range changed
    if (first_idx, last_idx) == _last_visible_range:
        return
    _last_visible_range = (first_idx, last_idx)

    # Clear Treeview temporarily
    tree.delete(*tree.get_children())
    sorted_item_keys.clear()
    all_item_iids.clear()
    image_cache.clear()

    for i in range(first_idx, last_idx):
        add_item_to_tree(all_items_data[i], historical_counter=i, render_image=False)

    update_visible_images() 

tree.bind("<Configure>", lambda e: update_visible_images())
v_scrollbar.config(command=lambda *args: (tree.yview(*args), update_visible_images()))
tree.bind("<Motion>", lambda e: update_visible_images())


def pad_image(img, left_pad=0, top_pad=0, target_width=200, target_height=40):
    # Create new blank image with transparent background
    new_img = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
    new_img.paste(img, (0, 0))
    return new_img

def update_total_items_count():
    total_items_var.set(f"Total: {len(all_item_iids)}")

# ---------- Load Functions ----------
def load_all_items_threaded():
    def worker():
        all_items = tracker.load_all_parsed_items_from_csv()
        reverse_load = sort_reverse.get("time", True)
        if reverse_load:
            all_items = list(reversed(all_items))

        # Schedule batches to the main thread (Tkinter must only modify widgets in main thread)
        root.after(0, add_items_in_batches, all_items)

    threading.Thread(target=worker, daemon=True).start()

def add_items_in_batches(items, batch_size=200, start_index=0):
    end_index = min(start_index + batch_size, len(items))
    for i in range(start_index, end_index):
        # Add item but don't render images yet
        add_item_to_tree(items[i], historical_counter=i, render_image=False)

    if end_index < len(items):
        # Schedule next batch
        root.after(15, add_items_in_batches, items, batch_size, end_index)
    else:
        update_visible_images()
        filter_tree_by_time()
        update_total_items_count()

def load_all_items():
    tree.delete(*tree.get_children())  # clear all existing items
    all_items = tracker.load_all_parsed_items_from_csv()

    reverse_load = sort_reverse.get("time", True)
    if reverse_load:
        all_items = list(reversed(all_items))

    # Add items in batches (images rendered lazily)
    add_items_in_batches(all_items)


# ----- Load Latest 5 Items -----
def load_latest_wing():
    tree.delete(*tree.get_children())  # clear all existing items
    tracker.parsed_items = tracker.load_recent_parsed_items_from_csv(max_items=5)
    if not tracker.parsed_items:
        return

    reverse_load = sort_reverse.get("time", True)
    items_to_add = list(reversed(tracker.parsed_items)) if reverse_load else tracker.parsed_items

    for i, item in enumerate(items_to_add):
        add_item_to_tree(item, historical_counter=i, render_image=True)

    filter_tree_by_time()
    update_total_items_count()

# ----- Load Latest 1 Item -----
def load_latest_item():
    tree.delete(*tree.get_children())  # clear current items
    tracker.parsed_items = tracker.load_recent_parsed_items_from_csv(max_items=1)
    if not tracker.parsed_items:
        return

    item = tracker.parsed_items[0]
    add_item_to_tree(item, historical_counter=i, render_image=True)
    filter_tree_by_time()
    update_total_items_count()

# ----- Clear Tree ----- 
def clear_tree():
    tree.delete(*tree.get_children())
    _last_visible_iids.clear()
    sorted_item_keys.clear()
    item_time_map.clear()
    all_item_iids.clear()
    original_img_cache.clear()
    image_cache.clear()


# ---------- Sorting ----------
sort_reverse = {"img": False, "item": False, "value": False, "type": True, "stack_size": False, "area_level": False, "layout": False, "player": False, "league": False, "time": True}

def sort_tree(column):
    children = tree.get_children()
    items = [(tree.set(iid, column), iid) for iid in children]

    if column == "value":
        items.sort(key=lambda x: float(tree.set(x[1], "numeric_value")), reverse=sort_reverse[column])

    elif column == "time":
        from datetime import datetime
        def parse_time(val):
            try:
                return datetime.strptime(val, "%d %b %Y - %H:%M")
            except Exception:
                return datetime.min
        items.sort(key=lambda x: parse_time(x[0]), reverse=sort_reverse[column])
    else:
        items.sort(key=lambda x: x[0].lower(), reverse=sort_reverse[column])

    for index, (val, iid) in enumerate(items):
        tree.move(iid, "", index)
        tag = "odd" if index % 2 == 0 else "even"
        if not is_dark_mode:
            tag = "light_odd" if index % 2 == 0 else "light_even"
        tree.item(iid, tags=(tag,))

    sort_reverse[column] = not sort_reverse[column]

# ---------- Filtering by Time ----------
def filter_tree_by_time(*args):
    selected = time_filter_var.get()
    now = datetime.now()

    for iid in all_item_iids:
        if not tree.exists(iid):
            continue
        dt = item_time_map.get(iid)
        show = False

        if dt is None:
            show = False
        else:
            delta = now - dt
            if selected == "All":
                show = True
            elif selected == "Today":
                show = dt.date() == now.date()
            elif selected == "Last hour":
                show = delta <= timedelta(hours=1)
            elif selected == "Last 2 hours":
                show = delta <= timedelta(hours=2)
            elif selected == "Last 12 hours":
                show = delta <= timedelta(hours=12)
            elif selected == "Last 24 hours":
                show = delta <= timedelta(days=1)
            elif selected == "Last week":
                show = delta <= timedelta(weeks=1)
            elif selected == "Last 2 weeks":
                show = delta <= timedelta(weeks=2)
            elif selected == "Last month":
                show = delta <= timedelta(days=30)
            elif selected == "Last year":
                show = delta <= timedelta(days=365)

        if show:
            tree.reattach(iid, "", "end")
        else:
            tree.detach(iid)

time_filter_var = tk.StringVar(value="All")
time_filter_var.trace_add("write", filter_tree_by_time)


def open_custom_hours_popup():
    popup = tk.Toplevel(root)
    popup.title("Custom Hours Filter")
    popup.geometry("250x100")
    popup.resizable(True, True)
    popup.grab_set()  # modal

    ttk.Label(popup, text="Enter hours:").pack(pady=(10, 5))

    entry_var = tk.StringVar(value="")
    entry = ttk.Entry(popup, textvariable=entry_var, width=10)
    entry.pack()

    def apply_custom():
        try:
            hours = float(entry_var.get())
            custom_hours_var.set(str(hours))
        except ValueError:
            tk.messagebox.showerror("Invalid Input", "Please enter a number.")
            return
        popup.destroy()
        filter_tree_by_time()

    ttk.Button(popup, text="Apply", command=apply_custom).pack(pady=10)

    entry.focus()
    entry.bind("<Return>", lambda e: apply_custom())

# Define time filter variable and dropdown
time_options = [
    "All", "Last hour", "Last 2 hours", "Last 12 hours", "Today", "Last 24 hours", "Last week", "Last 2 weeks", "Last month", "Last year", "Custom..."
]
# Then attach to the dropdown without recreating it
time_filter_dropdown = ttk.Combobox(
    left_frame,
    textvariable=time_filter_var,
    values=time_options,
    width=20,
    state="readonly"
)
time_filter_dropdown.grid(row=EXTRA_BUTTON_INDEX, column=1, sticky="w", pady=(5,2))
ttk.Label(left_frame, text="Filter by Time:").grid(row=EXTRA_BUTTON_INDEX, column=0, sticky="w", pady=(5,2))
EXTRA_BUTTON_INDEX += 1

def update_img_column_state(show_column: bool):
    global images_visible

    if show_column:
        # Restore width & enable toggle button
        tree.column("img", width=IMAGE_COL_WIDTH, minwidth=20, stretch=False)
        toggle_img_btn.state(["!disabled"])
    else:
        # Hide column & disable toggle button
        tree.column("img", width=0, minwidth=0)
        toggle_img_btn.state(["disabled"])
        # Remove images from rows
        for iid in tree.get_children():
            tree.item(iid, image='')

    # Maintain correct order for displaycolumns
    current_displayed = list(tree["displaycolumns"])
    if show_column and "img" not in current_displayed:
        # Insert 'img' at its original position
        index = columns.index("img")
        current_displayed.insert(index, "img")
    elif not show_column and "img" in current_displayed:
        current_displayed.remove("img")

    tree["displaycolumns"] = current_displayed

def toggle_images():
    global images_visible
    images_visible = not images_visible

    for iid in tree.get_children():
        orig_img = original_img_cache.get(iid)
        if images_visible and orig_img:
            photo = ImageTk.PhotoImage(orig_img)
            tree.item(iid, image=photo)
            image_cache[iid] = photo
        else:
            tree.item(iid, image='')

    tree.column("#0", width=IMAGE_COL_WIDTH if images_visible else 0)

def toggle_image_column(show):
    toggle_img_btn.state(["!disabled"] if show else ["disabled"])
    tree.column("#0", width=IMAGE_COL_WIDTH if show else 0)

def toggle_column_tree(col_name, show):
    if col_name == "img":
        update_img_column_state(show)
    else:
        # Respect original order for other columns
        current_displayed = list(tree["displaycolumns"])
        if show and col_name not in current_displayed:
            index = columns.index(col_name)
            current_displayed.insert(index, col_name)
        elif not show and col_name in current_displayed:
            current_displayed.remove(col_name)
        tree["displaycolumns"] = current_displayed

EXTRA_BUTTON_INDEX+1

# Example buttons for toggling columns
toggle_frame = ttk.Frame(right_frame)
toggle_frame.grid(row=EXTRA_BUTTON_INDEX, column=0, columnspan=2, sticky="ew", pady=(0,5))

# Dropdown-style menu button
menu_btn = ttk.Menubutton(toggle_frame, text="Columns")
menu = tk.Menu(menu_btn, tearoff=False)
menu_btn["menu"] = menu
menu_btn.grid(row=0, column=0, padx=5)

# Track checked state per column
col_vars = {}
menu_indices = {}  # store menu item indices

for i, col in enumerate(columns):
    var = tk.BooleanVar(value=True)
    col_vars[col] = var
    menu.add_checkbutton(
        label=col.title(),
        variable=var,
        command=lambda c=col, v=var: toggle_column_tree(c, v.get())
    )
    menu_indices[col] = i  # save the menu index

# Keep the existing toggle images button separate
toggle_img_btn = ttk.Button(toggle_frame, text="Toggle Images", command=toggle_images)
toggle_img_btn.grid(row=0, column=1, padx=5)

# ----- Capture Output Console (Bottom) -----
console_frame = ttk.Frame(root)
console_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="ew")
console_output = tk.Text(console_frame, height=6, width=110, wrap="word", state="disabled")
console_output.pack(side="left", fill="both", expand=True)

scrollbar = ttk.Scrollbar(console_frame, command=console_output.yview)
scrollbar.pack(side="right", fill="y")
console_output['yscrollcommand'] = scrollbar.set
capture_console = TextRedirector(console_output)

def toggle_theme():
    global is_dark_mode
    is_dark_mode = not is_dark_mode
    apply_theme()


# ----- GUI Layout -----
settings_menu.add_separator() 
settings_menu.add_command(label="Exit", command=handle_exit)


load_latest_btn = ttk.Button(left_frame, text="Load Latest Wing", command=load_latest_wing)
load_latest_btn.grid(row=EXTRA_BUTTON_INDEX, column=0, pady=10, sticky="ew")

load_all_btn = ttk.Button(left_frame, text="Load All Data", command=load_all_items_threaded)
load_all_btn.grid(row=EXTRA_BUTTON_INDEX, column=1, pady=10, sticky="ew")
EXTRA_BUTTON_INDEX += 1

load_latest_1_btn = ttk.Button(left_frame, text="Load Latest 1 Item", command=load_latest_item)
load_latest_1_btn.grid(row=EXTRA_BUTTON_INDEX, column=0, pady=5, sticky="ew")

clear_tree_btn = ttk.Button(left_frame, text="Clear Tree", command=clear_tree)
clear_tree_btn.grid(row=EXTRA_BUTTON_INDEX, column=1, pady=5, sticky="ew")

EXTRA_BUTTON_INDEX += 1

# ----- PoE Player Label and Textbox -----
ttk.Label(left_frame, text="PoE Player:").grid(row=EXTRA_BUTTON_INDEX, column=0, sticky="w", pady=(5, 2))
poe_player_var = tk.StringVar(value=getattr(tracker, "poe_user", ""))  # default from tracker
poe_player_entry = ttk.Entry(left_frame, textvariable=poe_player_var, width=20)
poe_player_entry.grid(row=EXTRA_BUTTON_INDEX, column=1, pady=(5, 2), sticky="w")
poe_player_entry['state'] = 'normal'  # editable

EXTRA_BUTTON_INDEX += 1

def update_poe_player(*args):
    tracker.poe_user = poe_player_var.get()
    utils.set_setting('User', 'poe_user', tracker.poe_user)
    if c.DEBUGGING:
        print(f"[DEBUG] PoE Player set to: {tracker.poe_user}")


poe_player_var.trace_add("write", update_poe_player)

# ----- League Label and Dropdown -----
league_versions = [
    "3.26", "3.25", "3.24", "3.23", "3.22", "3.21",
    "3.20", "3.19", "3.18", "3.17", "3.16", "3.15",
    "3.14", "3.13", "3.12"
]

ttk.Label(left_frame, text="League:").grid(row=EXTRA_BUTTON_INDEX, column=0, sticky="w", pady=(5, 2))
league_var = tk.StringVar(value=getattr(tracker, "league_version", league_versions[0]))  # default first
league_entry = ttk.Combobox(left_frame, textvariable=league_var, values=league_versions, width=20)
league_entry.grid(row=EXTRA_BUTTON_INDEX, column=1, pady=(5, 2), sticky="w")
league_entry['state'] = 'normal'  # editable

EXTRA_BUTTON_INDEX += 1

def update_league(*args):
    tracker.league_version = league_var.get()
    utils.set_setting('User', 'poe_league', tracker.league_version)
    if c.DEBUGGING:
        print(f"[DEBUG] League set to: {tracker.league_version}")

tracker.poe_user = utils.get_setting('User', 'poe_user', getattr(tracker, 'poe_user', ''))
poe_player_var.set(tracker.poe_user)

tracker.league_version = utils.get_setting('User', 'poe_league', getattr(tracker, 'poe_league', league_versions[0]))
league_var.set(tracker.league_version)


league_var.trace_add("write", update_league)

# ----- Blueprint Info Labels and Editable Textboxes -----
layout_keywords = [
    "Bunker", "Records Office", "Mansion", "Smuggler's Den",
    "Underbelly", "Laboratory", "Prohibited Library", "Repository", "Tunnels"
]

ttk.Label(left_frame, text="Blueprint Type:").grid(row=EXTRA_BUTTON_INDEX, column=0, sticky="w", pady=(5, 2))
blueprint_type_var = tk.StringVar(value=tracker.blueprint_layout)
blueprint_type_entry = ttk.Combobox(left_frame, textvariable=blueprint_type_var, values=layout_keywords, width=20)
blueprint_type_entry.grid(row=EXTRA_BUTTON_INDEX, column=1, pady=(5, 2), sticky="w")
blueprint_type_entry['state'] = 'normal'  # editable

EXTRA_BUTTON_INDEX += 1

def validate_area_level(P):
    if P == "":
        return True  # allow clearing
    if P.isdigit() and 1 <= int(P) <= 86:
        return True
    return False

vcmd = (root.register(validate_area_level), "%P")

ttk.Label(left_frame, text="Area Level:").grid(row=EXTRA_BUTTON_INDEX, column=0, sticky="w", pady=(5, 2))
area_level_var = tk.StringVar(value=str(tracker.blueprint_area_level))
area_level_entry = ttk.Entry(left_frame, textvariable=area_level_var, width=20, validate="key", validatecommand=vcmd)
area_level_entry.grid(row=EXTRA_BUTTON_INDEX, column=1, pady=(5, 2), sticky="w")

EXTRA_BUTTON_INDEX+=1

# ----- Global flag -----
updating_from_tracker = False

# ----- Update tracker automatically when user types -----
def update_tracker_blueprint(*args):
    global updating_from_tracker
    if updating_from_tracker:
        return  # skip updates triggered by code

    layout = blueprint_type_var.get()
    level_str = area_level_var.get()
    level = int(level_str) if level_str.isdigit() else tracker.blueprint_area_level
    tracker.blueprint_layout = layout
    tracker.blueprint_area_level = level

    if c.DEBUGGING:
        print(f"[DEBUG] Blueprint updated from Entry → Type: {layout}, Level: {level}")

blueprint_type_var.trace_add("write", update_tracker_blueprint)
area_level_var.trace_add("write", update_tracker_blueprint)

def update_blueprint_info():
    global updating_from_tracker
    updating_from_tracker = True  # block trace callback

    blueprint_type_var.set(tracker.blueprint_layout)
    area_level_var.set(str(tracker.blueprint_area_level))

    updating_from_tracker = False

# --- Separator before Search Bar ---
separator = ttk.Separator(left_frame, orient='horizontal')
separator.grid(row=EXTRA_BUTTON_INDEX, column=0, columnspan=2, sticky="ew", pady=(10, 5))

EXTRA_BUTTON_INDEX += 1  # move to next row for the search bar

# --- Search Bar ---
ttk.Label(left_frame, text="Search:").grid(row=EXTRA_BUTTON_INDEX, column=0, sticky="w", pady=(5, 2))

search_var = tk.StringVar()
search_entry = ttk.Entry(left_frame, textvariable=search_var, width=20)
search_entry.grid(row=EXTRA_BUTTON_INDEX, column=1, pady=(5, 2), sticky="w")

EXTRA_BUTTON_INDEX += 1  # move to next row for counter

# --- Search Counter (below the search bar) ---
search_count_var = tk.StringVar(value="Found: 0")
search_count_label = ttk.Label(left_frame, textvariable=search_count_var)
search_count_label.grid(row=EXTRA_BUTTON_INDEX, column=0, columnspan=2, sticky="w", pady=(0, 5))

def search_items(*args):
    query = search_var.get().lower().strip()
    matched_count = 0

    for iid in all_item_iids:
        if not tree.exists(iid):
            continue  # skip iids that were deleted

        values = tree.item(iid, "values")
        text = " ".join(str(v).lower() for v in values)
        if query and query not in text:
            tree.detach(iid)
        else:
            tree.reattach(iid, "", "end")
            matched_count += 1

    search_count_var.set(f"Found: {matched_count}")
    update_total_items_count()

# Live filter: runs automatically when typing
search_var.trace_add("write", search_items)

EXTRA_BUTTON_INDEX += 1

# --- Total Items Label (under search counter) ---
total_items_var = tk.StringVar(value="Total: 0")
total_items_label = ttk.Label(left_frame, textvariable=total_items_var)
total_items_label.grid(row=EXTRA_BUTTON_INDEX, column=0, columnspan=2, sticky="w", pady=(0, 5))

EXTRA_BUTTON_INDEX += 1

def toggle_console():
    if console_frame.winfo_ismapped():
        console_frame.grid_remove()
        console_toggle_btn.config(text="▲ Console")  # pointing up to expand
    else:
        console_frame.grid()
        console_toggle_btn.config(text="▼ Console")  # pointing down to collapse

console_toggle_btn = ttk.Button(toggle_frame, text="▼ Console", width=12, command=toggle_console)
console_toggle_btn.grid(row=0, column=3, padx=5, sticky="w")
EXTRA_BUTTON_INDEX += 1

separator = ttk.Separator(left_frame, orient='horizontal')
separator.grid(row=EXTRA_BUTTON_INDEX, column=0, columnspan=2, sticky="ew", pady=(10, 5))

EXTRA_BUTTON_INDEX += 1  # move to next row for the search bar

# ---------- Info Panel ----------
info_frame = ttk.LabelFrame(left_frame, text="Info", style="Info.TLabelframe", padding=(8,4,8,4))
info_frame.grid(row=EXTRA_BUTTON_INDEX, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

row_index = 0
info_labels = {}  # store references

info_labels['capture'] = ttk.Label(info_frame, text=c.info_show_keys_capture,
                                   wraplength=220, justify="left", style="TLabel")
info_labels['capture'].grid(row=row_index, column=0, sticky="w", padx=4, pady=2)
row_index += 1

info_labels['snippet'] = ttk.Label(info_frame, text=c.info_show_keys_snippet,
                                   wraplength=220, justify="left", style="TLabel")
info_labels['snippet'].grid(row=row_index, column=0, sticky="w", padx=4, pady=2)
row_index += 1

info_labels['layout'] = ttk.Label(info_frame, text=c.info_show_keys_layout,
                                  wraplength=220, justify="left", style="TLabel")
info_labels['layout'].grid(row=row_index, column=0, sticky="w", padx=4, pady=2)
row_index += 1

info_labels['exit'] = ttk.Label(info_frame, text=c.info_show_keys_exit,
                                wraplength=220, justify="left", style="TLabel")
info_labels['exit'].grid(row=row_index, column=0, sticky="w", padx=4, pady=2)
row_index += 1


def update_info_labels():
    info_labels['capture'].config(text=f"Press {curio_keybinds.get_display_hotkey('capture')} to capture all curios on screen (no duplicates).")
    info_labels['snippet'].config(text=f"Press {curio_keybinds.get_display_hotkey('snippet')} to snippet a region to capture allows duplicates.")
    info_labels['layout'].config(text=f"Press {curio_keybinds.get_display_hotkey('layout_capture')} to set current layout.")
    info_labels['exit'].config(text=f"Press {curio_keybinds.get_display_hotkey('exit')} to exit the script.")

update_info_labels()

EXTRA_BUTTON_INDEX += 1


curio_keybinds.handlers = {
    'capture': handle_capture,
    'snippet': handle_snippet,
    'layout_capture': handle_layout_capture,
    'exit': handle_exit,
    'debug': handle_debugging_toggle
}

# init runtime hotkeys from file
curio_keybinds.init_from_settings()
curio_keybinds.start_global_listener()

# ----- Run App -----
apply_theme()
# shift_to_left()
root.mainloop()
