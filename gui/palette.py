"""Shared colour palettes for all windows.

Three themes are supported: LIGHT, DARK and POE. CTk only knows light/dark
appearance modes, so POE runs on CTk's dark mode with its own colour theme
(ctk_themes/poe_theme.json). Switching to/from POE requires a restart, so the
active theme is read once at import time.
"""

import custom_themes
from settings import get_setting

THEME_MODES = custom_themes.BUILTIN_MODES


def normalize_mode(mode) -> str:
    mode = str(mode or "DARK").upper()
    return mode if mode in THEME_MODES else "DARK"


# Theme the app was started with (user theme name or built-in mode) and the
# built-in mode it is based on. Changes to either need a restart.
ACTIVE_THEME = str(get_setting("Application", "theme_mode", "DARK") or "DARK")
ACTIVE_MODE, ACTIVE_COLORS = custom_themes.resolve(ACTIVE_THEME)
COLOR_MAP = custom_themes.color_map(ACTIVE_MODE, ACTIVE_COLORS)
_SLOT = 0 if ACTIVE_MODE == "LIGHT" else 1


def recolor(value):
    """Apply the active user theme / accent to a colour, (light, dark) tuple or dict."""
    if isinstance(value, str):
        return COLOR_MAP.get(value.lower(), value)
    if isinstance(value, tuple) and len(value) == 2:
        out = list(value)
        out[_SLOT] = recolor(out[_SLOT])
        return tuple(out)
    if isinstance(value, dict):
        return {k: recolor(v) for k, v in value.items()}
    return value


def is_poe() -> bool:
    return ACTIVE_MODE == "POE"


def themed(light_dark: tuple, poe):
    """(light, dark) tuple for CTk; in POE mode the dark slot becomes `poe`.
    The active user theme / accent colour is applied to the result."""
    if is_poe():
        return (light_dark[0], recolor(poe))
    return recolor(light_dark)


# Path of Exile–inspired palette. Colours only — no GGG art.
POE_PALETTE = {
    "window_bg": "#0c0b0a",
    "panel_bg": "#12100d",
    "row_bg": "#14110e",
    "row_alt_bg": "#1a1612",
    "border": "#5a4a32",
    "border_dim": "#3a3024",
    "header_bg": "#1f1a14",
    "gold": "#a38d6d",          # labels / headers
    "gold_bright": "#d8c39b",   # hover / selected accent
    "text": "#c8c8c8",          # default PoE text
    "unique": "#af6025",        # unique item name
    "unique_dim": "#80664c",    # missing unique (dimmed but readable)
    "currency": "#aa9e82",      # currency text
    "muted": "#9a8a70",         # small secondary text (readable on panel_bg)
    "select_bg": "#3a2e1e",
    "bar_track": "#0a0908",
    "bar_fill": "#a38d6d",
}

# Same keys as POE_PALETTE, for the Collection window in the other themes.
COLLECTION_PALETTE = {
    "POE": POE_PALETTE,
    "DARK": {
        "window_bg": "#2f3136",
        "panel_bg": "#2b2d31",
        "row_bg": "#2f3136",
        "row_alt_bg": "#36393f",
        "border": "#40444b",
        "border_dim": "#3a3d44",
        "header_bg": "#202225",
        "gold": "#b9bbbe",
        "gold_bright": "#ffffff",
        "text": "#dcddde",
        "unique": "#d27a3a",
        "unique_dim": "#8e9297",
        "currency": "#aa9e82",
        "muted": "#8e9297",
        "select_bg": "#4752c4",
        "bar_track": "#202225",
        "bar_fill": "#5865f2",
    },
    "LIGHT": {
        "window_bg": "#f4f6f8",
        "panel_bg": "#ffffff",
        "row_bg": "#f4f6f8",
        "row_alt_bg": "#e8eaed",
        "border": "#d0d4d9",
        "border_dim": "#e0e0e0",
        "header_bg": "#dfe3e8",
        "gold": "#2b2f33",
        "gold_bright": "#003a6b",
        "text": "#1f2328",
        "unique": "#af6025",
        "unique_dim": "#8a7a66",
        "currency": "#7a6a48",
        "muted": "#5f6368",
        "select_bg": "#cfe3f7",
        "bar_track": "#e0e0e0",
        "bar_fill": "#0078d7",
    },
}

TREE_PALETTE = {
    "DARK": {
        "bg": "#2f3136",
        "alt_bg": "#36393f",
        "fg": "#dcddde",
        "hover_bg": "#42464e",
        "sel_bg": "#4752c4",
        "sel_fg": "#ffffff",
        "heading_bg": "#202225",
        "heading_hover_bg": "#292b2f",
        "heading_fg": "#b9bbbe",
    },
    "LIGHT": {
        "bg": "#f4f6f8",
        "alt_bg": "#e8eaed",
        "fg": "#000000",
        "hover_bg": "#d6e6f5",
        "sel_bg": "#0078d7",
        "sel_fg": "#ffffff",
        "heading_bg": "#dfe3e8",
        "heading_hover_bg": "#d3d8de",
        "heading_fg": "#2b2f33",
    },
    "POE": {
        "bg": POE_PALETTE["row_bg"],
        "alt_bg": POE_PALETTE["row_alt_bg"],
        "fg": POE_PALETTE["text"],
        "hover_bg": "#2a2218",
        "sel_bg": POE_PALETTE["select_bg"],
        "sel_fg": POE_PALETTE["gold_bright"],
        "heading_bg": POE_PALETTE["header_bg"],
        "heading_hover_bg": POE_PALETTE["select_bg"],
        "heading_fg": POE_PALETTE["gold"],
    },
}

if COLOR_MAP:
    if ACTIVE_MODE == "POE":
        POE_PALETTE.update(recolor(POE_PALETTE))
    else:
        COLLECTION_PALETTE[ACTIVE_MODE] = recolor(COLLECTION_PALETTE[ACTIVE_MODE])
    TREE_PALETTE[ACTIVE_MODE] = recolor(TREE_PALETTE[ACTIVE_MODE])

# (light, dark) tuples for CTk widgets
SEPARATOR_COLOR = themed(("#d0d4d9", "#40444b"), POE_PALETTE["border_dim"])
MUTED_TEXT = themed(("#5f6368", "#8e9297"), POE_PALETTE["muted"])
CARD_COLOR = themed(("#e8eaed", "#36393f"), POE_PALETTE["row_alt_bg"])
DANGER_COLOR = ("#c62828", "#ed4245")
DANGER_HOVER = themed(("#fbe3e3", "#4a2a2d"), "#3a1a14")
ACCENT_COLOR = themed(("#0078d7", "#5865f2"), POE_PALETTE["gold"])
# Single accent colour for the active theme (for widgets that take one colour).
ACCENT_HEX = ACCENT_COLOR[_SLOT]


def tree_palette(mode: str) -> dict:
    return TREE_PALETTE.get(str(mode).upper(), TREE_PALETTE[ACTIVE_MODE])


def collection_palette(mode: str) -> dict:
    return COLLECTION_PALETTE.get(str(mode).upper(), COLLECTION_PALETTE[ACTIVE_MODE])
