import os

import customtkinter as ctk

from load_utils import get_resource_path

THEME_FILES = {
    "LIGHT": "ctk_themes/heist_theme.json",
    "DARK": "ctk_themes/heist_theme.json",
    "POE": "ctk_themes/poe_theme.json",
}


def _appearance(mode):
    return "light" if str(mode).upper() == "LIGHT" else "dark"


def needs_restart(old_mode, new_mode):
    """Switching to/from POE swaps the CTk colour theme, which needs a restart."""
    old_mode, new_mode = str(old_mode).upper(), str(new_mode).upper()
    return old_mode != new_mode and "POE" in (old_mode, new_mode)


def apply_theme(mode):
    ctk.set_appearance_mode(_appearance(mode))


class CTkThemes:
    def __init__(self, default_mode="DARK"):
        self.current_mode = default_mode.upper()

        self.theme_file = get_resource_path(
            THEME_FILES.get(self.current_mode, THEME_FILES["DARK"])
        )

        if os.path.isfile(self.theme_file):
            ctk.set_default_color_theme(
                self.theme_file
            )

            print(
                f"[INFO] Loaded CTk theme: "
                f"{self.theme_file}"
            )
        else:
            print(
                f"[WARN] Theme file not found: "
                f"{self.theme_file}"
            )

        ctk.set_appearance_mode(_appearance(self.current_mode))

    def register(self, widget, widget_type=None):
        pass
