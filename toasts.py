import time
import tkinter as tk
from dataclasses import dataclass
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

import config as c
import currency_utils
import fonts
import ocr_utils as utils
import platform_compat
from logger import log_message
from renderer import render_item, get_border_color
from settings import get_setting, set_setting
from tree_manager import TreeManager


TOASTS = []
TOAST_MARGIN, TOAST_SPACING, TOAST_PADDING = 10, 6, 4
TOAST_ALPHA = 0.98
FADE_STEPS, FADE_STEP_MS = 10, 25
TOASTS_DURATION = max(
    c.TOAST_DURATION_MIN,
    int(get_setting('Application', 'toasts_duration_seconds', c.DEFAULT_TOAST_DURATION)),
)
ARE_TOASTS_ENABLED = get_setting('Application', 'are_toasts_enabled', True)
TOAST_POSITION = get_setting("Application", "toast_position", "top_right")
TOAST_Y_OFFSET = int(get_setting("Application", "toast_y_offset", 80))
TOAST_X_OFFSET = int(get_setting("Application", "toast_x_offset", 0))
IMAGE_COL_WIDTH = int(get_setting("Application", "toast_image_width", 200))
TOAST_IMAGE_HEIGHT = int(get_setting("Application", "toast_image_height", 40))
TOAST_FONT_SIZE = int(get_setting("Application", "toast_font_size", 11))
TOAST_HEADLINE_FONT_SIZE = int(get_setting("Application", "toast_headline_font_size", 10))
COLLECTION_MISSING_COLOR = get_setting("Application", "collection_missing_color", "#00FF00")
TOAST_FADE_OUT = bool(get_setting("Application", "toast_fade_out", c.DEFAULT_TOAST_FADE_OUT))
TOAST_MONITOR = str(get_setting("Application", "toast_monitor", c.DEFAULT_TOAST_MONITOR))

TOAST_FONT = None
TOAST_HEADLINE_FONT = None
EXAMPLE_TOAST = None


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


def get_monitor_choices():
    """Values for the settings Monitor dropdown."""
    names = ["Primary"]
    for i, m in enumerate(platform_compat.get_monitors(), start=1):
        suffix = " (Primary)" if m["primary"] else ""
        names.append(f"Monitor {i}: {m['width']}x{m['height']}{suffix}")
    return names


def get_target_monitor(root):
    """(left, top, width, height) of the monitor toasts should appear on."""
    monitors = platform_compat.get_monitors()

    if TOAST_MONITOR.startswith("Monitor "):
        try:
            index = int(TOAST_MONITOR.split()[1].rstrip(":")) - 1
            m = monitors[index]
            return m["left"], m["top"], m["width"], m["height"]
        except (ValueError, IndexError):
            pass  # Monitor unplugged or invalid setting: fall back to primary.

    if monitors:
        m = monitors[0]
        return m["left"], m["top"], m["width"], m["height"]

    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def reposition(root):
    alive = [t for t in TOASTS if t.winfo_exists()]
    TOASTS[:] = alive
    if not TOASTS:
        return

    mon_x, mon_y, screen_w, screen_h = get_target_monitor(root)

    position = TOAST_POSITION
    y_offset = TOAST_Y_OFFSET
    x_offset = TOAST_X_OFFSET

    stack_down = position.startswith("top")

    if stack_down:
        y = mon_y + TOAST_MARGIN + y_offset
    else:
        y = mon_y + screen_h - TOAST_MARGIN - y_offset

    for t in TOASTS:
        try:
            t.update_idletasks()
            w = t.winfo_reqwidth()
            h = t.winfo_reqheight()

            # X positioning
            if position.endswith("right"):
                x = mon_x + screen_w - w - TOAST_MARGIN - x_offset
            else:
                x = mon_x + TOAST_MARGIN + x_offset

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


def create_toast(
    root,
    message,
    image=None,
    duration=None,
    is_missing=False,
    item=None,
    tree_manager: TreeManager = None,
    tracker=None,
    force_show=False,
    auto_close=True,
    headline=None,
    border_color=None,
    border_thickness=None,
):
    if not ARE_TOASTS_ENABLED and not force_show:
        return None

    if duration is None:
        duration = get_toast_duration_ms()

    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-alpha", TOAST_ALPHA)
    toast.attributes("-topmost", True)
    toast.attributes("-toolwindow", True)

    bg, fg = "black", "white"

    if border_color is None:
        border_color = COLLECTION_MISSING_COLOR if is_missing else "black"
    if border_thickness is None:
        border_thickness = 4 if is_missing else 0

    frame = tk.Frame(
        toast,
        bg=bg,
        padx=TOAST_PADDING,
        pady=TOAST_PADDING,
        highlightbackground=border_color,
        highlightthickness=border_thickness,
    )
    frame.pack()

    if image:
        img_label = tk.Label(frame, image=image, bg=bg)
        img_label.image = image
        img_label.pack(side="left", padx=(0, 5))
        toast.img_ref = image

    text_frame = tk.Frame(frame, bg=bg)
    text_frame.pack(side="left", anchor="center")

    if headline:
        headline_label = tk.Label(
            text_frame,
            text=headline,
            bg=bg,
            fg=fg,
            font=get_toast_headline_font(),
            anchor="center",
            justify="center",
        )
        headline_label.pack(side="top", anchor="center")

    text_label = tk.Label(
        text_frame,
        text=message,
        bg=bg,
        font=get_toast_font(),
        fg=fg,
        anchor="center",
        justify="center",
    )
    text_label.pack(side="top", anchor="center")

    if item is not None:
        check_var = ctk.StringVar(value="False")

        def mark_picked():
            item_text = utils.parse_item_name(item)

            if tree_manager is not None:
                # Read at click time: deletes can shift record numbers
                # while the toast is open.
                tree_manager.data_mgr.modify_record(
                    root,
                    getattr(item, "record_number", None),
                    item_text,
                    updates={"Picked": check_var.get()},
                )
                tree_manager.refresh_treeview(tracker=tracker)

        pickup_checkbox = ctk.CTkCheckBox(
            frame,
            text="",
            width=4,
            border_color=get_border_color(item),
            variable=check_var,
            command=mark_picked,
            onvalue="True",
            offvalue="False",
        )
        pickup_checkbox.pack(side="right", padx=(10, 0))

    toast.lift()

    # Track the countdown so hovering can pause it.
    state = {"after_id": None, "remaining": duration, "started": 0.0, "closing": False}

    def destroy_now():
        if toast in TOASTS:
            TOASTS.remove(toast)

        try:
            toast.destroy()
        except tk.TclError as e:
            log_message(e)

        reposition(root)

    def fade_out(step=FADE_STEPS):
        try:
            if step <= 0:
                destroy_now()
                return
            toast.attributes("-alpha", TOAST_ALPHA * step / FADE_STEPS)
            toast.after(FADE_STEP_MS, fade_out, step - 1)
        except tk.TclError:
            destroy_now()

    def close_toast(immediate=False):
        if state["closing"]:
            return
        state["closing"] = True
        cancel_timer()
        if immediate or not TOAST_FADE_OUT:
            destroy_now()
        else:
            fade_out()

    def start_timer():
        if not auto_close or state["closing"]:
            return
        state["started"] = time.monotonic()
        state["after_id"] = toast.after(max(0, int(state["remaining"])), close_toast)

    def cancel_timer():
        if state["after_id"] is not None:
            try:
                toast.after_cancel(state["after_id"])
            except tk.TclError:
                pass
            state["after_id"] = None

    def pointer_inside():
        try:
            px, py = toast.winfo_pointerxy()
            x, y = toast.winfo_rootx(), toast.winfo_rooty()
            return x <= px < x + toast.winfo_width() and y <= py < y + toast.winfo_height()
        except tk.TclError:
            return False

    def on_enter(_event=None):
        if state["after_id"] is None:
            return
        elapsed_ms = (time.monotonic() - state["started"]) * 1000
        state["remaining"] = max(0, state["remaining"] - elapsed_ms)
        cancel_timer()

    def on_leave(_event=None):
        # <Leave> also fires when moving between child widgets; only resume
        # once the pointer has actually left the toast.
        if state["after_id"] is None and not pointer_inside():
            # Give the user a moment after moving away.
            state["remaining"] = max(state["remaining"], 1000)
            start_timer()

    toast.bind("<Enter>", on_enter)
    toast.bind("<Leave>", on_leave)
    if auto_close:
        # The example preview is controlled from settings, so it isn't dismissable here.
        toast.bind("<Button-3>", lambda _e: close_toast())

    toast.close_toast = close_toast

    TOASTS.append(toast)
    enforce_toast_limit()
    reposition(root)
    start_timer()

    return toast


def enforce_toast_limit():
    """Close the oldest auto-closing toasts once the visible cap is exceeded."""
    alive = [t for t in TOASTS if t.winfo_exists() and t is not EXAMPLE_TOAST]
    excess = len(alive) - c.MAX_VISIBLE_TOASTS
    for t in alive[:max(0, excess)]:
        closer = getattr(t, "close_toast", None)
        if closer is not None:
            closer(immediate=True)


def is_item_missing(item):
    owned = getattr(item, "owned", False)
    return not owned and utils.is_unique(getattr(item, "type", ""))


def build_item_message(
    item,
    include_record=False,
    show_owned=None,
    show_stack_size=None,
    show_tier=None,
    show_estimated_value=None,
):
    """Build a toast's text. Each ``show_*`` flag overrides its default when not None."""
    item_text = utils.parse_item_name(item)
    _, stack_size_txt = currency_utils.get_stack_size(item)
    display_value = currency_utils.calculate_estimate_value(item)
    five_link_value = currency_utils.calculate_five_link_estimate_value(item)
    six_link_value = currency_utils.calculate_six_link_estimate_value(item)
    tier = getattr(item, "tier", "")

    def pick(override, default):
        return default if override is None else override

    parts = []

    if pick(show_owned, is_item_missing(item)):
        parts.append("Missing\n")

    if include_record:
        parts.append(f"Record: {getattr(item, 'record_number', None)}\n")

    parts.append(item_text)

    if pick(show_stack_size, bool(stack_size_txt)):
        parts.append(f" | Stack Size: {stack_size_txt}")

    if pick(show_tier, bool(tier)):
        parts.append(f" | Tier: {tier}")

    if pick(show_estimated_value, bool(display_value)):
        if display_value:
            parts.append(f"\nEstimated Value: {display_value}")
        if five_link_value:
            parts.append(f"\n5-L: {five_link_value}")
        if six_link_value:
            parts.append(f" | 6-L: {six_link_value}")

    return "".join(parts)


def show(root, item, message=None, duration=None, tree_manager: TreeManager = None, tracker=None):
    is_missing = is_item_missing(item)

    if message is None:
        message = build_item_message(item, include_record=True)

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
    is_missing = is_item_missing(item)

    main_message = options.custom_message or build_item_message(
        item,
        show_owned=options.show_owned,
        show_stack_size=options.show_stack_size,
        show_tier=options.show_tier,
        show_estimated_value=options.show_estimated_value,
    )

    tk_img = render_toast_image(item)

    border_color = options.border_color or (
        COLLECTION_MISSING_COLOR if is_missing else "black"
    )
    border_thickness = (
        options.border_thickness
        if options.border_thickness is not None
        else (3 if is_missing else 0)
    )

    if options.is_highlight:
        border_color = options.border_color or "#FFD700"
        border_thickness = (
            options.border_thickness
            if options.border_thickness is not None
            else 3
        )

    return create_toast(
        root,
        main_message,
        image=tk_img,
        headline=options.headline,
        border_color=border_color,
        border_thickness=border_thickness,
    )


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
        "Missing\n"
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
        auto_close=False,
        headline="EXAMPLE TOAST PREVIEW - HEADLINE"
    )

    return EXAMPLE_TOAST


def render_toast_image(item):
    img = render_item(item)

    img = img.resize(
        (
            max(1, IMAGE_COL_WIDTH - 4),
            max(1, TOAST_IMAGE_HEIGHT),
        ),
        Image.Resampling.LANCZOS,
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


def set_toast_image_height(height: int, root=None):
    global TOAST_IMAGE_HEIGHT

    TOAST_IMAGE_HEIGHT = int(height)
    set_setting("Application", "toast_image_height", TOAST_IMAGE_HEIGHT)

    if root is not None:
        refresh_example(root)

    log_message(f"Toast image height set to: {TOAST_IMAGE_HEIGHT}px")

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
    set_setting("Application", "toast_headline_font_size", TOAST_HEADLINE_FONT_SIZE)

    if root is not None:
        refresh_example(root)

    log_message(f"Toast headline font size set to: {TOAST_HEADLINE_FONT_SIZE}")


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


def set_toast_fade_out(enabled: bool):
    global TOAST_FADE_OUT
    TOAST_FADE_OUT = bool(enabled)
    set_setting("Application", "toast_fade_out", TOAST_FADE_OUT)
    log_message(f"Toast fade-out enabled: {TOAST_FADE_OUT}")


def set_toast_monitor(monitor: str, root=None):
    global TOAST_MONITOR
    TOAST_MONITOR = str(monitor)
    set_setting("Application", "toast_monitor", TOAST_MONITOR)

    if root is not None:
        reposition(root)

    log_message(f"Toast monitor set to: {TOAST_MONITOR}")


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
