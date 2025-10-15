import tkinter as tk

from PIL import ImageTk

import ocr_utils as utils
from logger import log_message
from renderer import render_item
from settings import get_setting, set_setting

IMAGE_COL_WIDTH = 200
ROW_HEIGHT = 40
TOASTS = []
TOAST_MARGIN, TOAST_SPACING, TOAST_PADDING = 10, 6, 4
TOASTS_DURATION = get_setting('Application', 'toasts_duration_seconds', 5)
ARE_TOASTS_ENABLED = get_setting('Application', 'are_toasts_enabled', True)


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


def create_toast(root, message, image=None, duration=None, is_missing=False):
    if not ARE_TOASTS_ENABLED:
        return None
    duration = duration or get_toast_duration_ms()

    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-alpha", 0.98)
    toast.attributes("-topmost", True)
    toast.attributes("-toolwindow", True)

    # Add green border if item is owned
    border_color = "green" if is_missing else "black"
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

    # Add image if provided
    if image:
        img_label = tk.Label(frame, image=image, bg="black")
        img_label.image = image
        img_label.pack(side="left", padx=(0, 8))
        toast.img_ref = image

    # Add text
    text_label = tk.Label(frame, text=message, bg="black", fg="white", anchor="w")
    text_label.pack(side="left")

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
    is_missing = False
    if not owned and utils.is_unique(type):
        is_missing = True

    if message is None:
        item_text = utils.parse_item_name(item)
        _, stack_size_txt = utils.get_stack_size(item)
        display_value = utils.calculate_estimate_value(item)
        tier = getattr(item, "tier", "")

        added_owned_txt = "Missing\n" if is_missing else ""
        added_stack_size_txt = f" | Stack Size: {stack_size_txt}" if stack_size_txt else ""
        added_tier_txt = f" | Tier: {tier}" if tier else ""
        added_estimated_value_txt = f"\n Estimated Value: {display_value}" if display_value else ""

        message = added_owned_txt + item_text + added_stack_size_txt + added_tier_txt + added_estimated_value_txt

    img = render_item(item).resize((IMAGE_COL_WIDTH - 4, ROW_HEIGHT))
    tk_img = ImageTk.PhotoImage(img)

    return create_toast(root, message, image=tk_img, duration=duration, is_missing=is_missing)



def show_message(root, message, duration=None):
    return create_toast(root, message, duration=duration)


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
