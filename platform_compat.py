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
