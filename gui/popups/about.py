import os
import sys
import webbrowser

from PIL import Image
import customtkinter as ctk

import load_utils
from fonts import make_font
from gui.palette import POE_PALETTE
from version_utils import VERSION
from win_utils import center_window_on_parent, prepare_popup

STATS_URL = "https://sokratis.space/curio_tracker/stats/"
WEBSITE_URL = "https://sokratis.space/curio_tracker/"
GITHUB_URL = "https://github.com/sokratis12GR/Curio-Tracker"
ISSUES_URL = "https://github.com/sokratis12GR/Curio-Tracker/issues"
KOFI_URL = "https://ko-fi.com/sofodev"

FULL_WIDTH = 298
HALF_WIDTH = 145


def _open_url(url):
    try:
        webbrowser.open_new(url)
    except Exception as e:
        print(f"Could not open {url}: {e}")


def _load_github_icon():
    try:
        icon_path = load_utils.get_resource_path("assets/github-icon.png")
        img = Image.open(icon_path).resize((18, 18), Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img)
    except Exception as e:
        print(f"Could not load GitHub icon: {e}")
        return None


def _section(parent, title):
    """Create a titled, rounded section frame and return its inner body."""
    section = ctk.CTkFrame(parent, corner_radius=8)
    section.pack(fill="x", padx=4, pady=(0, 10))

    ctk.CTkLabel(
        section,
        text=title,
        font=make_font(12, "bold")
    ).pack(pady=(8, 4))

    body = ctk.CTkFrame(section, fg_color="transparent")
    body.pack(padx=10, pady=(0, 10))
    return body


class CustomAboutPopup:
    def __init__(self, parent, theme_manager=None):
        self.parent = parent
        self.theme_manager = theme_manager

        # --- Paths ---
        self.data_directory = os.path.dirname(load_utils.SETTINGS_PATH)
        self.logs_directory = os.path.dirname(load_utils.LOG_FILE)

        # --- Popup setup ---
        self.popup = ctk.CTkToplevel(self.parent)
        prepare_popup(self.popup)
        self.popup.title("About Heist Curio Tracker")
        self.popup.resizable(False, False)
        self.popup.protocol("WM_DELETE_WINDOW", self._close)
        self.popup.bind("<Escape>", lambda e: self._close())
        self.popup.transient(self.parent.winfo_toplevel())
        self.popup.minsize(430, 620)
        self.popup.attributes("-topmost", True)

        # --- Determine accent color from theme ---
        mode = getattr(self.theme_manager, "current_mode", "LIGHT").upper()
        self.accent = {"DARK": "#5865f2", "POE": POE_PALETTE["gold"]}.get(mode, "#0078d7")

        # --- Frame container ---
        frame = ctk.CTkFrame(self.popup, fg_color="transparent")
        frame.pack(padx=20, pady=16, fill="both", expand=True)

        self._build_header(frame)
        self._build_data_section(frame)
        self._build_local_section(frame)
        self._build_project_section(frame)
        self._build_footer(frame)

        # --- Center popup ---
        center_window_on_parent(self.popup, self.parent)

        self.popup.grab_set()
        self.popup.focus_force()

    # --- Sections ---
    def _build_header(self, frame):
        ctk.CTkLabel(
            frame,
            text="Heist Curio Tracker",
            font=make_font(18, "bold"),
            text_color=self.accent
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            frame,
            text="Path of Exile Heist Curio tracking and data utility",
            font=make_font(10),
            text_color=("gray35", "gray70")
        ).pack()

        ctk.CTkLabel(
            frame,
            text=f"Version {VERSION}  •  Created by Sokratis Fotkatzikis",
            font=make_font(10, "bold")
        ).pack(pady=(4, 12))

    def _build_data_section(self, frame):
        body = _section(frame, "Your Data")

        ctk.CTkButton(
            body,
            text="Analyze Your Data",
            width=FULL_WIDTH,
            height=36,
            font=make_font(12, "bold"),
            fg_color=self.accent,
            cursor="hand2",
            command=lambda: _open_url(STATS_URL)
        ).pack()

        ctk.CTkLabel(
            body,
            text="Upload your exported data for charts and stats",
            font=make_font(9),
            text_color=("gray40", "gray60")
        ).pack(pady=(4, 0))

    def _build_local_section(self, frame):
        body = _section(frame, "Local Data")

        ctk.CTkButton(
            body,
            text="Open Data Folder",
            width=HALF_WIDTH,
            command=lambda: self._open_folder(self.data_directory)
        ).grid(row=0, column=0, padx=4, pady=(0, 6))

        ctk.CTkButton(
            body,
            text="Open Logs",
            width=HALF_WIDTH,
            command=lambda: self._open_folder(self.logs_directory)
        ).grid(row=0, column=1, padx=4, pady=(0, 6))

        self.debug_button = ctk.CTkButton(
            body,
            text="Copy Debug Information",
            width=FULL_WIDTH,
            command=self._copy_debug_info
        )
        self.debug_button.grid(row=1, column=0, columnspan=2, padx=4)

    def _build_project_section(self, frame):
        body = _section(frame, "Project")

        github_icon = _load_github_icon()
        buttons = [
            dict(text="Project Website", command=lambda: _open_url(WEBSITE_URL)),
            dict(text="GitHub", command=lambda: _open_url(GITHUB_URL),
                 image=github_icon, compound="left"),
            dict(text="Report an Issue", command=lambda: _open_url(ISSUES_URL)),
            dict(text="Support on Ko-fi", command=lambda: _open_url(KOFI_URL)),
        ]

        for i, opts in enumerate(buttons):
            if opts.get("image") is None:
                opts.pop("image", None)
                opts.pop("compound", None)
            ctk.CTkButton(
                body,
                width=HALF_WIDTH,
                cursor="hand2",
                **opts
            ).grid(row=i // 2, column=i % 2, padx=4, pady=3)

    def _build_footer(self, frame):
        ctk.CTkLabel(
            frame,
            text=(
                "This product isn't affiliated with or endorsed by "
                "Grinding Gear Games in any way. Path of Exile and its "
                "game imagery are property of Grinding Gear Games."
            ),
            font=make_font(9),
            text_color=("gray40", "gray60"),
            wraplength=360,
            justify="center"
        ).pack(pady=(4, 0))

        ctk.CTkButton(
            frame,
            text="Close",
            command=self._close,
            width=100
        ).pack(pady=(10, 0))

    # --- Actions ---
    def _open_folder(self, path):
        try:
            os.makedirs(path, exist_ok=True)

            if sys.platform == "win32":
                os.startfile(path)
            else:
                webbrowser.open(f"file://{path}")

        except Exception as e:
            print(f"Could not open folder {path}: {e}")

    def _copy_debug_info(self):
        debug_info = (
            f"Heist Curio Tracker\n"
            f"Version: {VERSION}\n"
            f"Data directory: {self.data_directory}\n"
            f"Logs directory: {self.logs_directory}"
        )

        try:
            self.popup.clipboard_clear()
            self.popup.clipboard_append(debug_info)
            self.popup.update()

            self.debug_button.configure(text="Copied!")
            self.popup.after(1500, self._reset_debug_button)

        except Exception as e:
            print(f"Could not copy debug information: {e}")

    def _reset_debug_button(self):
        try:
            if self.debug_button.winfo_exists():
                self.debug_button.configure(text="Copy Debug Information")
        except Exception:
            pass

    # --- Close ---
    def _close(self):
        try:
            if self.popup.winfo_exists():
                self.popup.grab_release()
                self.popup.after(10, self.popup.destroy)
        except Exception:
            pass
