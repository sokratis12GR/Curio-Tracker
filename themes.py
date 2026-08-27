import os

import customtkinter as ctk

from load_utils import get_resource_path


def apply_theme(mode):
    mode = mode.upper()

    ctk.set_appearance_mode(
        "dark" if mode != "LIGHT" else "light"
    )


class CTkThemes:
    def __init__(self, default_mode="DARK"):
        self.current_mode = default_mode.upper()

        self.theme_file = get_resource_path(
            "ctk_themes/heist_theme.json"
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

        ctk.set_appearance_mode(
            "dark"
            if self.current_mode != "LIGHT"
            else "light"
        )

    def register(self, widget, widget_type=None):
        pass
