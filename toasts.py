import tkinter as tk
import customtkinter as ctk
from dataclasses import dataclass
from typing import Optional

from PIL import ImageTk

import currency_utils
import fonts
import ocr_utils as utils
from csv_manager import CSVManager
from logger import log_message
from renderer import render_item
from settings import get_setting, set_setting

IMAGE_COL_WIDTH = 200
ROW_HEIGHT = 40
TOASTS = []
TOAST_MARGIN, TOAST_SPACING, TOAST_PADDING = 10, 6, 4
TOASTS_DURATION = get_setting('Application', 'toasts_duration_seconds', 5)
ARE_TOASTS_ENABLED = get_setting('Application', 'are_toasts_enabled', True)
csv_manager = CSVManager()


def reposition(root):
    screen_w = root.winfo_screenwidth()
    x_right = screen_w - TOAST_MARGIN
    y = TOAST_MARGIN

    # filter out any destroyed toasts
    alive = []
    for t in TOASTS:
        if t.winfo_exists():
            alive.append(t)

    TOASTS[:] = alive  # replace with only valid windows

    for t in TOASTS:
        try:
            t.update_idletasks()
            w = t.winfo_reqwidth()
            h = t.winfo_reqheight()
            t.geometry(f"+{x_right - w}+{y}")
            y += h + TOAST_SPACING
        except tk.TclError:
            # window disappeared between check and move
            continue


def get_toast_duration_ms():
    return TOASTS_DURATION * 1000


def create_toast(root, message, image=None, duration=None, is_missing=False, item=None):
    if not ARE_TOASTS_ENABLED:
        return None
    duration = duration or get_toast_duration_ms()

    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-alpha", 0.98)
    toast.attributes("-topmost", True)
    toast.attributes("-toolwindow", True)

    missing_color = get_setting("Application", "collection_missing_color", "#00FF00")
    border_color = missing_color if is_missing else "black"
    border_thickness = 3 if is_missing else 0

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
        img_label.pack(side="left", padx=(0, 8))
        toast.img_ref = image

    # Add text
    text_label = tk.Label(frame, text=message, bg="black", fg="white", anchor="w")
    text_label.pack(side="left")

    def mark_picked(val=True):
        picked = getattr(item, "picked", False)
        item_text = utils.parse_item_name(item)
        csv_manager.modify_record(root, record_number, item_text, updates={"Picked": not picked})
        root.focus_force()
        return

    if item is not None:
        pickup_checkbox = ctk.CTkCheckBox(frame, text="", width=5, command=mark_picked)
        pickup_checkbox.pack(side="right")

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

    toast.after(duration, close_toast)
    return toast


def show(root, item, message=None, duration=None):
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

    img = render_item(item).resize((IMAGE_COL_WIDTH - 4, ROW_HEIGHT))
    tk_img = ImageTk.PhotoImage(img)

    return create_toast(root, message, image=tk_img, duration=duration, is_missing=is_missing, item=item)


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

    img = render_item(item).resize((IMAGE_COL_WIDTH - 4, ROW_HEIGHT))
    tk_img = ImageTk.PhotoImage(img)

    border_color = options.border_color or (
        get_setting("Application", "collection_missing_color", "#00FF00") if is_missing else "black")
    border_thickness = options.border_thickness or (3 if is_missing else 0)
    if options.is_highlight:
        border_color = options.border_color or "#FFD700"  # gold
        border_thickness = options.border_thickness or 4

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
                    font=fonts.make_font(size=12, weight="bold"),
                    bg="black",
                    fg="white",
                    anchor="w",
                    justify="center"
                )
                headline_label.pack(side="top", anchor="center")

            text_label = tk.Label(
                text_frame,
                text=main_message,
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


def toggle_toasts(enabled: bool):
    global ARE_TOASTS_ENABLED
    ARE_TOASTS_ENABLED = enabled
    set_setting('Application', 'are_toasts_enabled', enabled)
    log_message(f"Toasts enabled: {enabled}")


def set_toast_duration(seconds: int):
    global TOASTS_DURATION
    TOASTS_DURATION = seconds
    set_setting('Application', 'toasts_duration_seconds', seconds)
    log_message(f"Toast duration set to: {seconds}s")
