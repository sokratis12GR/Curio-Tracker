import threading
import tkinter as tk
from collections import Counter
from tkinter import ttk

import customtkinter as ctk
from PIL import Image, ImageTk

import config
import ocr_utils as utils
from fonts import make_font
from currency_utils import convert_to_float
from gui.palette import collection_palette
from ocr_utils import format_currency_value
from img_utils import get_cached_icon, get_icon, get_icons_parallel
from link_utils import generate_trade_url_from_values, open_url
from settings import get_setting
from win_utils import center_window_on_parent, prepare_popup


class CollectionPopup:
    ICON_SIZE = 24  # icon width/height

    _cached_items = None
    _cache_lock = threading.Lock()

    def __init__(self, parent=None, tracker=None, title="Collection"):
        self.parent = parent
        self.tracker = tracker
        self.title = title
        self.all_items = []

        self._row_item_map = {}

        self.theme_mode = str(
            get_setting("Application", "theme_mode", "DARK")
        ).upper()

        self.collection_league = str(get_setting("Application", "poeladder_collection_league", ""))

        self.tree_bg = None
        self.tree_alt_bg = None
        self.tree_fg = None

        placeholder_pil = Image.new(
            "RGBA",
            (self.ICON_SIZE, self.ICON_SIZE),
            (150, 150, 150, 255)
        )

        self.placeholder = ImageTk.PhotoImage(
            placeholder_pil,
            master=self.parent
        )

        # Keep Tk image references alive.
        self._image_refs = [self.placeholder]

        # Sort state
        self._sort_column = "Tier"
        self._sort_ascending = True

        # Filter state
        self.type_var = ctk.StringVar(value=self.ALL_TYPES)
        self.owned_var = ctk.StringVar(value="All")
        self.found_only_var = ctk.BooleanVar(value=False)

    ALL_TYPES = "All types"
    HEADINGS = {
        "#0": "Name",
        "Type": "Type",
        "Tier": "Tier",
        "Found": "Found",
        "Owned": "Owned",
        "Value": "Value",
    }

    def show(self):
        popup = ctk.CTkToplevel(self.parent)
        prepare_popup(popup)
        popup.title(self.title)

        popup.geometry("900x720")
        popup.minsize(750, 480)
        popup.resizable(True, True)
        popup.transient(self.parent.winfo_toplevel())
        self.popup = popup

        P = collection_palette(self.theme_mode)

        popup.configure(fg_color=P["window_bg"])

        main_frame = ctk.CTkFrame(popup, fg_color=P["window_bg"], corner_radius=0)
        main_frame.pack(fill="both", expand=True, padx=12, pady=12)

        league_name = getattr(self.tracker, "league_version", "")
        popup.title(f"{self.title} - {league_name} - {self.collection_league}")

        # Build the collection immediately from already-loaded terms.json
        # (needed up front for the Type filter options).
        self.load_items()

        self._apply_tree_theme()
        self._load_currency_icons()

        # --- Stat bar ---
        self._build_stat_bar(main_frame)

        # --- Search + filters ---
        controls = ctk.CTkFrame(main_frame, fg_color="transparent")
        controls.pack(fill="x", pady=(0, 8))

        control_style = dict(
            corner_radius=6,
            border_width=1,
            border_color=P["border"],
            fg_color=P["panel_bg"],
            text_color=P["text"],
            font=make_font(11),
        )

        # No textvariable: CTkEntry hides its placeholder when one is set.
        self.search_entry = ctk.CTkEntry(
            controls,
            placeholder_text="Search name, type or tier...",
            placeholder_text_color=P["muted"],
            height=30,
            **control_style
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.search_entry.bind("<KeyRelease>", lambda e: self.filter_items())

        type_values = [self.ALL_TYPES] + sorted(
            {str(item["type"]) for item in self.all_items},
            key=str.lower
        )
        ctk.CTkOptionMenu(
            controls,
            values=type_values,
            variable=self.type_var,
            width=140,
            height=30,
            corner_radius=6,
            fg_color=P["header_bg"],
            button_color=P["header_bg"],
            button_hover_color=P["select_bg"],
            text_color=P["text"],
            dropdown_fg_color=P["panel_bg"],
            dropdown_hover_color=P["select_bg"],
            dropdown_text_color=P["text"],
            font=make_font(11),
            dropdown_font=make_font(11),
            command=lambda _v: self.filter_items()
        ).pack(side="left", padx=(0, 8))

        ctk.CTkSegmentedButton(
            controls,
            values=["All", "Owned", "Missing"],
            variable=self.owned_var,
            width=210,
            height=30,
            corner_radius=6,
            border_width=2,
            fg_color=P["border_dim"],
            selected_color=P["select_bg"],
            selected_hover_color=P["select_bg"],
            unselected_color=P["panel_bg"],
            unselected_hover_color=P["header_bg"],
            text_color=P["gold_bright"],
            font=make_font(11),
            command=lambda _v: self.filter_items()
        ).pack(side="left", padx=(0, 8))

        ctk.CTkCheckBox(
            controls,
            text="Found only",
            variable=self.found_only_var,
            corner_radius=4,
            border_width=1,
            checkbox_width=18,
            checkbox_height=18,
            border_color=P["border"],
            fg_color=P["select_bg"],
            hover_color=P["header_bg"],
            checkmark_color=P["gold_bright"],
            text_color=P["gold"],
            font=make_font(11),
            command=self.filter_items
        ).pack(side="left")

        columns = ("Type", "Tier", "Found", "Owned", "Value")

        # Rounded bronze-bordered panel around the list; the inner padding
        # keeps the (square) Treeview inside the rounded corners.
        tree_frame = ctk.CTkFrame(
            main_frame,
            fg_color=P["row_bg"],
            corner_radius=8,
            border_width=1,
            border_color=P["border"],
        )
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="tree headings",
            height=20,
            style="Collection.Treeview"
        )

        self.tree.tag_configure("even", background=self.tree_bg)
        self.tree.tag_configure("odd", background=self.tree_alt_bg)

        # Foreground by ownership (Treeview can't colour a single cell):
        # owned rows in unique-item colour, missing rows dimmed.
        self.tree.tag_configure("owned", foreground=P["unique"])
        self.tree.tag_configure("missing", foreground=P["unique_dim"])
        self.tree.tag_configure("unknown", foreground=P["text"])

        self.tree.bind("<Double-1>", self.open_link)
        self.tree.bind("<Motion>", self.on_hover)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Return>", lambda e: self._open_selected("wiki"))

        self._context_menu = tk.Menu(
            self.tree, tearoff=0,
            bg=P["panel_bg"], fg=P["text"],
            activebackground=P["select_bg"], activeforeground=P["gold_bright"],
            bd=1, relief="solid"
        )
        self._context_menu.add_command(
            label="Open Wiki",
            command=lambda: self._open_selected("wiki")
        )
        self._context_menu.add_command(
            label="Open Trade",
            command=lambda: self._open_selected("trade_url")
        )
        self._context_menu.add_separator()
        self._context_menu.add_command(
            label="Copy name",
            command=self._copy_selected_name
        )

        self.tree.heading("#0", text="Name", command=lambda: self.sort_by("#0"))
        self.tree.column("#0", width=250, anchor="w")

        self.tree.heading("Type", text="Type", command=lambda: self.sort_by("Type"))
        self.tree.column("Type", width=120, anchor="center")

        self.tree.heading("Tier", text="Tier", command=lambda: self.sort_by("Tier"))
        self.tree.column("Tier", width=70, anchor="center")

        self.tree.heading("Found", text="Found", command=lambda: self.sort_by("Found"))
        self.tree.column("Found", width=80, anchor="center")

        self.tree.heading("Owned", text="Owned", command=lambda: self.sort_by("Owned"))
        self.tree.column("Owned", width=60, anchor="center")

        self.tree.heading("Value", text="Value", command=lambda: self.sort_by("Value"))
        self.tree.column("Value", width=120, anchor="center")

        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        scrollbar.pack(side="right", fill="y", padx=(0, 6), pady=6)

        scrollbar.configure(style="Collection.Vertical.TScrollbar")

        self.all_items.sort(
            key=lambda x: (
                not bool(x["tier"]),
                str(x["tier"]).lower()
            )
        )
        self._update_heading_arrows()

        # Icons already in memory (preloaded at startup) are applied before
        # the first draw, so most rows appear with their icon straight away.
        self._apply_cached_icons()

        # Names appear immediately.
        self.filter_items()

        threading.Thread(
            target=self._load_icons_thread,
            daemon=True
        ).start()

        threading.Thread(
            target=self._load_found_counts_thread,
            daemon=True
        ).start()

        # Center popup on main application
        center_window_on_parent(
            popup,
            self.parent
        )

        popup.grab_set()
        popup.focus_force()
        popup.wait_window()

    def _apply_tree_theme(self):
        style = ttk.Style()
        style.theme_use("default")

        P = collection_palette(self.theme_mode)

        bg = P["row_bg"]
        fg = P["text"]
        heading_bg = P["header_bg"]
        heading_hover_bg = P["select_bg"]
        heading_fg = P["gold"]
        border_color = P["border_dim"]
        scrollbar_bg = P["border"]
        scrollbar_trough = P["window_bg"]
        scrollbar_arrow = P["gold"]

        self.tree_bg = bg
        self.tree_alt_bg = P["row_alt_bg"]
        self.tree_fg = fg

        style.configure(
            "Collection.Treeview",
            background=bg,
            fieldbackground=bg,
            foreground=fg,
            rowheight=30,
            font=make_font(10),
            borderwidth=0,
            relief="flat"
        )

        style.map(
            "Collection.Treeview",
            background=[("selected", P["select_bg"])],
            foreground=[("selected", P["gold_bright"])]
        )

        style.configure(
            "Collection.Treeview.Heading",
            background=heading_bg,
            foreground=heading_fg,
            font=make_font(10, "bold"),
            borderwidth=1,
            relief="flat",
            padding=(4, 6)
        )

        style.map(
            "Collection.Treeview.Heading",
            background=[
                ("active", heading_hover_bg),
                ("pressed", heading_hover_bg)
            ],
            foreground=[
                ("active", P["gold_bright"]),
                ("pressed", P["gold_bright"])
            ]
        )

        style.configure(
            "Collection.Vertical.TScrollbar",
            troughcolor=scrollbar_trough,
            background=scrollbar_bg,
            arrowcolor=scrollbar_arrow,
            bordercolor=border_color,
            lightcolor=scrollbar_bg,
            darkcolor=scrollbar_bg,
            relief="flat",
            arrowsize=12
        )
        style.map(
            "Collection.Vertical.TScrollbar",
            background=[("active", P["gold"])]
        )


    def _load_currency_icons(self):
        self._currency_icons = {}

        def _load():
            icons = {}
            for key, name, url in (
                ("Chaos", "Chaos Orb (Value Icon)", config.CHAOS_ORB_ICON_URL),
                ("Divines", "Divine Orb (Value Icon)", config.DIVINE_ORB_ICON_URL),
            ):
                try:
                    pil = get_icon(name=name, url=url, size=(22, 22),
                                   parent=self.parent, return_pil=True)
                except Exception:
                    pil = None
                if isinstance(pil, Image.Image):
                    icons[key] = pil

            def _apply():
                for key, pil in icons.items():
                    self._currency_icons[key] = ctk.CTkImage(
                        light_image=pil, dark_image=pil, size=(22, 22)
                    )
                self._update_summary()

            try:
                self.parent.after(0, _apply)
            except Exception:
                pass

        threading.Thread(target=_load, daemon=True).start()

    def on_hover(self, event):
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)

        if not row:
            self.tree.config(cursor="")
            return

        item = self._row_item_map.get(row)

        if not item:
            self.tree.config(cursor="")
            return

        # #0 = Name -> Wiki
        # #5 = Value -> Trade
        if col == "#0" and item.get("wiki"):
            self.tree.config(cursor="hand2")
        elif col == "#5" and item.get("trade_url"):
            self.tree.config(cursor="hand2")
        else:
            self.tree.config(cursor="")

    def load_items(self):
        terms = getattr(self.tracker, "term_types", {}) or {}
        tiers = getattr(self.tracker, "TIERS_DATASET", {}) or {}

        collection_active = getattr(
            self.tracker,
            "COLLECTION_DATASET_ACTIVE",
            {}
        ) or {}

        currency = getattr(self.tracker, "CURRENCY_DATASET", {}) or {}

        if CollectionPopup._cached_items is None:
            with CollectionPopup._cache_lock:
                if CollectionPopup._cached_items is None:
                    cached = []

                    for name, type_name in terms.items():
                        if not utils.is_unique(type_name):
                            continue

                        tier_info = tiers.get(name, {}) or {}

                        display_name = (
                            f"{name} (Replica)"
                            if type_name and type_name.lower() == "replica"
                            else name
                        )

                        cached.append({
                            "name": display_name,
                            "base_name": name,
                            "type": type_name or "Unknown",
                            "tier": tier_info.get("tier", ""),
                            "img_url": tier_info.get("img"),
                            "wiki": tier_info.get("wiki"),
                        })

                    cached.sort(
                        key=lambda item: item["base_name"].lower()
                    )

                    CollectionPopup._cached_items = cached

        self.all_items = []

        has_collection_status = bool(collection_active)

        for cached_item in CollectionPopup._cached_items:
            item = cached_item.copy()

            tier_info = tiers.get(item["base_name"], {}) or {}

            if tier_info:
                item["tier"] = tier_info.get("tier", "")
                item["img_url"] = tier_info.get("img")
                item["wiki"] = tier_info.get("wiki")

            item["_tk_img"] = None
            item["found_count"] = 0

            if has_collection_status:
                owned = collection_active.get(
                    item["base_name"],
                    False
                )
                item["owned"] = "✔" if owned else "✖"
            else:
                item["owned"] = "?"

            price = currency.get(item["base_name"], {}) or {}
            item["chaos"] = convert_to_float(price.get("chaos"))
            item["value_text"] = self._format_chaos(item["chaos"])

            item["trade_url"] = generate_trade_url_from_values(
                item["type"],
                item["base_name"]
            )

            self.all_items.append(item)

    @staticmethod
    def _format_chaos(chaos):
        """Format a chaos amount the same way the main tree does."""
        if not chaos or chaos <= 0:
            return ""

        divine_equiv = convert_to_float(
            get_setting("Application", "divine_equivalent", 183.5)
        )

        if divine_equiv > 0 and chaos >= divine_equiv * 0.99:
            return f"{format_currency_value(chaos / divine_equiv)} Divines"

        return f"{format_currency_value(chaos)} Chaos"

    def generate_trade_url(self, item):
        return generate_trade_url_from_values(
            item.get("type"),
            item.get("base_name")
        )

    def _apply_cached_icons(self):
        for item in self.all_items:
            if item.get("_tk_img") is not None or not item.get("img_url"):
                continue

            pil_img = get_cached_icon(
                item["name"],
                (self.ICON_SIZE, self.ICON_SIZE)
            )

            if pil_img is not None:
                self._set_item_tk_image(item, pil_img)

    def _set_item_tk_image(self, item, pil_img):
        try:
            tk_img = ImageTk.PhotoImage(pil_img, master=self.parent)
        except Exception:
            return

        item["_tk_img"] = tk_img
        self._image_refs.append(tk_img)

    def _load_icons_thread(self):
        missing = [
            (item["name"], item.get("img_url"))
            for item in self.all_items
            if item.get("_tk_img") is None and item.get("img_url")
        ]

        if not missing:
            return

        loaded_icons = get_icons_parallel(
            missing,
            size=(self.ICON_SIZE, self.ICON_SIZE)
        )

        if self.parent and loaded_icons:
            try:
                self.parent.after(
                    0,
                    lambda: self._apply_loaded_icons(loaded_icons)
                )
            except Exception:
                pass

    def _tree_alive(self):
        if not hasattr(self, "tree"):
            return False

        try:
            return bool(self.tree.winfo_exists())
        except Exception:
            return False

    def _apply_loaded_icons(self, loaded_icons):
        if not self._tree_alive():
            return

        for item in self.all_items:
            pil_img = loaded_icons.get(item["name"])

            if pil_img is None:
                continue

            self._set_item_tk_image(item, pil_img)

            # Update the existing row in place rather than rebuilding the
            # whole tree (avoids flicker and losing scroll/selection).
            row_id = item.get("_row_id")
            if row_id and self.tree.exists(row_id):
                self.tree.item(row_id, image=item["_tk_img"])

    def open_link(self, event):
        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)

        if not row_id:
            return

        item = self._row_item_map.get(row_id)

        if not item:
            return

        self.tree.selection_set(row_id)

        # Name column -> Wiki
        if col == "#0":
            open_url(item.get("wiki"))
            return

        # Value column -> Trade
        if col == "#5":
            open_url(item.get("trade_url"))

    def refresh_tree(self, filtered=None):
        if not hasattr(self, "tree"):
            return

        try:
            if not self.tree.winfo_exists():
                return
        except Exception:
            return

        self.tree.delete(*self.tree.get_children())
        self._row_item_map.clear()

        for item in self.all_items:
            item["_row_id"] = None

        rows = filtered if filtered is not None else self.all_items

        for i, item in enumerate(rows):
            img = item.get("_tk_img") or self.placeholder

            row_tag = "even" if i % 2 == 0 else "odd"
            status_tag = {
                "✔": "owned",
                "✖": "missing"
            }.get(item["owned"], "unknown")


            row_id = self.tree.insert(
                "",
                "end",
                text=item["name"],
                image=img,
                values=(
                    item["type"],
                    item["tier"],
                    item["found_count"],
                    item["owned"],
                    item.get("value_text", "")
                ),
                tags=(row_tag, status_tag)
            )

            self._row_item_map[row_id] = item
            item["_row_id"] = row_id

    def _visible_items(self):
        entry = getattr(self, "search_entry", None)
        query = entry.get().lower().strip() if entry else ""
        type_filter = self.type_var.get()
        owned_filter = self.owned_var.get()
        found_only = self.found_only_var.get()

        result = []
        for item in self.all_items:
            if query and not (
                query in item["name"].lower()
                or query in str(item["type"]).lower()
                or query in str(item["tier"]).lower()
            ):
                continue
            if type_filter != self.ALL_TYPES and str(item["type"]) != type_filter:
                continue
            if owned_filter == "Owned" and item["owned"] != "✔":
                continue
            if owned_filter == "Missing" and item["owned"] != "✖":
                continue
            if found_only and not item.get("found_count"):
                continue
            result.append(item)

        return result

    def filter_items(self):
        if not self._tree_alive():
            return

        visible = self._visible_items()
        self.refresh_tree(visible)
        self._update_summary(visible)

    def _build_stat_bar(self, parent):
        P = collection_palette(self.theme_mode)

        # Single panel, square corners, thin bronze border.
        bar_frame = ctk.CTkFrame(
            parent,
            fg_color=P["panel_bg"],
            corner_radius=8,
            border_width=1,
            border_color=P["border"],
        )
        bar_frame.pack(fill="x", pady=(0, 2))

        self._cards = {}
        specs = [
            ("collection", "Collection"),
            ("owned", "Owned Value"),
            ("missing", "Missing Value"),
            ("found", "Found"),
        ]

        col = 0
        for idx, (key, title) in enumerate(specs):
            if idx > 0:
                # Vertical bronze rule between sections.
                tk.Frame(bar_frame, bg=P["border_dim"], width=1).grid(
                    row=0, column=col, sticky="ns", pady=10
                )
                col += 1

            bar_frame.grid_columnconfigure(col, weight=1, uniform="stats")

            section = ctk.CTkFrame(bar_frame, fg_color="transparent")
            section.grid(row=0, column=col, sticky="nsew", padx=14, pady=(8, 10))
            col += 1

            ctk.CTkLabel(
                section, text=title, anchor="center",
                text_color=P["gold"], font=make_font(11, "bold")
            ).pack(fill="x")

            value = ctk.CTkLabel(
                section, text="—", anchor="center", compound="left",
                text_color=P["text"], font=make_font(18, "bold")
            )
            value.pack(fill="x", pady=(2, 0))

            bar = None
            if key == "collection":
                bar = ctk.CTkProgressBar(
                    section, height=6, corner_radius=3,
                    border_width=1, border_color=P["border_dim"],
                    fg_color=P["bar_track"], progress_color=P["bar_fill"]
                )
                bar.set(0)
                bar.pack(fill="x", pady=(4, 0))

            sub = ctk.CTkLabel(
                section, text="", anchor="center",
                text_color=P["muted"], font=make_font(11)
            )
            sub.pack(fill="x")

            self._cards[key] = {"value": value, "sub": sub, "bar": bar}

        self.filtered_note = ctk.CTkLabel(
            parent, text="", anchor="e", height=18,
            text_color=P["muted"], font=make_font(11)
        )
        self.filtered_note.pack(fill="x", pady=(0, 4))

    def _set_card(self, key, value, sub="", icon=None):
        card = self._cards[key]
        # CTkLabel needs image="" (not None) to clear a previous image.
        card["value"].configure(text=value, image=icon if icon else "")
        card["sub"].configure(text=sub)

    def _value_with_icon(self, chaos):
        """Return (number text, icon) — the orb icon replaces the unit word."""
        text = self._format_chaos(chaos) or "0 Chaos"
        number, _, unit = text.rpartition(" ")
        icon = getattr(self, "_currency_icons", {}).get(unit)
        if icon is None:
            return text, None
        return f"{number} ", icon

    def _update_summary(self, visible=None):
        if not hasattr(self, "_cards") or not self._tree_alive():
            return

        if visible is None:
            visible = self._visible_items()

        total = len(visible)
        has_ownership = any(item["owned"] != "?" for item in self.all_items)

        # Collection progress
        bar = self._cards["collection"]["bar"]
        if has_ownership:
            owned = sum(1 for i in visible if i["owned"] == "✔")
            pct = (owned / total) if total else 0
            self._set_card("collection", f"{owned} / {total}", f"{pct * 100:.1f}% complete")
            bar.set(pct)
        else:
            self._set_card("collection", f"— / {total}", "ownership unknown")
            bar.set(0)

        # Values
        if has_ownership:
            owned_value = sum(i.get("chaos", 0) for i in visible if i["owned"] == "✔")
            missing_value = sum(i.get("chaos", 0) for i in visible if i["owned"] == "✖")
            text, icon = self._value_with_icon(owned_value)
            self._set_card("owned", text, "in owned items", icon)
            text, icon = self._value_with_icon(missing_value)
            self._set_card("missing", text, "to complete", icon)
        else:
            self._set_card("owned", "—", "ownership unknown")
            self._set_card("missing", "—", "ownership unknown")

        # Found
        found_unique = sum(1 for i in visible if i.get("found_count"))
        drops = sum(i.get("found_count") or 0 for i in visible)
        self._set_card("found", f"{found_unique} unique", f"{drops:,} total drops")

        if total != len(self.all_items):
            self.filtered_note.configure(text=f"Filtered from {len(self.all_items)} items")
        else:
            self.filtered_note.configure(text="")

    def _update_heading_arrows(self):
        for col, label in self.HEADINGS.items():
            if col == self._sort_column:
                arrow = " ▲" if self._sort_ascending else " ▼"
                self.tree.heading(col, text=label + arrow)
            else:
                self.tree.heading(col, text=label)

    def _selected_item(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return self._row_item_map.get(selection[0])

    def _open_selected(self, key):
        item = self._selected_item()
        if item and item.get(key):
            open_url(item.get(key))

    def _copy_selected_name(self):
        item = self._selected_item()
        if not item:
            return
        try:
            self.tree.clipboard_clear()
            self.tree.clipboard_append(item["base_name"])
        except Exception:
            pass

    def _show_context_menu(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        self.tree.selection_set(row_id)
        self.tree.focus(row_id)
        item = self._row_item_map.get(row_id) or {}

        self._context_menu.entryconfigure(
            "Open Wiki",
            state="normal" if item.get("wiki") else "disabled"
        )
        self._context_menu.entryconfigure(
            "Open Trade",
            state="normal" if item.get("trade_url") else "disabled"
        )

        try:
            self._context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._context_menu.grab_release()

    def sort_by(self, col):
        if self._sort_column == col:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_ascending = True

        if col == "#0":
            key_func = lambda x: x.get(
                "base_name",
                x["name"]
            ).lower()

        elif col == "Type":
            key_func = lambda x: str(
                x["type"]
            ).lower()

        elif col == "Tier":
            key_func = lambda x: (
                not bool(x["tier"]),
                str(x["tier"]).lower()
            )

        elif col == "Found":
            key_func = lambda x: x.get("found_count", 0)

        elif col == "Owned":
            key_func = lambda x: {
                "✔": 0,
                "✖": 1,
                "?": 2
            }.get(x["owned"], 2)

        elif col == "Value":
            key_func = lambda x: x.get("chaos", 0)

        else:
            key_func = None

        if key_func:
            self.all_items.sort(
                key=key_func,
                reverse=not self._sort_ascending
            )

            self._sort_column = col
            self._update_heading_arrows()
            # Re-apply current search/filters instead of showing everything.
            self.filter_items()

    def _load_found_counts_thread(self):
        try:
            data_mgr = getattr(self.tracker, "data_mgr", None)

            if data_mgr is None:
                return

            rows = data_mgr.load_dict()

            if not rows:
                return

            # Only count items which actually belong to this collection.
            valid_names = {
                item["base_name"]
                for item in self.all_items
            }

            counts = Counter()

            unique_columns = (
                config.csv_trinket_header,
                config.csv_replacement_header,
                config.csv_replica_header,
                config.csv_experimented_header,
                config.csv_weapon_enchant_header,
                config.csv_armor_enchant_header,
            )

            for row in rows:
                for column in unique_columns:
                    name = row.get(column)

                    if not name:
                        continue

                    name = utils.smart_title_case(str(name).strip())

                    if name in valid_names:
                        counts[name] += 1

            if self.parent:
                try:
                    self.parent.after(
                        0,
                        lambda: self._apply_found_counts(counts)
                    )
                except Exception:
                    pass

        except Exception as e:
            if config.DEBUGGING:
                print(f"[Collection] Failed to calculate found counts: {e}")

    def _apply_found_counts(self, counts):
        if not self._tree_alive():
            return

        for item in self.all_items:
            item["found_count"] = counts.get(
                item["base_name"],
                0
            )

            row_id = item.get("_row_id")
            if row_id and self.tree.exists(row_id):
                self.tree.set(row_id, "Found", item["found_count"])

        # "Found only" depends on these counts, so re-filter if it's on;
        # otherwise just refresh the summary.
        if self.found_only_var.get():
            self.filter_items()
        else:
            self._update_summary()
