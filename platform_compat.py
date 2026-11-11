import os
import sys

IS_WINDOWS = sys.platform == "win32"


def grab_screen(bbox=None):
    from PIL import Image, ImageGrab

    if IS_WINDOWS or sys.platform == "darwin":
        return ImageGrab.grab(bbox=bbox)

    import mss

    with mss.mss() as sct:
        monitor = (
            {"left": bbox[0], "top": bbox[1], "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]}
            if bbox else sct.monitors[0]
        )
        shot = sct.grab(monitor)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def get_monitors():
    """Return monitors as a list of dicts: left, top, width, height, primary.

    The primary monitor is listed first. Returns an empty list if detection fails.
    """
    monitors = []

    try:
        if IS_WINDOWS:
            import win32api

            for handle, _dc, _rect in win32api.EnumDisplayMonitors():
                info = win32api.GetMonitorInfo(handle)
                left, top, right, bottom = info["Monitor"]
                monitors.append({
                    "left": left, "top": top,
                    "width": right - left, "height": bottom - top,
                    "primary": bool(info.get("Flags", 0) & 1),
                })
        else:
            import mss

            with mss.mss() as sct:
                for i, m in enumerate(sct.monitors[1:]):
                    monitors.append({
                        "left": m["left"], "top": m["top"],
                        "width": m["width"], "height": m["height"],
                        "primary": i == 0,
                    })
    except Exception:
        return []

    monitors.sort(key=lambda m: (not m["primary"], m["left"], m["top"]))
    return monitors


def grab_clipboard_image():
    from PIL import ImageGrab

    if IS_WINDOWS or sys.platform == "darwin":
        return ImageGrab.grabclipboard()

    return None


def get_frozen_product_version(exe_path):
    if not IS_WINDOWS:
        return None

    try:
        import win32api

        info = win32api.GetFileVersionInfo(exe_path, "\\")
        lang, codepage = win32api.GetFileVersionInfo(exe_path, "\\VarFileInfo\\Translation")[0]
        str_info_path = f"\\StringFileInfo\\{lang:04X}{codepage:04X}\\ProductVersion"
        return win32api.GetFileVersionInfo(exe_path, str_info_path)
    except Exception:
        return None


def get_app_data_dir(app_name):
    if IS_WINDOWS:
        return os.path.join(os.getenv("APPDATA"), app_name)

    xdg_data_home = os.getenv("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(xdg_data_home, app_name)


def patch_ctk_transparent_color():
    if IS_WINDOWS or sys.platform == "darwin":
        return

    from customtkinter.windows.widgets.core_rendering.ctk_canvas import CTkCanvas

    original_itemconfig = CTkCanvas.itemconfig

    def itemconfig(self, tag_or_id, *args, **kwargs):
        for key in ("fill", "outline"):
            if kwargs.get(key) == "transparent":
                kwargs[key] = self.cget("bg")
        return original_itemconfig(self, tag_or_id, *args, **kwargs)

    CTkCanvas.itemconfig = itemconfig
