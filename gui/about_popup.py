import sys
import tkinter as tk
import webbrowser
from tkinter import ttk
from version_utils import VERSION

def show_about_popup(root, theme_manager):
    popup = tk.Toplevel(root)
    popup.title("About Curio Tracker")
    popup.resizable(False, False)

    # Theme colors
    if theme_manager.is_dark_mode:
        bg, fg, accent = "#36393f", "#dcddde", "#5865f2"
    else:
        bg, fg, accent = "#f4f6f8", "black", "#0078d7"
    popup.configure(bg=bg)

    # Layout frame
    frm = ttk.Frame(popup)
    frm.pack(padx=20, pady=20)

    # Author info
    ttk.Label(frm, text="Heist Curio Tracker", font=("Segoe UI", 14, "bold")).pack(pady=(0, 5))
    ttk.Label(frm, text="Author: Sokratis Fotkatzkis").pack()
    ttk.Label(frm, text=f"Version: {VERSION}").pack(pady=(0, 10))

    # ---- GitHub button ----
    import load_utils

    def open_github():
        webbrowser.open_new("https://github.com/sokratis12GR/Curio-Tracker")

    try:
        github_img = tk.PhotoImage(file=load_utils.get_resource_path("assets/github-icon.png")).subsample(8, 8)

        github_btn = tk.Button(
            frm,
            image=github_img,
            text=" GitHub Repository",
            compound="left",  # icon on the left, text on the right
            font=("Segoe UI", 10, "underline"),
            fg=accent,
            cursor="hand2",
            command=open_github,
            borderwidth=0,
            bg=bg,
            activebackground=bg
        )
        github_btn.image = github_img  # keep a reference
        github_btn.pack(pady=(5, 0))

    except Exception:
        # fallback text button if image not found
        ttk.Button(frm, text="GitHub Repository", command=open_github).pack(pady=(5, 0))

    # ---- Ko-fi button ----
    def open_kofi():
        webbrowser.open_new("https://ko-fi.com/sofodev")  # <-- replace with your Ko-fi link

    try:
        kofi_img = tk.PhotoImage(file=load_utils.get_resource_path("assets/kofi5.png")).subsample(4, 4)
        kofi_btn = tk.Button(frm, image=kofi_img, command=open_kofi, borderwidth=0, bg=bg, activebackground=bg,
                             cursor="hand2")
        kofi_btn.image = kofi_img  # keep reference
        kofi_btn.pack(pady=(10, 0))
    except Exception as e:
        # fallback text button if image missing
        ttk.Button(frm, text="Support me on Ko-fi", command=open_kofi).pack(pady=(10, 0))

    ttk.Button(frm, text="Close", command=popup.destroy).pack(pady=(15, 0))

    # Center popup
    popup.update_idletasks()
    w, h = popup.winfo_width(), popup.winfo_height()
    x = (popup.winfo_screenwidth() // 2) - (w // 2)
    y = (popup.winfo_screenheight() // 2) - (h // 2)
    popup.geometry(f"{w}x{h}+{x}+{y}")
    popup.transient(root)
    popup.grab_set()
    root.wait_window(popup)
