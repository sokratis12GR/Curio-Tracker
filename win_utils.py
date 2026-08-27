import pygetwindow as gw

import config as c
from logger import log_message


def get_poe_bbox():
    windows = [w for w in gw.getWindowsWithTitle(c.target_application) if w.visible]
    if not windows:
        log_message(c.not_found_target_txt)
        return None
    win = windows[0]
    return win.left, win.top, win.left + win.width, win.top + win.height


def center_window_on_parent(window, parent):
    window.update_idletasks()

    parent = parent.winfo_toplevel()
    parent.update_idletasks()

    x = (
            parent.winfo_x()
            + (parent.winfo_width() // 2)
            - (window.winfo_width() // 2)
    )

    y = (
            parent.winfo_y()
            + (parent.winfo_height() // 2)
            - (window.winfo_height() // 2)
    )

    window.geometry(f"+{x}+{y}")
