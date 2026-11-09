import json

import customtkinter as ctk

from settings import get_setting


def _safe_combo_values(values, fallback=None):
    cleaned = []

    if values is not None:
        try:
            iterable = list(values)
        except (TypeError, ValueError):
            iterable = []

        for value in iterable:
            if value is None:
                continue

            text = str(value).strip()

            if not text:
                continue

            if text not in cleaned:
                cleaned.append(text)

    if not cleaned and fallback is not None:
        fallback_text = str(fallback).strip()

        if fallback_text:
            cleaned.append(fallback_text)

    return cleaned


def _safe_json_dict_setting(section, key):
    value = get_setting(section, key, {})

    if isinstance(value, dict):
        return value

    if not value:
        return {}

    try:
        parsed = json.loads(value)

        if isinstance(parsed, dict):
            return parsed
    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    return {}


def _safe_float_setting(section, key, default, minimum=0.0, maximum=1.0):
    value = get_setting(
        section,
        key,
        default
    )

    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(default)

    value = max(
        minimum,
        min(maximum, value)
    )

    return value


# -------------------------------
# Collapsible Section
# -------------------------------
class CollapsibleSection(ctk.CTkFrame):
    def __init__(self, parent, title, expanded=True):
        super().__init__(parent, fg_color="transparent")
        self.title = title
        self.expanded = expanded
        self.settings_window = None

        self.header = ctk.CTkButton(self, text="", anchor="w", height=34, command=self.toggle)
        self.header.pack(fill="x", pady=(3, 0))

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        if self.expanded:
            self.content.pack(fill="x", padx=8, pady=(5, 8))

        self._update_header()

    def _update_header(self):
        arrow = "▼" if self.expanded else "▶"
        self.header.configure(text=f"{arrow}  {self.title}")

    def toggle(self):
        self.expanded = not self.expanded

        if self.expanded:
            self.content.pack(fill="x", padx=8, pady=(5, 8))
        else:
            self.content.pack_forget()

        self._update_header()
