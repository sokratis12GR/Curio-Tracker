import os

import customtkinter as ctk

import custom_themes
from load_utils import get_resource_path

THEME_FILES = custom_themes.BASE_THEME_FILES


def _base_mode(mode):
    name = str(mode or "DARK")
    if name.upper() in custom_themes.BUILTIN_MODES:
        return name.upper()
    theme = custom_themes.list_themes().get(name)
    return theme["base"] if theme else "DARK"


def _appearance(mode):
    return "light" if _base_mode(mode) == "LIGHT" else "dark"


def needs_restart(old_mode, new_mode):
    """Only LIGHT <-> DARK can switch live; POE, user themes and a custom accent
    change the CTk colour theme, which needs a restart."""
    old_mode, new_mode = str(old_mode), str(new_mode)
    if old_mode.upper() == new_mode.upper():
        return False
    live = {"LIGHT", "DARK"}
    return (old_mode.upper() not in live or new_mode.upper() not in live
            or custom_themes.accent_override() is not None)


def apply_theme(mode):
    ctk.set_appearance_mode(_appearance(mode))


class CTkThemes:
    def __init__(self, default_mode="DARK"):
        base, colors = custom_themes.resolve(default_mode)
        self.current_mode = base

        self.theme_file = get_resource_path(THEME_FILES[base])

        if os.path.isfile(self.theme_file):
            theme_file = self.theme_file
            mapping = custom_themes.color_map(base, colors)
            if mapping:
                try:
                    theme_file = custom_themes.build_ctk_theme(base, mapping, self.theme_file)
                except (OSError, ValueError) as e:
                    print(f"[WARN] Could not apply custom colours: {e}")

            ctk.set_default_color_theme(theme_file)

            print(
                f"[INFO] Loaded CTk theme: "
                f"{theme_file}"
            )
        else:
            print(
                f"[WARN] Theme file not found: "
                f"{self.theme_file}"
            )

        ctk.set_appearance_mode(_appearance(base))

    def register(self, widget, widget_type=None):
        pass
