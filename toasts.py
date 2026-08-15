import tkinter as tk
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

import currency_utils
import fonts
import ocr_utils as utils
from logger import log_message
from renderer import render_item, get_border_color
from settings import get_setting, set_setting
from tree_manager import TreeManager

IMAGE_COL_WIDTH = int(get_setting("Application", "toast_image_width", 200))
ROW_HEIGHT = int(get_setting("Application", "toast_row_height", 40))
TOAST_FONT_SIZE = int(get_setting("Application", "toast_font_size", 11))
TOAST_HEADLINE_FONT_SIZE = int(get_setting("Application", "toast_headline_font_size", 10))
TOASTS = []
TOAST_MARGIN, TOAST_SPACING, TOAST_PADDING = 10, 6, 4
TOASTS_DURATION = get_setting('Application', 'toasts_duration_seconds', 5)
ARE_TOASTS_ENABLED = get_setting('Application', 'are_toasts_enabled', True)
TOAST_POSITION = get_setting("Application", "toast_position", "top_right")
TOAST_Y_OFFSET = int(get_setting("Application", "toast_y_offset", 80))
TOAST_X_OFFSET = int(get_setting("Application", "toast_x_offset", 0))
COLLECTION_MISSING_COLOR = get_setting("Application", "collection_missing_color", "#00FF00")

TOAST_FONT = None
TOAST_HEADLINE_FONT = None
EXAMPLE_TOAST = None

EXAMPLE_IMAGE_URL = (
    "https://web.poecdn.com/gen/image/"
    "WzI1LDE0LHsiZiI6IjJESXRlbXMvQmVsdHMvQmF0ZWRCcmVhdGgiLCJzY2FsZSI6MX1d/"
    "726ab7c1f0/BatedBreath.png"
)

EXAMPLE_SOURCE_IMAGE = None


def get_toast_font():
    global TOAST_FONT

    if TOAST_FONT is None:
        TOAST_FONT = fonts.make_font(TOAST_FONT_SIZE)

    return TOAST_FONT


def get_toast_headline_font():
    global TOAST_HEADLINE_FONT

    if TOAST_HEADLINE_FONT is None:
        TOAST_HEADLINE_FONT = fonts.make_font(
            size=TOAST_HEADLINE_FONT_SIZE,
            weight="bold"
        )

    return TOAST_HEADLINE_FONT


def reposition(root):
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    position = TOAST_POSITION
    y_offset = TOAST_Y_OFFSET
    x_offset = TOAST_X_OFFSET

    alive = [t for t in TOASTS if t.winfo_exists()]
    TOASTS[:] = alive
    if not TOASTS:
        return

    stack_down = position.startswith("top")
    stack_up = position.startswith("bottom")

    if stack_down:
        y = TOAST_MARGIN + y_offset
    else:
        y = screen_h - TOAST_MARGIN - y_offset

    for t in TOASTS:
        try:
            t.update_idletasks()
            w = t.winfo_reqwidth()
            h = t.winfo_reqheight()

            # X positioning
            if position.endswith("right"):
                x = screen_w - w - TOAST_MARGIN - x_offset
            else:
                x = TOAST_MARGIN + x_offset

            # Y positioning
            if stack_down:
                t.geometry(f"+{x}+{y}")
                y += h + TOAST_SPACING
            else:
                y -= h
                t.geometry(f"+{x}+{y}")
                y -= TOAST_SPACING

        except tk.TclError:
            continue


def get_toast_duration_ms():
    return TOASTS_DURATION * 1000


def create_toast(root, message, image=None, duration=None, is_missing=False, item=None,
                 tree_manager: TreeManager = None, tracker=None, force_show=False, auto_close=True):
    if not ARE_TOASTS_ENABLED and not force_show:
        return None
    if duration is None:
        duration = get_toast_duration_ms()

    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-alpha", 0.98)
    toast.attributes("-topmost", True)
    toast.attributes("-toolwindow", True)

    missing_color = COLLECTION_MISSING_COLOR
    border_color = missing_color if is_missing else "black"
    border_thickness = 4 if is_missing else 0

    frame = tk.Frame(
        toast,
        bg="black",
        padx=TOAST_PADDING,
        pady=TOAST_PADDING,
        highlightbackground=border_color,
        highlightthickness=border_thickness
    )
    frame.pack()

    record_number = getattr(item, "record_number", None)

    # Add image if provided
    if image:
        img_label = tk.Label(frame, image=image, bg="black")
        img_label.image = image
        img_label.pack(side="left", padx=(0, 5))
        toast.img_ref = image

    # Add text
    text_label = tk.Label(frame, text=message, bg="black", font=get_toast_font(), fg="white", anchor="w")
    text_label.pack(side="left")

    if item is not None:
        check_var = ctk.StringVar(value="False")

        def mark_picked():
            item_text = utils.parse_item_name(item)

            if tree_manager is not None:
                tree_manager.data_mgr.modify_record(
                    root,
                    record_number,
                    item_text,
                    updates={"Picked": check_var.get()}
                )
                tree_manager.refresh_treeview(tracker=tracker)

            root.focus_force()
            return

        pickup_checkbox = ctk.CTkCheckBox(
            frame,
            text="",
            width=4,
            border_color=get_border_color(item),
            variable=check_var,
            command=mark_picked,
            onvalue="True",
            offvalue="False"
        )
        pickup_checkbox.pack(side="right", padx=(10, 0))

    toast.lift()
    root.focus_force()

    TOASTS.append(toast)
    reposition(root)

    # Schedule close
    def close_toast():
        if toast in TOASTS:
            TOASTS.remove(toast)
        try:
            toast.destroy()
        except Exception as e:
            log_message(e)
            pass
        reposition(root)

    if auto_close:
        toast.after(duration, close_toast)

    return toast


def show(root, item, message=None, duration=None, tree_manager: TreeManager = None, tracker=None):
    owned = getattr(item, "owned", False)
    type = getattr(item, "type", "")
    record_number = getattr(item, "record_number", None)
    is_missing = False
    if not owned and utils.is_unique(type):
        is_missing = True

    if message is None:
        item_text = utils.parse_item_name(item)
        _, stack_size_txt = currency_utils.get_stack_size(item)
        display_value = currency_utils.calculate_estimate_value(item)
        five_link_value = currency_utils.calculate_five_link_estimate_value(item)
        six_link_value = currency_utils.calculate_six_link_estimate_value(item)
        tier = getattr(item, "tier", "")

        added_owned_txt = "Missing\n" if is_missing else ""
        added_record_number_txt = f"Record: {record_number}\n"
        added_stack_size_txt = f" | Stack Size: {stack_size_txt}" if stack_size_txt else ""
        added_tier_txt = f" | Tier: {tier}" if tier else ""
        added_estimated_value_txt = f"\n Estimated Value: {display_value}" if display_value else ""
        added_5_link_value_txt = f"\n5-L: {five_link_value}" if five_link_value else ""
        added_6_link_value_txt = f" | 6-L: {six_link_value}" if six_link_value else ""

        message = (added_owned_txt + added_record_number_txt + item_text + added_stack_size_txt + added_tier_txt +
                   added_estimated_value_txt + added_5_link_value_txt + added_6_link_value_txt)

    tk_img = render_toast_image(item)

    return create_toast(root, message, image=tk_img, duration=duration, is_missing=is_missing, item=item,
                        tree_manager=tree_manager, tracker=tracker)


def show_message(root, message, duration=None):
    return create_toast(root, message, duration=duration)


@dataclass
class CustomToastOptions:
    is_highlight: bool = False
    border_color: Optional[str] = None
    border_thickness: Optional[int] = None
    show_owned: Optional[bool] = None
    show_stack_size: Optional[bool] = None
    show_tier: Optional[bool] = None
    show_estimated_value: Optional[bool] = None
    custom_message: Optional[str] = None
    headline: Optional[str] = None

def show_custom(root, item, options: CustomToastOptions):
    item_text = utils.parse_item_name(item)
    _, stack_size_txt = currency_utils.get_stack_size(item)
    display_value = currency_utils.calculate_estimate_value(item)
    tier = getattr(item, "tier", "")
    owned = getattr(item, "owned", False)
    type_ = getattr(item, "type", "")
    record_number = getattr(item, "record_number", None)
    five_link_value = currency_utils.calculate_five_link_estimate_value(item)
    six_link_value = currency_utils.calculate_six_link_estimate_value(item)

    is_missing = not owned and utils.is_unique(type_)

    added_owned_txt = "Missing\n" if (options.show_owned if options.show_owned is not None else is_missing) else ""
    added_stack_size_txt = f" | Stack Size: {stack_size_txt}" if (
        options.show_stack_size if options.show_stack_size is not None else bool(stack_size_txt)) else ""
    added_tier_txt = f" | Tier: {tier}" if (options.show_tier if options.show_tier is not None else bool(tier)) else ""
    added_estimated_value_txt = f"\nEstimated Value: {display_value}" if (
        options.show_estimated_value if options.show_estimated_value is not None else bool(display_value)) else ""
    added_5_link_value_txt = f"\n5-L: {five_link_value}" if five_link_value and (
        options.show_estimated_value if options.show_estimated_value is not None else bool(display_value)) else ""
    added_6_link_value_txt = f" | 6-L: {six_link_value}" if six_link_value and (
        options.show_estimated_value if options.show_estimated_value is not None else bool(display_value)) else ""

    main_message = options.custom_message or (
            added_owned_txt + item_text + added_stack_size_txt + added_tier_txt +
            added_estimated_value_txt + added_5_link_value_txt + added_6_link_value_txt
    )

    tk_img = render_toast_image(item)

    border_color = options.border_color or (
        COLLECTION_MISSING_COLOR if is_missing else "black")
    border_thickness = options.border_thickness or (3 if is_missing else 0)
    if options.is_highlight:
        border_color = options.border_color or "#FFD700"  # gold
        border_thickness = options.border_thickness or 3

    toast = create_toast(root, "", image=tk_img, is_missing=False)
    if toast:
        try:
            frame = toast.winfo_children()[0]
            frame.configure(highlightbackground=border_color, highlightthickness=border_thickness)

            if hasattr(toast, "img_ref"):
                img_label = frame.winfo_children()[0]
            else:
                img_label = tk.Label(frame, image=tk_img, bg="black")
                img_label.image = tk_img
                img_label.pack(side="left")
                toast.img_ref = tk_img

            text_frame = tk.Frame(frame, bg="black", height=ROW_HEIGHT)
            text_frame.pack(side="left", anchor="w")

            if options.headline:
                headline_label = tk.Label(
                    text_frame,
                    text=options.headline,
                    font=get_toast_headline_font(),
                    bg="black",
                    fg="white",
                    anchor="w",
                    justify="center"
                )
                headline_label.pack(side="top", anchor="center")

            text_label = tk.Label(
                text_frame,
                text=main_message,
                font=get_toast_font(),
                bg="black",
                fg="white",
                anchor="w",
                justify="left"
            )
            text_label.pack(side="top", anchor="w")

        except Exception as e:
            log_message(f"[WARN] Failed to apply custom content: {e}")

        reposition(root)
    return toast


@dataclass
class ExampleItemName:
    lines: list


@dataclass
class ExampleToastItem:
    item_name: str = "Bated Breath"
    name: str = "Bated Breath"
    type: str = "Replica"

    itemRarity: str = "Unique"
    itemClass: str = None

    itemName: ExampleItemName = None

    tier: int = 0
    record_number: int = 12345
    owned: bool = False
    duplicate: bool = False

    quality: int = 0
    itemLevel: int = 0
    corrupted: bool = False

    baseStats: list = None
    requirements: list = None
    implicits: list = None
    enchants: list = None
    affixes: list = None
    runes: list = None

    flavorText: dict = None

    stack_size: Optional[int] = None
    stack_size_max: Optional[int] = None

    estimated_value: Optional[float] = None
    estimated_value_chaos: Optional[float] = None
    chaos_value: Optional[float] = None

    icon: str = (
        "https://web.poecdn.com/gen/image/WzI1LDE0LHsiZiI6IjJESXRlbXMvQmVsdHMvQmF0ZWRCcmVhdGgiLCJzY2FsZSI6MX1d/726ab7c1f0/BatedBreath.png"
    )

    def __post_init__(self):
        if self.itemName is None:
            self.itemName = ExampleItemName(
                lines=["Replica Bated Breath"]
            )

        if self.baseStats is None:
            self.baseStats = []

        if self.requirements is None:
            self.requirements = []

        if self.implicits is None:
            self.implicits = []

        if self.enchants is None:
            self.enchants = []

        if self.affixes is None:
            self.affixes = []

        if self.runes is None:
            self.runes = []

        if self.flavorText is None:
            self.flavorText = {
                "lines": []
            }

def show_example(root):
    global EXAMPLE_TOAST

    if EXAMPLE_TOAST is not None:
        try:
            if EXAMPLE_TOAST.winfo_exists():
                return EXAMPLE_TOAST
        except tk.TclError:
            pass

        EXAMPLE_TOAST = None

    item = ExampleToastItem()

    message = (
        "EXAMPLE TOAST PREVIEW | Missing\n"
        "Record: 12345\n"
        "Replica Bated Breath | Tier: 0\n"
        "Estimated Value: 100 Divines"
    )

    tk_img = render_toast_image(item)

    EXAMPLE_TOAST = create_toast(
        root,
        message,
        image=tk_img,
        is_missing=True,
        force_show=True,
        auto_close=False
    )

    return EXAMPLE_TOAST


def render_toast_image(item):
    img = render_item(item)

    img = img.resize(
        (
            max(1, IMAGE_COL_WIDTH - 4),
            max(1, ROW_HEIGHT)
        )
    )

    return ImageTk.PhotoImage(img)


def hide_example():
    global EXAMPLE_TOAST

    if EXAMPLE_TOAST is None:
        return

    if EXAMPLE_TOAST in TOASTS:
        TOASTS.remove(EXAMPLE_TOAST)

    try:
        EXAMPLE_TOAST.destroy()
    except tk.TclError:
        pass

    EXAMPLE_TOAST = None


def get_example_image():
    global EXAMPLE_SOURCE_IMAGE

    try:
        if EXAMPLE_SOURCE_IMAGE is None:
            with urllib.request.urlopen(EXAMPLE_IMAGE_URL, timeout=5) as response:
                image_data = response.read()

            EXAMPLE_SOURCE_IMAGE = Image.open(
                BytesIO(image_data)
            ).convert("RGBA")

        resized = EXAMPLE_SOURCE_IMAGE.resize(
            (
                max(1, IMAGE_COL_WIDTH - 4),
                max(1, ROW_HEIGHT)
            ),
            Image.Resampling.LANCZOS
        )

        return ImageTk.PhotoImage(resized)

    except Exception as e:
        log_message(f"[WARN] Failed to load example toast image: {e}")
        return None


def toggle_example(root):
    global EXAMPLE_TOAST

    if EXAMPLE_TOAST is not None:
        try:
            if EXAMPLE_TOAST.winfo_exists():
                hide_example()
                reposition(root)
                return False
        except tk.TclError:
            EXAMPLE_TOAST = None

    show_example(root)
    reposition(root)
    return True


def toggle_toasts(enabled: bool):
    global ARE_TOASTS_ENABLED
    ARE_TOASTS_ENABLED = enabled
    set_setting('Application', 'are_toasts_enabled', enabled)
    log_message(f"Toasts enabled: {enabled}")


def refresh_example(root):
    global EXAMPLE_TOAST

    if EXAMPLE_TOAST is None:
        return

    try:
        if not EXAMPLE_TOAST.winfo_exists():
            EXAMPLE_TOAST = None
            return
    except tk.TclError:
        EXAMPLE_TOAST = None
        return

    hide_example()
    show_example(root)
    reposition(root)


def set_toast_image_width(width: int, root=None):
    global IMAGE_COL_WIDTH

    IMAGE_COL_WIDTH = int(width)
    set_setting("Application", "toast_image_width", IMAGE_COL_WIDTH)

    if root is not None:
        refresh_example(root)

    log_message(f"Toast image width set to: {IMAGE_COL_WIDTH}px")


def set_toast_row_height(height: int, root=None):
    global ROW_HEIGHT

    ROW_HEIGHT = int(height)
    set_setting("Application", "toast_row_height", ROW_HEIGHT)

    if root is not None:
        refresh_example(root)

    log_message(f"Toast row height set to: {ROW_HEIGHT}px")


def set_toast_font_size(size: int, root=None):
    global TOAST_FONT_SIZE, TOAST_FONT

    TOAST_FONT_SIZE = int(size)
    TOAST_FONT = None

    set_setting("Application", "toast_font_size", TOAST_FONT_SIZE)

    if root is not None:
        refresh_example(root)

    log_message(f"Toast font size set to: {TOAST_FONT_SIZE}")


def set_toast_headline_font_size(size: int, root=None):
    global TOAST_HEADLINE_FONT_SIZE, TOAST_HEADLINE_FONT

    TOAST_HEADLINE_FONT_SIZE = int(size)
    TOAST_HEADLINE_FONT = None

    set_setting(
        "Application",
        "toast_headline_font_size",
        TOAST_HEADLINE_FONT_SIZE
    )

    if root is not None:
        refresh_example(root)

    log_message(
        f"Toast headline font size set to: {TOAST_HEADLINE_FONT_SIZE}"
    )


def set_toast_duration(seconds: int):
    global TOASTS_DURATION
    TOASTS_DURATION = seconds
    set_setting('Application', 'toasts_duration_seconds', seconds)
    log_message(f"Toast duration set to: {seconds}s")


def set_toast_position(position: str, root=None):
    global TOAST_POSITION
    TOAST_POSITION = position
    set_setting("Application", "toast_position", position)

    if root is not None:
        reposition(root)

    log_message(f"Toast position set to: {position}")


def set_toast_y_offset(offset: int, root=None):
    global TOAST_Y_OFFSET
    TOAST_Y_OFFSET = int(offset)
    set_setting("Application", "toast_y_offset", TOAST_Y_OFFSET)

    if root is not None:
        reposition(root)

    log_message(f"Toast Y offset set to: {TOAST_Y_OFFSET}px")


def set_toast_x_offset(offset: int, root=None):
    global TOAST_X_OFFSET
    TOAST_X_OFFSET = int(offset)
    set_setting("Application", "toast_x_offset", TOAST_X_OFFSET)

    if root is not None:
        reposition(root)

    log_message(f"Toast X offset set to: {TOAST_X_OFFSET}px")


def set_collection_missing_color(color: str):
    global COLLECTION_MISSING_COLOR
    COLLECTION_MISSING_COLOR = color
    set_setting("Application", "collection_missing_color", color)

    if EXAMPLE_TOAST is not None:
        try:
            if EXAMPLE_TOAST.winfo_exists():
                frame = EXAMPLE_TOAST.winfo_children()[0]
                frame.configure(highlightbackground=color)
        except (tk.TclError, IndexError):
            pass

    log_message(f"Collection missing color set to: {color}")
