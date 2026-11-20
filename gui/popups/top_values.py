import threading
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
from PIL import Image, ImageTk

from currency_utils import convert_to_float
from fonts import make_font
from gui.palette import collection_palette
from img_utils import get_cached_icon, get_icons_parallel
from link_utils import generate_trade_url_from_values, open_url
from ocr_utils import format_currency_value
from settings import get_setting
from top_values import available_types, rank_curios, sort_rows
from win_utils import center_window_on_parent, prepare_popup

LIMITS = {"Top 25": 25, "Top 50": 50, "Top 100": 100, "All": None}
ICON_SIZE = 24
HIGHLIGHT_COUNT = 3

# Display heading -> row key. "#0" is the tree column that holds the icon and name.
COLUMNS = {"#0": ("Name", "name"), "Rank": ("Rank", "rank"), "Type": ("Type", "type"),
           "Tier": ("Tier", "tier"), "Chaos": ("Chaos", "chaos"), "Divine": ("Divine", "divine")}
DATA_COLUMNS = ("Rank", "Type", "Tier", "Chaos", "Divine")
COLUMN_WIDTHS = {"#0": 320, "Rank": 75, "Type": 130, "Tier": 60, "Chaos": 90, "Divine": 90}
DEFAULT_DESCENDING = {"chaos", "divine"}


class TopValuesPopup:
    """Lists every curio that can drop, ranked by its poe.ninja value for the active league."""

    def __init__(self, parent, tracker):
        self.parent = parent
        self.tracker = tracker
        self.theme_mode = str(get_setting("Application", "theme_mode", "DARK")).upper()
        self.sort_column = "rank"
        self.sort_desc = False
        self._icons = {}
        self._requested_icons = set()

    def _datasets(self):
        currency = getattr(self.tracker, "CURRENCY_DATASET", {}) or {}
        tiers = getattr(self.tracker, "TIERS_DATASET", {}) or {}
        term_types = getattr(self.tracker, "term_types", {}) or {}
        return currency, tiers, term_types

    def show(self):
        P = collection_palette(self.theme_mode)
        self.P = P
        popup = ctk.CTkToplevel(self.parent)
        prepare_popup(popup)
        popup.title("Most Valuable Curios")
        popup.geometry("820x680")
        popup.minsize(640, 420)
        popup.transient(self.parent.winfo_toplevel())
        popup.configure(fg_color=P["window_bg"])
        popup.bind("<Escape>", lambda e: popup.destroy())
        self.popup = popup

        currency, _, term_types = self._datasets()

        self.placeholder = ImageTk.PhotoImage(
            Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0)), master=popup)

        self._build_header(popup, currency)

        controls = ctk.CTkFrame(popup, fg_color="transparent")
        controls.pack(fill="x", padx=12, pady=(0, 8))

        self.search_var = ctk.StringVar()
        search = ctk.CTkEntry(controls, textvariable=self.search_var, placeholder_text="Search...", width=240)
        search.pack(side="left")
        self.search_var.trace_add("write", lambda *_: self.refresh())

        self.type_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(controls, variable=self.type_var, values=["All"] + available_types(currency, term_types),
                          command=lambda _: self.refresh(), width=150).pack(side="left", padx=(8, 0))

        self.limit_var = ctk.StringVar(value="Top 50")
        ctk.CTkOptionMenu(controls, variable=self.limit_var, values=list(LIMITS),
                          command=lambda _: self.refresh(), width=100).pack(side="left", padx=(8, 0))

        table = ctk.CTkFrame(popup, fg_color=P["window_bg"], corner_radius=0)
        table.pack(fill="both", expand=True, padx=12)

        self._apply_tree_theme(P)
        self.tree = ttk.Treeview(table, columns=DATA_COLUMNS, show="tree headings", style="TopValues.Treeview")
        for col in COLUMNS:
            anchor = "w" if col in ("#0", "Type") else "center"
            self.tree.heading(col, anchor=anchor, command=lambda c=col: self._on_heading(c))
            self.tree.column(col, width=COLUMN_WIDTHS[col], anchor=anchor, stretch=(col == "#0"))
        self.tree.tag_configure("odd", background=P["row_alt_bg"])
        self.tree.tag_configure("top", foreground=P["gold_bright"], font=self._table_font("bold"))
        self.tree.bind("<Double-1>", self._on_double_click)

        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview,
                                  style="TopValues.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.footer = ctk.CTkLabel(popup, text="", text_color=P["muted"], font=make_font(10))
        self.footer.pack(fill="x", padx=14, pady=(4, 8), anchor="w")

        self.refresh()
        center_window_on_parent(popup, self.parent)
        search.focus_set()

    def _build_header(self, popup, currency):
        P = self.P
        header = ctk.CTkFrame(popup, fg_color=P["panel_bg"], corner_radius=6)
        header.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(header, text="Most Valuable Curios", text_color=P["gold"],
                     font=make_font(16, "bold")).pack(side="left", padx=12, pady=8)

        league = get_setting("Application", "data_league", "")
        divine = convert_to_float((currency.get("Divine Orb") or {}).get("chaos"))
        details = [part for part in (
            f"League: {league}" if league else "",
            f"1 Divine = {format_currency_value(divine)} Chaos" if divine else "",
        ) if part]
        ctk.CTkLabel(header, text="   |   ".join(details), text_color=P["currency"],
                     font=make_font(11)).pack(side="right", padx=12, pady=8)

    def _on_heading(self, col):
        key = COLUMNS[col][1]
        if self.sort_column == key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_column = key
            self.sort_desc = key in DEFAULT_DESCENDING
        self.refresh()

    def _update_headings(self):
        for col, (label, key) in COLUMNS.items():
            arrow = (" ▼" if self.sort_desc else " ▲") if key == self.sort_column else ""
            self.tree.heading(col, text=label + arrow)

    def refresh(self):
        currency, tiers, term_types = self._datasets()
        rows = rank_curios(currency, term_types, tiers,
                           type_filter=self.type_var.get(),
                           search=self.search_var.get(),
                           limit=LIMITS.get(self.limit_var.get()))
        rows = sort_rows(rows, self.sort_column, self.sort_desc)
        self._update_headings()

        self.tree.delete(*self.tree.get_children())
        self._row_names = {}
        self._row_types = {}
        for i, row in enumerate(rows):
            tags = ["odd"] if i % 2 else []
            if row["rank"] <= HIGHLIGHT_COUNT:
                tags.append("top")
            iid = self.tree.insert("", tk.END, text=f" {row['name']}", image=self._icon_for(row),
                                   tags=tags, values=(
                                       row["rank"],
                                       row["type"],
                                       row["tier"],
                                       format_currency_value(row["chaos"]),
                                       format_currency_value(row["divine"]) if row["divine"] else "",
                                   ))
            self._row_names[iid] = row["name"]
            self._row_types[iid] = row["type"]

        if not currency:
            self.footer.configure(text="No price data loaded yet.")
        else:
            self.footer.configure(text=f"Showing {len(rows)} curios  ·  prices from poe.ninja  ·  double-click a row to open trade")

        self._load_missing_icons(rows)

    def _icon_for(self, row):
        name = row["name"]
        if name in self._icons:
            return self._icons[name]
        pil = get_cached_icon(name, (ICON_SIZE, ICON_SIZE)) if row["img"] else None
        if pil is None:
            return self.placeholder
        self._icons[name] = ImageTk.PhotoImage(pil, master=self.popup)
        return self._icons[name]

    def _load_missing_icons(self, rows):
        missing = [(r["name"], r["img"]) for r in rows
                   if r["img"] and r["name"] not in self._icons and r["name"] not in self._requested_icons]
        if not missing:
            return
        self._requested_icons.update(name for name, _ in missing)

        def worker():
            loaded = get_icons_parallel(missing, size=(ICON_SIZE, ICON_SIZE))
            if loaded:
                try:
                    self.popup.after(0, lambda: self._apply_icons(loaded))
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    def _apply_icons(self, loaded):
        try:
            if not self.tree.winfo_exists():
                return
        except Exception:
            return
        for name, pil in loaded.items():
            self._icons[name] = ImageTk.PhotoImage(pil, master=self.popup)
        for iid, name in self._row_names.items():
            if name in loaded:
                self.tree.item(iid, image=self._icons[name])

    @staticmethod
    def _table_font(weight="normal"):
        """ttk tables size CTkFont inconsistently, so they get a plain Tk font tuple instead."""
        family = get_setting("Application", "font_family", "Segoe UI")
        return (family, 11, weight) if weight != "normal" else (family, 11)

    def _on_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid or event.y < 0 or self.tree.identify_region(event.x, event.y) == "heading":
            return
        url = generate_trade_url_from_values(self._row_types.get(iid), self._row_names.get(iid))
        if url:
            open_url(url)
        else:
            self.footer.configure(text=f"No trade link available for {self._row_names.get(iid)}.")

    def _apply_tree_theme(self, P):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TopValues.Treeview", background=P["row_bg"], fieldbackground=P["row_bg"],
                        foreground=P["text"], rowheight=32, font=self._table_font(), borderwidth=0, relief="flat")
        style.map("TopValues.Treeview", background=[("selected", P["select_bg"])],
                  foreground=[("selected", P["gold_bright"])])
        style.configure("TopValues.Treeview.Heading", background=P["header_bg"], foreground=P["gold"],
                        font=self._table_font("bold"), borderwidth=1, relief="flat", padding=(4, 6))
        style.map("TopValues.Treeview.Heading",
                  background=[("active", P["select_bg"]), ("pressed", P["select_bg"])],
                  foreground=[("active", P["gold_bright"]), ("pressed", P["gold_bright"])])
        style.configure("TopValues.Vertical.TScrollbar", troughcolor=P["window_bg"], background=P["border"],
                        arrowcolor=P["gold"], bordercolor=P["border_dim"], lightcolor=P["border"],
                        darkcolor=P["border"], relief="flat", arrowsize=12)


def show_top_values_popup(parent, tracker):
    TopValuesPopup(parent, tracker).show()
