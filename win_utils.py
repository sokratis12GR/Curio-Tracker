try:
    # pygetwindow raises NotImplementedError at import time on Linux, so the
    # import itself must be guarded, not just calls into it.
    import pygetwindow as gw
except Exception:
    gw = None

import config as c
import platform_compat
from logger import log_message


def get_poe_bbox():
    if gw is not None:
        windows = [w for w in gw.getWindowsWithTitle(c.target_application) if w.visible]
        if not windows:
            log_message(c.not_found_target_txt)
            return None
        win = windows[0]
        return win.left, win.top, win.left + win.width, win.top + win.height

    if not platform_compat.IS_WINDOWS:
        return _get_poe_bbox_linux(c.target_application)

    log_message(c.not_found_target_txt)
    return None


def _get_poe_bbox_linux(title):
    # X11/XWayland window lookup via python-xlib
    try:
        from Xlib import display
    except ImportError:
        log_message(c.not_found_target_txt)
        return None

    try:
        d = display.Display()
        root = d.screen().root
        client_list = root.get_full_property(d.intern_atom('_NET_CLIENT_LIST'), 0)
        if client_list is None:
            log_message(c.not_found_target_txt)
            return None

        for window_id in client_list.value:
            window = d.create_resource_object('window', window_id)
            try:
                name = window.get_wm_name()
            except Exception:
                name = None
            if not name or title not in str(name):
                continue

            geom = window.get_geometry()
            coords = window.translate_coords(root, 0, 0)
            return coords.x, coords.y, coords.x + geom.width, coords.y + geom.height

        log_message(c.not_found_target_txt)
        return None
    except Exception as e:
        log_message(f"[ERROR] Linux window lookup failed (requires X11/XWayland): {e}")
        return None


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
