"""User themes and accent colour.

A user theme is a JSON file in the app data `themes` folder:

    {
      "name": "Ocean",
      "base": "DARK",
      "colors": {"accent": "#1abc9c", "card": "#203040", ...}
    }

It recolours one of the built-in themes (LIGHT, DARK or POE): every colour in
`colors` replaces that role's built-in colour everywhere it is used, both in
the CTk widget theme and in the hand-picked palettes in gui/palette.py.
Themes are applied at startup, so changing them needs a restart.
"""

import json
import os
import re

from load_utils import get_data_path
from settings import get_setting

BUILTIN_MODES = ("LIGHT", "DARK", "POE")
THEMES_DIR = os.path.dirname(get_data_path(os.path.join("themes", "placeholder")))
GENERATED_THEME = os.path.join(THEMES_DIR, ".active_ctk_theme.json")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Editable colour roles: role -> (label, {base: built-in colours it replaces}).
# The first colour of each tuple is the role's default shown in the editor.
ROLES = {
    "accent": ("Accent", {"LIGHT": ("#0078d7",), "DARK": ("#5865f2",), "POE": ("#a38d6d",)}),
    "accent_hover": ("Accent (hover / selected)",
                     {"LIGHT": ("#005fa3",), "DARK": ("#4752c4",), "POE": ()}),
    "window": ("Window background", {"LIGHT": ("#f4f6f8",), "DARK": ("#2f3136",), "POE": ("#12100d",)}),
    "panel": ("Panel background", {"LIGHT": ("#ffffff",), "DARK": ("#2b2d31",), "POE": ("#0c0b0a",)}),
    "card": ("Cards / inputs", {"LIGHT": ("#e8eaed",), "DARK": ("#36393f",), "POE": ("#1a1612",)}),
    "control": ("Buttons / borders", {"LIGHT": ("#e0e0e0",), "DARK": ("#40444b",), "POE": ("#3a3024",)}),
    "header": ("Table header", {"LIGHT": ("#dfe3e8",), "DARK": ("#202225",), "POE": ("#1f1a14",)}),
    "text": ("Text", {"LIGHT": ("#1f2328", "black", "#000000"), "DARK": ("#dcddde",),
                      "POE": ("#c8c8c8",)}),
    "muted": ("Secondary text", {"LIGHT": ("#5f6368",), "DARK": ("#8e9297",), "POE": ("#9a8a70",)}),
}

BASE_THEME_FILES = {
    "LIGHT": "ctk_themes/heist_theme.json",
    "DARK": "ctk_themes/heist_theme.json",
    "POE": "ctk_themes/poe_theme.json",
}


def default_color(role, base):
    sources = ROLES[role][1].get(base, ())
    return sources[0] if sources else None


def is_hex(value):
    return isinstance(value, str) and bool(HEX_RE.match(value))


def darken(hex_color, factor=0.8):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(v * factor))) for v in (r, g, b)))


# ---------- Theme files ----------
def _theme_path(name):
    safe = re.sub(r"[^\w\- ]", "_", name).strip() or "theme"
    return os.path.join(THEMES_DIR, f"{safe}.json")


def validate_theme(data):
    """Return a cleaned theme dict, or raise ValueError."""
    if not isinstance(data, dict):
        raise ValueError("Theme file must contain a JSON object.")
    name = str(data.get("name", "")).strip()
    if not name:
        raise ValueError("Theme needs a \"name\".")
    if name.upper() in BUILTIN_MODES:
        raise ValueError(f"\"{name}\" is a built-in theme name.")
    base = str(data.get("base", "DARK")).upper()
    if base not in BUILTIN_MODES:
        raise ValueError(f"\"base\" must be one of {', '.join(BUILTIN_MODES)}.")
    colors = {}
    for role, value in (data.get("colors") or {}).items():
        if role in ROLES and is_hex(value):
            colors[role] = value.lower()
    return {"name": name, "base": base, "colors": colors}


def list_themes():
    """All valid user themes, keyed by name."""
    themes = {}
    try:
        files = sorted(os.listdir(THEMES_DIR))
    except OSError:
        return themes
    for fname in files:
        if not fname.endswith(".json") or fname.startswith("."):
            continue
        try:
            with open(os.path.join(THEMES_DIR, fname), encoding="utf-8") as f:
                theme = validate_theme(json.load(f))
            themes[theme["name"]] = theme
        except (OSError, ValueError, json.JSONDecodeError) as e:
            print(f"[WARN] Skipping theme {fname}: {e}")
    return themes


def save_theme(theme):
    theme = validate_theme(theme)
    with open(_theme_path(theme["name"]), "w", encoding="utf-8") as f:
        json.dump(theme, f, indent=2)
    return theme


def import_theme(path):
    with open(path, encoding="utf-8") as f:
        return save_theme(json.load(f))


def delete_theme(name):
    path = _theme_path(name)
    if os.path.isfile(path):
        os.remove(path)


def theme_names():
    return list(BUILTIN_MODES) + sorted(list_themes())


# ---------- Active theme ----------
def accent_override():
    value = str(get_setting("Application", "accent_color", "") or "").strip()
    return value.lower() if is_hex(value) else None


def resolve(theme_name):
    """(base mode, {role: colour}) for a theme name plus the accent setting."""
    name = str(theme_name or "DARK")
    if name.upper() in BUILTIN_MODES:
        base, colors = name.upper(), {}
    else:
        theme = list_themes().get(name)
        if theme is None:
            print(f"[WARN] Theme '{name}' not found, using DARK.")
            base, colors = "DARK", {}
        else:
            base, colors = theme["base"], dict(theme["colors"])
    accent = accent_override()
    if accent:
        colors["accent"] = accent
        colors.pop("accent_hover", None)
    if "accent" in colors and "accent_hover" not in colors:
        colors["accent_hover"] = darken(colors["accent"])
    return base, colors


def color_map(base, colors):
    """Built-in colour (lowercase) -> replacement, for the given base."""
    mapping = {}
    for role, new in colors.items():
        for old in ROLES[role][1].get(base, ()):
            mapping[old.lower()] = new
    return mapping


def build_ctk_theme(base, mapping, base_file):
    """Write a copy of the base CTk theme with the mapping applied; returns its path."""
    with open(base_file, encoding="utf-8") as f:
        data = json.load(f)
    slot = 0 if base == "LIGHT" else 1
    for widget in data.values():
        if not isinstance(widget, dict):
            continue
        for value in widget.values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[slot], str):
                value[slot] = mapping.get(value[slot].lower(), value[slot])
    with open(GENERATED_THEME, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return GENERATED_THEME
