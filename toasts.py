import tkinter as tk
from PIL import ImageTk
from renderer import render_item
import ocr_utils as utils

IMAGE_COL_WIDTH = 200
ROW_HEIGHT = 40
TOASTS = []
TOAST_MARGIN, TOAST_SPACING, TOAST_PADDING = 10, 6, 4

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


def show(root, item, message=None, duration=5000):
    img = render_item(item)
    img = img.resize((IMAGE_COL_WIDTH - 4, ROW_HEIGHT))
    tk_img = ImageTk.PhotoImage(img)

    toast = tk.Toplevel(root)
    toast.overrideredirect(True)       
    toast.attributes("-alpha", 0.98)   
    toast.attributes("-topmost", True) 
    toast.attributes("-toolwindow", True)   

    frame = tk.Frame(toast, bg="black", padx=TOAST_PADDING, pady=TOAST_PADDING)
    frame.pack()

    img_label = tk.Label(frame, image=tk_img, bg="black")
    img_label.image = tk_img
    img_label.pack(side="left", padx=(0, 8))
    
    toast.img_ref = tk_img

    if getattr(item, "enchants", None) and len(item.enchants) > 0:
        item_text = "\n".join([str(e) for e in item.enchants])
    else:
        item_text = getattr(item, "itemName", "New Item")
        if hasattr(item_text, "lines"):
            item_text = "\n".join([str(line) for line in item_text.lines])
    stack_size = getattr(item, "stack_size", "")
    item_type = getattr(item, "type", "N/A")
    try:
        stack_size = int(stack_size)
    except (ValueError, TypeError):
        stack_size = 1
    stack_size_txt = (
            stack_size
            if int(stack_size) > 0 and utils.is_currency_or_scarab(item_type)
            else ""
        )
    msg = message or item_text + (" | Stack Size: " + str(stack_size_txt) if str(stack_size_txt) != "" else "")
    text_label = tk.Label(frame, text=msg, bg="black", fg="white", anchor="w")
    text_label.pack(side="left")

    toast.lift()
    root.focus_force() 

    TOASTS.append(toast)
    reposition(root)

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

def show_message(root, message, duration=5000):
    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-alpha", 0.98)
    toast.attributes("-topmost", True)
    toast.attributes("-toolwindow", True)

    frame = tk.Frame(toast, bg="black", padx=TOAST_PADDING, pady=TOAST_PADDING)
    frame.pack()

    text_label = tk.Label(frame, text=message, bg="black", fg="white", anchor="w")
    text_label.pack(side="left")

    toast.lift()
    root.focus_force()

    TOASTS.append(toast)
    reposition(root)

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
