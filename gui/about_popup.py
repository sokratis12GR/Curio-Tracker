import webbrowser
from PIL import Image
import customtkinter as ctk

import load_utils
from fonts import make_font
from version_utils import VERSION


def _add_kofi_button(frame):
    def open_kofi():
        webbrowser.open_new("https://ko-fi.com/sofodev")

    try:
        icon_path = load_utils.get_resource_path("assets/kofi5.png")
        img = Image.open(icon_path)
        kofi_img = ctk.CTkImage(light_image=img, dark_image=img, size=(110, 35))

        ctk.CTkButton(
            frame,
            image=kofi_img,
            text="",
            command=open_kofi,
            fg_color="transparent",
            hover_color=("gray75", "gray30"),
            cursor="hand2",
            width=100,
            height=40,
        ).pack(pady=(10, 0))
    except Exception as e:
        print(f"Could not load Ko-fi image: {e}")
        ctk.CTkButton(frame, text="Support me on Ko-fi", command=open_kofi, width=180).pack(pady=(10, 0))


def _add_github_button(frame):
    def open_github():
        webbrowser.open_new("https://github.com/sokratis12GR/Curio-Tracker")

    try:
        icon_path = load_utils.get_resource_path("assets/github-icon.png")
        img = Image.open(icon_path).resize((18, 18), Image.LANCZOS)
        github_img = ctk.CTkImage(light_image=img, dark_image=img)

        ctk.CTkButton(
            frame,
            image=github_img,
            text="GitHub Repository",
            compound="left",
            command=open_github,
            width=180,
        ).pack(pady=(5, 0))
    except Exception as e:
        print(f"Could not load GitHub icon: {e}")
        ctk.CTkButton(frame, text="GitHub Repository", command=open_github, width=180).pack(pady=(5, 0))


class CustomAboutPopup:
    def __init__(self, parent, theme_manager=None):
        self.parent = parent
        self.theme_manager = theme_manager

        # --- Popup setup ---
        self.popup = ctk.CTkToplevel(self.parent)
        self.popup.title("About Curio Tracker")
        self.popup.resizable(False, False)
        self.popup.protocol("WM_DELETE_WINDOW", self._close)
        self.popup.bind("<Escape>", lambda e: self._close())
        self.popup.transient(self.parent)
        self.popup.grab_set()
        self.popup.focus_force()
        self.popup.minsize(250, 220)
        self.popup.attributes("-topmost", True)

        # --- Determine accent color from theme ---
        if getattr(self.theme_manager, "current_mode", "LIGHT").upper() == "DARK":
            self.accent = "#5865f2"
        else:
            self.accent = "#0078d7"

        # --- Frame container ---
        frame = ctk.CTkFrame(self.popup)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        # --- Header ---
        ctk.CTkLabel(frame, text="Heist Curio Tracker", font=make_font(14, "bold")).pack(pady=(0, 5))
        ctk.CTkLabel(frame, text="Author: Sokratis Fotkatzkis", font=make_font(11)).pack()
        ctk.CTkLabel(frame, text=f"Version: {VERSION}", font=make_font(11, "bold")).pack(pady=(0, 10))

        # --- Buttons ---
        _add_github_button(frame)
        _add_kofi_button(frame)

        # --- Close Button ---
        ctk.CTkButton(frame, text="Close", command=self._close, width=100).pack(pady=(15, 0))

        # --- Center popup ---
        self.popup.update_idletasks()
        w, h = self.popup.winfo_width(), self.popup.winfo_height()
        x = (self.popup.winfo_screenwidth() // 2) - (w // 2)
        y = (self.popup.winfo_screenheight() // 2) - (h // 2)
        self.popup.geometry(f"{w}x{h}+{x}+{y}")

    # --- Close ---
    def _close(self):
        try:
            if self.popup.winfo_exists():
                self.popup.grab_release()
                self.popup.after(10, self.popup.destroy)
        except Exception:
            pass
