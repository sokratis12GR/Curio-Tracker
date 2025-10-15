import webbrowser

import customtkinter as ctk
import requests
from PIL import Image

from gui.ctksimplebox import CTkMessageBox
from version_utils import VERSION


def version_tuple(v: str):
    return tuple(int(x) for x in v.strip("v").split("."))


def check_for_updates(root, theme_manager):
    msgbox = CTkMessageBox(root, min_size=(300, 20), max_size=(300, 100))
    try:
        url = "https://api.github.com/repos/sokratis12GR/Curio-Tracker/releases/latest"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        latest = data.get("tag_name", "").strip()
        release_url = data.get("html_url", "")

        if latest and version_tuple(latest) > version_tuple(VERSION):
            show_update_popup(root, theme_manager, latest, release_url)
        else:
            msgbox.showinfo("Up to Date", f"You are using the latest version ({VERSION}).")
    except Exception as e:
        msgbox.showerror("Update Check Failed", f"Could not check for updates:\n{e}")


def show_update_popup(root, theme_manager, latest_version, release_url):
    popup = ctk.CTkToplevel(root)
    popup.title("Update Available")
    popup.resizable(False, False)
    popup.transient(root)
    popup.minsize(250,220)
    popup.grab_set()
    popup.focus_force()

    # Theme colors
    if getattr(theme_manager, "current_mode", "LIGHT").upper() == "DARK":
        accent = "#5865f2"
    else:
        accent = "#0078d7"

    frm = ctk.CTkFrame(popup)
    frm.pack(padx=20, pady=20, fill="both", expand=True)

    ctk.CTkLabel(frm, text="Update Available", font=("Segoe UI", 14, "bold")).pack(pady=(0, 5))
    ctk.CTkLabel(frm, text=f"Your version: {VERSION}", font=("Segoe UI", 11)).pack()
    ctk.CTkLabel(frm, text=f"Latest version: {latest_version}", font=("Segoe UI", 11, "bold")).pack(pady=(0, 10))

    def open_github():
        webbrowser.open_new(release_url)

    try:
        import load_utils
        icon_path = load_utils.get_resource_path("assets/github-icon.png")
        img = Image.open(icon_path).resize((18, 18), Image.LANCZOS)
        github_img = ctk.CTkImage(light_image=img, dark_image=img)
        ctk.CTkButton(
            frm,
            image=github_img,
            text="Download Latest Release",
            compound="left",
            command=open_github,
            width=180,
        ).pack(pady=(5, 0))
    except Exception as e:
        print(f"⚠️ Could not load GitHub icon: {e}")
        ctk.CTkButton(frm, text="Download Latest Release", command=open_github, width=180).pack(pady=(5, 0))

    ctk.CTkButton(frm, text="Close", command=popup.destroy, width=100).pack(pady=(15, 0))

    popup.update_idletasks()
    w, h = popup.winfo_width(), popup.winfo_height()
    x = (popup.winfo_screenwidth() // 2) - (w // 2)
    y = (popup.winfo_screenheight() // 2) - (h // 2)
    popup.geometry(f"{w}x{h}+{x}+{y}")

    popup.wait_window()
