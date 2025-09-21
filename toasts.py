import tkinter as tk
from PIL import ImageTk
from renderer import render_item
import ocr_utils as utils

IMAGE_COL_WIDTH = 200
ROW_HEIGHT = 40
TOASTS = []
TOAST_MARGIN, TOAST_SPACING, TOAST_PADDING = 10, 6, 4
TOASTS_DURATION = 5

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


def create_toast(root, message, image=None, duration=None):
    duration = duration or get_toast_duration_ms()

    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-alpha", 0.98)
    toast.attributes("-topmost", True)
    toast.attributes("-toolwindow", True)

    frame = tk.Frame(toast, bg="black", padx=TOAST_PADDING, pady=TOAST_PADDING)
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
        except Exception:
            pass
        reposition(root)

    toast.after(duration, close_toast)
    return toast


def show(root, item, message=None, duration=None):
    if message is None:
        # Build default message from item
        if getattr(item, "enchants", None) and len(item.enchants) > 0:
            item_text = "\n".join(str(e) for e in item.enchants)
        else:
            item_text = getattr(item, "itemName", "New Item")
            if hasattr(item_text, "lines"):
                item_text = "\n".join(str(line) for line in item_text.lines)

        _, stack_size_txt = utils.get_stack_size(item)
        display_value = utils.calculate_estimate_value(item)
        tier = getattr(item, "tier", "")

        added_stack_size_txt = f" | Stack Size: {stack_size_txt}" if stack_size_txt else ""
        added_tier_txt = f" | Tier: {tier}" if tier else ""
        added_estimated_value_txt = f"\n Estimated Value: {display_value}" if display_value else ""

        message = item_text + added_stack_size_txt + added_tier_txt + added_estimated_value_txt

    img = render_item(item).resize((IMAGE_COL_WIDTH - 4, ROW_HEIGHT))
    tk_img = ImageTk.PhotoImage(img)

    return create_toast(root, message, image=tk_img, duration=duration)


def show_message(root, message, duration=None):
    return create_toast(root, message, duration=duration)
