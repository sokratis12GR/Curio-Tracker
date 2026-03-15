import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

import customtkinter as ctk
import requests

from fonts import make_font
from version_utils import VERSION


def version_tuple(v: str):
    return tuple(int(x) for x in v.strip("v").split("."))


def check_for_updates(root, show_uptodate_popup=False, blocking=False):
    def worker():
        try:
            url = "https://api.github.com/repos/sokratis12GR/Curio-Tracker/releases/latest"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            latest = data.get("tag_name", "").strip()

            if not latest:
                return

            if version_tuple(latest) > version_tuple(VERSION):
                root.after(0, lambda: show_update_popup(
                    root,
                    latest,
                    data.get("html_url", "")
                ))
            else:
                if show_uptodate_popup:
                    root.after(0, lambda: show_up_to_date_popup(root, latest))

        except Exception:
            if show_uptodate_popup:
                root.after(0, lambda: show_up_to_date_popup(root, None, error=True))

    if blocking:
        worker()   # run immediately (no thread)
    else:
        threading.Thread(target=worker, daemon=True).start()


def show_up_to_date_popup(root, latest_version=None, error=False):
    popup = ctk.CTkToplevel(root)
    popup.title("Update Check")
    popup.resizable(False, False)
    popup.transient(root)
    popup.grab_set()
    popup.focus_force()

    frame = ctk.CTkFrame(popup)
    frame.pack(padx=20, pady=20)

    if error:
        text = "Failed to check for updates."
    else:
        text = f"You are up to date!\n\nCurrent version: {VERSION}"

    ctk.CTkLabel(
        frame,
        text=text,
        font=make_font(12),
        justify="center"
    ).pack(pady=(0, 15))

    ctk.CTkButton(
        frame,
        text="OK",
        command=popup.destroy,
        width=120
    ).pack()

    popup.update_idletasks()
    w, h = popup.winfo_width(), popup.winfo_height()
    x = (popup.winfo_screenwidth() // 2) - (w // 2)
    y = (popup.winfo_screenheight() // 2) - (h // 2)
    popup.geometry(f"{w}x{h}+{x}+{y}")

def deploy_updater():
    from load_utils import get_resource_path

    source = get_resource_path("updater.exe")
    app_dir = Path(sys.executable).parent
    target = app_dir / "updater.exe"

    shutil.copy2(source, target)

    return target


def show_update_popup(root, latest_version, release_url):
    popup = ctk.CTkToplevel(root)
    popup.title("Update Available")
    popup.resizable(False, False)
    popup.transient(root)
    popup.minsize(280, 240)
    popup.grab_set()
    popup.focus_force()
    print("Showing update popup for version:", latest_version)

    frm = ctk.CTkFrame(popup)
    frm.pack(padx=20, pady=20, fill="both", expand=True)

    ctk.CTkLabel(frm, text="Update Available", font=make_font(14, "bold")).pack(pady=(0, 5))
    ctk.CTkLabel(frm, text=f"Your version: {VERSION}", font=make_font(11)).pack()
    ctk.CTkLabel(frm, text=f"Latest version: {latest_version}", font=make_font(11, "bold")).pack(pady=(0, 10))

    def update_now():
        try:
            updater_path = deploy_updater()
            subprocess.Popen([str(updater_path)])
            root.destroy()
            sys.exit(0)
        except Exception as e:
            print(f"Failed to launch updater: {e}")

    ctk.CTkButton(
        frm,
        text="Update Now",
        command=update_now,
        width=180,
    ).pack(pady=(5, 5))

    def open_github():
        webbrowser.open_new(release_url)

    try:
        import load_utils
        from PIL import Image

        icon_path = load_utils.get_resource_path("assets/github-icon.png")
        img = Image.open(icon_path).resize((18, 18))
        github_img = ctk.CTkImage(light_image=img, dark_image=img)

        ctk.CTkButton(
            frm,
            image=github_img,
            text="Download from GitHub",
            compound="left",
            command=open_github,
            width=180,
        ).pack(pady=(0, 5))

    except Exception:
        ctk.CTkButton(
            frm,
            text="Download from GitHub",
            command=open_github,
            width=180,
        ).pack(pady=(0, 5))

    ctk.CTkButton(
        frm,
        text="Later",
        command=popup.destroy,
        width=120,
    ).pack(pady=(10, 0))

    popup.update_idletasks()
    w, h = popup.winfo_width(), popup.winfo_height()
    x = (popup.winfo_screenwidth() // 2) - (w // 2)
    y = (popup.winfo_screenheight() // 2) - (h // 2)
    popup.geometry(f"{w}x{h}+{x}+{y}")

    popup.wait_window()
