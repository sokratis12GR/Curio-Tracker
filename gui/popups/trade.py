import json
import threading
import urllib.parse
import webbrowser

import customtkinter as ctk
from PIL import Image
from customtkinter import CTkImage

from config import LEAGUE
from gui.palette import POE_PALETTE, themed
from img_utils import get_cached_icon, get_icons_parallel
from win_utils import center_window_on_parent, prepare_popup

TRADE_URL_BASE = "https://www.pathofexile.com/trade/search"

# ---------------- ENCHANT MAPPING ----------------
ENCHANT_MODS = {
    "enchant.stat_4168369352": "Heist Targets are always Currency or Scarabs",
    "enchant.stat_2619914138": "Heist Targets are always Replica Unique Items",
    "enchant.stat_3709545805": "Heist Targets are always Enchanted Armaments",
    "enchant.stat_1123534836": "Heist Targets are always Thieves' Trinkets",
    "enchant.stat_4182516619": "Heist Targets are always Experimented Items",
}
# Short labels for the dropdown, e.g. "Currency or Scarabs".
ENCHANT_SHORT = {k: v.replace("Heist Targets are always ", "") for k, v in ENCHANT_MODS.items()}
ENCHANT_BY_TEXT = {v: k for k, v in ENCHANT_SHORT.items()}

ENCHANT_ANY = "Any"
ENCHANT_NONE = "None"
ENCHANT_SPECIFIC = "Specific"

# ---------------- BLUEPRINTS ----------------

BLUEPRINT_LAYOUTS = [
    "Blueprint: Bunker",
    "Blueprint: Records Office",
    "Blueprint: Laboratory",
    "Blueprint: Prohibited Library",
    "Blueprint: Mansion",
    "Blueprint: Smuggler's Den",
    "Blueprint: Repository",
    "Blueprint: Tunnels",
    "Blueprint: Underbelly",
]

ASSET_BASE = "https://sokratis.space/curio_tracker/assets/heist"

BLUEPRINT_ICONS = {
    "Blueprint: Bunker": f"{ASSET_BASE}/bunker.png",
    "Blueprint: Records Office": f"{ASSET_BASE}/records_office.png",
    "Blueprint: Laboratory": f"{ASSET_BASE}/laboratory.png",
    "Blueprint: Prohibited Library": f"{ASSET_BASE}/prohibited_library.png",
    "Blueprint: Mansion": f"{ASSET_BASE}/mansion.png",
    "Blueprint: Smuggler's Den": f"{ASSET_BASE}/smugglers_den.png",
    "Blueprint: Repository": f"{ASSET_BASE}/repository.png",
    "Blueprint: Tunnels": f"{ASSET_BASE}/tunnels.png",
    "Blueprint: Underbelly": f"{ASSET_BASE}/underbelly.png",
}

WINGS_RANGE = (1, 4)
ILVL_RANGE = (50, 100)

DEFAULT_WINGS = ("4", "4")
DEFAULT_ILVL = ("83", "83")

ILVL_PRESETS = [
    ("83", ("83", "83")),
    ("83+", ("83", "")),
    ("75–82", ("75", "82")),
    ("Any", ("", "")),
]


def _range_filter(lo, hi):
    """Trade API range dict; omits unset bounds. Returns None if both unset."""
    f = {}
    if lo is not None:
        f["min"] = lo
    if hi is not None:
        f["max"] = hi
    return f or None


# ---------------- TRADE URL | QUERY ----------------
def build_blueprint_trade_url(
    blueprint_type,
    league=LEAGUE,
    wings_min=4,
    wings_max=4,
    ilvl_min=83,
    ilvl_max=83,
    enchant=None,
    exclude_enchants=False
):
    """Build a trade search URL. Pass None for a bound to leave it open."""
    stats = [{"type": "and", "filters": [], "disabled": False}]

    if enchant:
        stats.append({
            "type": "and",
            "filters": [{"id": enchant, "disabled": False}],
            "disabled": False
        })
    elif exclude_enchants:
        stats.append({
            "type": "not",
            "filters": [{"id": eid, "disabled": False} for eid in ENCHANT_MODS],
            "disabled": False
        })

    filters = {}

    wings = _range_filter(wings_min, wings_max)
    if wings:
        filters["heist_filters"] = {
            "disabled": False,
            "filters": {"heist_wings": wings, "heist_max_wings": dict(wings)}
        }

    ilvl = _range_filter(ilvl_min, ilvl_max)
    if ilvl:
        filters["misc_filters"] = {
            "disabled": False,
            "filters": {"ilvl": ilvl}
        }

    query = {
        "query": {
            "status": {"option": "securable"},
            "type": blueprint_type,
            "stats": stats,
            "filters": filters,
        },
        "sort": {"price": "asc"}
    }

    return (
        f"{TRADE_URL_BASE}/"
        f"{urllib.parse.quote(league)}"
        f"?q={urllib.parse.quote(json.dumps(query))}"
    )


# ---------------- UI ----------------

class QuickTradePopup:

    ICON_SIZE = 32
    WIDTH = 500

    TILE_COLOR = themed(("gray90", "gray13"), POE_PALETTE["row_bg"])
    TILE_HOVER = themed(("gray80", "gray25"), POE_PALETTE["header_bg"])
    TILE_SELECTED_BORDER = themed(("#3B8ED0", "#1F6AA5"), POE_PALETTE["gold"])

    ERROR_COLOR = ("#C0392B", "#E57373")

    def __init__(self, parent):
        self.parent = parent

        self.popup = ctk.CTkToplevel(parent)
        prepare_popup(self.popup)
        self.popup.title("Quick Trade")
        self.popup.resizable(False, False)
        self.popup.transient(parent.winfo_toplevel())

        self.main = ctk.CTkFrame(self.popup, fg_color="transparent")
        self.main.pack(fill="both", expand=True, padx=8, pady=8)
        self.main.grid_columnconfigure(0, weight=1)

        self.filters_open = True

        self.placeholder = CTkImage(
            light_image=Image.new("RGBA", (32, 32), (150, 150, 150, 255)),
            dark_image=Image.new("RGBA", (32, 32), (150, 150, 150, 255)),
            size=(32, 32)
        )

        self.icons = {}
        self.icon_labels = {}
        self.tiles = {}

        # Use icons already in memory before the first draw.
        for name in BLUEPRINT_ICONS:
            cached = get_cached_icon(name, (self.ICON_SIZE, self.ICON_SIZE))
            if cached is not None:
                self.icons[name] = self._to_ctk(cached)

        self._build()
        self._refresh_selection()
        self._update_summary()

        threading.Thread(target=self._wait_and_load_icons, daemon=True).start()

        self._built = True
        self._fit_window()
        center_window_on_parent(self.popup, self.parent)

        self.popup.bind("<Return>", lambda e: self.search())
        self.popup.bind("<Escape>", lambda e: self.popup.destroy())

        self.popup.grab_set()
        self.popup.focus_force()

    # ---------------- ICON SAFE LOAD ----------------

    def _to_ctk(self, pil_img):
        return CTkImage(
            light_image=pil_img,
            dark_image=pil_img,
            size=(self.ICON_SIZE, self.ICON_SIZE)
        )

    def _wait_and_load_icons(self):
        missing = [
            (name, url)
            for name, url in BLUEPRINT_ICONS.items()
            if name not in self.icons
        ]

        loaded = get_icons_parallel(missing, size=(self.ICON_SIZE, self.ICON_SIZE))
        if not loaded:
            return

        try:
            self.popup.after(0, lambda: self._apply_icons(loaded))
        except Exception:
            pass

    def _apply_icons(self, loaded):
        try:
            if not self.popup.winfo_exists():
                return
        except Exception:
            return

        # Swap images on the existing tiles instead of rebuilding the UI.
        for name, pil_img in loaded.items():
            ctk_img = self._to_ctk(pil_img)
            self.icons[name] = ctk_img

            label = self.icon_labels.get(name)
            if label is not None:
                label.configure(image=ctk_img)

    # ---------------- BUILD UI ----------------

    def _filter_row(self, label):
        """Add a 'Label | content' row to the filter panel; returns the content frame."""
        r = self._next_filter_row
        self._next_filter_row += 1

        ctk.CTkLabel(
            self.filter_frame, text=label, font=("Segoe UI", 11, "bold"), anchor="w"
        ).grid(row=r, column=0, sticky="w", padx=(14, 8), pady=4)

        content = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        content.grid(row=r, column=1, sticky="ew", padx=(0, 14), pady=4)
        return content

    def _range_row(self, label, defaults, presets):
        """Min/max entries plus preset buttons, all on one row."""
        row = self._filter_row(label)

        lo = ctk.CTkEntry(row, width=42, placeholder_text="min")
        hi = ctk.CTkEntry(row, width=42, placeholder_text="max")
        lo.insert(0, defaults[0])
        hi.insert(0, defaults[1])

        lo.pack(side="left")
        ctk.CTkLabel(row, text="–", width=14).pack(side="left")
        hi.pack(side="left", padx=(0, 10))

        self._default_border = lo.cget("border_color")

        for entry in (lo, hi):
            entry.bind("<KeyRelease>", lambda e: self._update_summary())

        for text, values in presets:
            ctk.CTkButton(
                row, text=text, width=44, height=26,
                command=lambda v=values: self._set_range(lo, hi, v)
            ).pack(side="left", padx=2)

        return lo, hi

    def _build(self):
        row = 0

        # HEADER
        header = ctk.CTkFrame(self.main, corner_radius=10)
        header.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Quick Search", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(6, 0)
        )
        ctk.CTkLabel(
            header, text=f"League: {LEAGUE}", font=("Segoe UI", 10),
            text_color=("gray45", "gray70")
        ).grid(row=0, column=1, sticky="e", padx=12, pady=(6, 0))

        self.summary_label = ctk.CTkLabel(
            header, text="", font=("Segoe UI", 10), height=18,
            text_color=("gray45", "gray70"), anchor="w", justify="left"
        )
        self.summary_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=12)

        ctk.CTkLabel(
            header, text="Click a blueprint to search with these filters.",
            font=("Segoe UI", 9), height=16, text_color=("gray45", "gray60")
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 6))
        row += 1

        # GRID
        grid = ctk.CTkFrame(self.main, fg_color="transparent")
        grid.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        row += 1

        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="tiles")

        for i, b in enumerate(BLUEPRINT_LAYOUTS):
            r, c = divmod(i, 3)

            frame = ctk.CTkFrame(
                grid, corner_radius=10, fg_color=self.TILE_COLOR,
                border_width=2, border_color=self.TILE_COLOR
            )
            frame.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
            self.tiles[b] = frame

            icon_label = ctk.CTkLabel(
                frame, text="", image=self.icons.get(b, self.placeholder), height=self.ICON_SIZE
            )
            icon_label.pack(pady=(6, 0))
            self.icon_labels[b] = icon_label

            text_label = ctk.CTkLabel(
                frame, text=b.replace("Blueprint: ", ""), font=("Segoe UI", 9), height=16
            )
            text_label.pack(pady=(0, 6))

            def on_enter(e, f=frame):
                f.configure(fg_color=self.TILE_HOVER)

            def on_leave(e, f=frame):
                f.configure(fg_color=self.TILE_COLOR)

            for w in (frame, icon_label, text_label):
                w.bind("<Button-1>", lambda e, n=b: self._select_blueprint(n))
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.configure(cursor="hand2")

        # ---------------- FILTER TOGGLE ----------------

        self.toggle = ctk.CTkButton(self.main, text="Filters ▼", height=26, command=self._toggle_filters)
        self.toggle.grid(row=row, column=0, sticky="ew")
        row += 1

        # ---------------- FILTER PANEL ----------------

        self.filter_frame = ctk.CTkFrame(self.main, corner_radius=12)
        self.filter_frame.grid(row=row, column=0, sticky="ew", pady=(6, 0))
        self.filter_frame.grid_columnconfigure(1, weight=1)
        self.filter_row = row
        self._next_filter_row = 0

        # Blueprint
        self.layout_var = ctk.StringVar(value=BLUEPRINT_LAYOUTS[0])
        ctk.CTkOptionMenu(
            self._filter_row("Blueprint"),
            values=BLUEPRINT_LAYOUTS,
            variable=self.layout_var,
            height=28,
            command=lambda _: (self._refresh_selection(), self._update_summary())
        ).pack(fill="x")

        # Wings
        wing_presets = [(f"{n}/{n}", (str(n), str(n)))
                        for n in range(WINGS_RANGE[0], WINGS_RANGE[1] + 1)]
        wing_presets.append(("Any", ("", "")))
        self.wings_min, self.wings_max = self._range_row("Wings", DEFAULT_WINGS, wing_presets)

        # Item level
        self.ilvl_min, self.ilvl_max = self._range_row("Item Level", DEFAULT_ILVL, ILVL_PRESETS)

        # Enchant
        enchant_row = self._filter_row("Enchant")
        self.enchant_mode = ctk.StringVar(value=ENCHANT_NONE)
        ctk.CTkSegmentedButton(
            enchant_row,
            values=[ENCHANT_ANY, ENCHANT_NONE, ENCHANT_SPECIFIC],
            variable=self.enchant_mode,
            height=28,
            command=lambda _: self._on_enchant_mode()
        ).pack(side="left")

        self.enchant_select = ctk.StringVar(value=next(iter(ENCHANT_SHORT.values())))
        self.enchant_menu = ctk.CTkOptionMenu(
            enchant_row,
            values=list(ENCHANT_SHORT.values()),
            variable=self.enchant_select,
            height=28,
            dynamic_resizing=False,
            command=lambda _: self._update_summary()
        )
        self.enchant_menu.pack(side="left", fill="x", expand=True, padx=(8, 0))

        # Error (only shown when there are errors) + search
        self.error_label = ctk.CTkLabel(
            self.filter_frame, text="", text_color=self.ERROR_COLOR,
            font=("Segoe UI", 10), anchor="w", justify="left", wraplength=440
        )
        self.error_row = self._next_filter_row
        self._next_filter_row += 1

        ctk.CTkButton(
            self.filter_frame, text="Search", command=self.search
        ).grid(row=self._next_filter_row, column=0, columnspan=2, sticky="ew", padx=14, pady=(6, 12))

        self._on_enchant_mode()

    # ---------------- FILTER HELPERS ----------------

    def _set_range(self, lo_entry, hi_entry, values):
        for entry, value in ((lo_entry, values[0]), (hi_entry, values[1])):
            entry.delete(0, "end")
            if value:
                entry.insert(0, value)
        self._update_summary()

    def _on_enchant_mode(self):
        specific = self.enchant_mode.get() == ENCHANT_SPECIFIC
        self.enchant_menu.configure(state="normal" if specific else "disabled")
        self._update_summary()

    def _parse_range(self, lo_entry, hi_entry, bounds, name, errors):
        """Return (lo, hi) as ints or None; append messages to errors."""
        result = []
        for entry in (lo_entry, hi_entry):
            text = entry.get().strip()
            value = None
            ok = True
            if text:
                try:
                    value = int(text)
                    ok = bounds[0] <= value <= bounds[1]
                except ValueError:
                    ok = False
            if not ok:
                errors.append(f"{name} must be a number between {bounds[0]} and {bounds[1]}.")
                value = None
            entry.configure(border_color=self._default_border if ok else self.ERROR_COLOR)
            result.append(value)

        lo, hi = result
        if lo is not None and hi is not None and lo > hi:
            errors.append(f"{name}: min can't be greater than max.")
            hi_entry.configure(border_color=self.ERROR_COLOR)
        return lo, hi

    def _collect_filters(self):
        """Read and validate the form. Returns (kwargs, errors)."""
        errors = []
        wings = self._parse_range(self.wings_min, self.wings_max, WINGS_RANGE, "Wings", errors)
        ilvl = self._parse_range(self.ilvl_min, self.ilvl_max, ILVL_RANGE, "Item level", errors)

        mode = self.enchant_mode.get()
        enchant = ENCHANT_BY_TEXT.get(self.enchant_select.get()) if mode == ENCHANT_SPECIFIC else None
        if mode == ENCHANT_SPECIFIC and enchant is None:
            errors.append("Pick an enchant.")

        kwargs = dict(
            wings_min=wings[0], wings_max=wings[1],
            ilvl_min=ilvl[0], ilvl_max=ilvl[1],
            enchant=enchant,
            exclude_enchants=(mode == ENCHANT_NONE),
        )
        return kwargs, list(dict.fromkeys(errors))

    @staticmethod
    def _describe_range(lo, hi, unit_fmt):
        if lo is None and hi is None:
            return None
        if lo == hi:
            return unit_fmt(str(lo))
        if hi is None:
            return unit_fmt(f"{lo}+")
        if lo is None:
            return unit_fmt(f"≤{hi}")
        return unit_fmt(f"{lo}–{hi}")

    def _update_summary(self):
        kwargs, errors = self._collect_filters()
        self._show_errors(errors)

        parts = [
            self._describe_range(kwargs["ilvl_min"], kwargs["ilvl_max"], lambda s: f"iLvl {s}") or "Any iLvl",
            self._describe_range(
                kwargs["wings_min"], kwargs["wings_max"],
                lambda s: f"{s}/{s} wings" if s.isdigit() else f"{s} wings"
            ) or "Any wings",
        ]
        mode = self.enchant_mode.get()
        if mode == ENCHANT_ANY:
            parts.append("Any enchant")
        elif mode == ENCHANT_NONE:
            parts.append("No enchants")
        else:
            parts.append(f"Targets: {self.enchant_select.get()}")

        self.summary_label.configure(text=" · ".join(parts))

    def _refresh_selection(self):
        selected = self.layout_var.get()
        for name, frame in self.tiles.items():
            frame.configure(
                border_color=self.TILE_SELECTED_BORDER if name == selected else self.TILE_COLOR
            )

    # ---------------- LOGIC ----------------

    def _fit_window(self):
        """Size the popup to its content so nothing needs scrolling."""
        self.popup.update_idletasks()
        height = self.main.winfo_reqheight() + 16  # main's pady
        self.popup.geometry(f"{self.WIDTH}x{height}")

    def _show_errors(self, errors):
        text = "\n".join(errors)
        if text == self.error_label.cget("text"):
            return
        self.error_label.configure(text=text)
        if errors:
            self.error_label.grid(row=self.error_row, column=0, columnspan=2,
                                  sticky="ew", padx=14, pady=(2, 0))
        else:
            self.error_label.grid_remove()
        if getattr(self, "_built", False):
            self._fit_window()

    def _toggle_filters(self):
        if self.filters_open:
            self.filter_frame.grid_remove()
            self.toggle.configure(text="Filters ▶")
        else:
            self.filter_frame.grid(row=self.filter_row, column=0, sticky="ew", pady=(6, 0))
            self.toggle.configure(text="Filters ▼")

        self.filters_open = not self.filters_open
        self._fit_window()

    def search(self):
        kwargs, errors = self._collect_filters()
        self._show_errors(errors)
        if errors:
            if not self.filters_open:
                self._toggle_filters()
            return

        webbrowser.open(build_blueprint_trade_url(self.layout_var.get(), **kwargs))

    def _select_blueprint(self, blueprint):
        self.layout_var.set(blueprint)
        self._refresh_selection()
        self._update_summary()
        self.search()


def show_quick_trade_popup(parent):
    QuickTradePopup(parent)
