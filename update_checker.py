import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import webbrowser
import requests
from version_utils import VERSION

def version_tuple(v: str):
    return tuple(int(x) for x in v.split("."))


def check_for_updates(root, theme_manager):
    try:
        url = "https://api.github.com/repos/sokratis12GR/Curio-Tracker/releases/latest"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        latest = data["tag_name"]
        release_url = data["html_url"]

        if version_tuple(latest) > version_tuple(VERSION):
            show_update_popup(root, theme_manager, latest, release_url)
        else:
            messagebox.showinfo("Up to Date", f"You are using the latest version ({VERSION}).")
    except Exception as e:
        messagebox.showerror("Update Check Failed", f"Could not check for updates:\n{e}")


def show_update_popup(root, theme_manager, latest_version, release_url):
    popup = tk.Toplevel(root)
    popup.title("Update Available")
    popup.resizable(False, False)

    if theme_manager.is_dark_mode:
        bg, fg, accent = "#36393f", "#dcddde", "#5865f2"
    else:
        bg, fg, accent = "#f4f6f8", "black", "#0078d7"
    popup.configure(bg=bg)

    frm = ttk.Frame(popup)
    frm.pack(padx=20, pady=20)

    ttk.Label(frm, text="Update Available", font=("Segoe UI", 14, "bold")).pack(pady=(0, 5))
    ttk.Label(frm, text=f"Your version: {VERSION}").pack()
    ttk.Label(frm, text=f"Latest version: {latest_version}", font=("Segoe UI", 10, "bold")).pack(pady=(0, 10))

    def open_github():
        webbrowser.open_new(release_url)

    try:
        import load_utils
        github_img = tk.PhotoImage(file=load_utils.get_resource_path("assets/github-icon.png")).subsample(8, 8)
        github_btn = tk.Button(
            frm,
            image=github_img,
            text=" Download Latest Release",
            compound="left",
            font=("Segoe UI", 10, "underline"),
            fg=accent,
            cursor="hand2",
            command=open_github,
            borderwidth=0,
            bg=bg,
            activebackground=bg
        )
        github_btn.image = github_img
        github_btn.pack(pady=(5, 0))
    except Exception:
        ttk.Button(frm, text="Download Latest Release", command=open_github).pack(pady=(5, 0))

    ttk.Button(frm, text="Close", command=popup.destroy).pack(pady=(15, 0))

    popup.update_idletasks()
    w, h = popup.winfo_width(), popup.winfo_height()
    x = (popup.winfo_screenwidth() // 2) - (w // 2)
    y = (popup.winfo_screenheight() // 2) - (h // 2)
    popup.geometry(f"{w}x{h}+{x}+{y}")
    popup.transient(root)
    popup.grab_set()
    root.wait_window(popup)
