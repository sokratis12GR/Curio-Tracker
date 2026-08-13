import threading
from collections import Counter
from link_utils import generate_trade_url_from_values, open_url

import customtkinter as ctk
from tkinter import ttk
from PIL import Image, ImageTk

import config
import ocr_utils as utils
from img_utils import get_icon


class CollectionPopup:
    ICON_SIZE = 24  # icon width/height

    _cached_items = None
    _cache_lock = threading.Lock()

    def __init__(self, parent=None, tracker=None, title="Collection"):
        self.parent = parent
        self.tracker = tracker
        self.title = title
        self.search_var = ctk.StringVar()
        self.all_items = []

        self._row_item_map = {}

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
        self._sort_column = "#0"
        self._sort_ascending = True

    def show(self):
        popup = ctk.CTkToplevel(self.parent)
        popup.title(self.title)
        popup.minsize(750, 400)

        main_frame = ctk.CTkFrame(popup)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        league_name = getattr(self.tracker, "league_version", "")
        popup.title(f"{self.title} - {league_name}")

        search_entry = ctk.CTkEntry(
            main_frame,
            placeholder_text="Search...",
            textvariable=self.search_var
        )
        search_entry.pack(fill="x", pady=(0, 10))
        self.search_var.trace_add("write", lambda *args: self.filter_items())

        columns = ("Type", "Tier", "Found", "Owned", "Wiki", "Trade")

        self.tree = ttk.Treeview(
            main_frame,
            columns=columns,
            show="tree headings",
            height=20
        )

        self.tree.bind("<Double-1>", self.open_link)
        self.tree.bind("<Motion>", self.on_hover)

        self.tree.heading("#0", text="Name", command=lambda: self.sort_by("#0"))
        self.tree.column("#0", width=250, anchor="w")

        self.tree.heading("Type", text="Type", command=lambda: self.sort_by("Type"))
        self.tree.column("Type", width=90, anchor="center")

        self.tree.heading("Tier", text="Tier", command=lambda: self.sort_by("Tier"))
        self.tree.column("Tier", width=70, anchor="center")

        self.tree.heading("Found", text="Found", command=lambda: self.sort_by("Found"))
        self.tree.column("Found", width=65, anchor="center")

        self.tree.heading("Owned", text="Owned", command=lambda: self.sort_by("Owned"))
        self.tree.column("Owned", width=60, anchor="center")

        self.tree.heading("Wiki", text="Wiki")
        self.tree.column("Wiki", width=80, anchor="center")

        self.tree.heading("Trade", text="Trade")
        self.tree.column("Trade", width=80, anchor="center")

        scrollbar = ttk.Scrollbar(
            main_frame,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Vertical.TScrollbar",
            troughcolor="#2f3136",
            background="#5865f2",
            arrowcolor="#dcddde",
            bordercolor="#2f3136",
            relief="flat"
        )

        scrollbar.configure(style="Vertical.TScrollbar")

        # Build the collection immediately from already-loaded terms.json.
        self.load_items()

        # Names appear immediately.
        self.refresh_tree()

        threading.Thread(
            target=self._load_icons_thread,
            daemon=True
        ).start()

        threading.Thread(
            target=self._load_found_counts_thread,
            daemon=True
        ).start()

        # Center popup
        popup.update_idletasks()

        w, h = popup.winfo_width(), popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (w // 2)
        y = (popup.winfo_screenheight() // 2) - (h // 2)

        popup.geometry(f"{w}x{h}+{x}+{y}")

        popup.grab_set()
        popup.focus_force()
        popup.wait_window()

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

        # #0 = Name
        # #5 = Wiki
        # #6 = Trade
        if col in ("#0", "#5") and item.get("wiki"):
            self.tree.config(cursor="hand2")
        elif col == "#6" and item.get("trade_url"):
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

            item["trade_url"] = generate_trade_url_from_values(
                item["type"],
                item["base_name"]
            )

            self.all_items.append(item)

    def generate_trade_url(self, item):
        return generate_trade_url_from_values(
            item.get("type"),
            item.get("base_name")
        )

    def _load_icons_thread(self):
        loaded_icons = []

        for item in self.all_items:
            try:
                pil_img = get_icon(
                    name=item["name"],
                    url=item.get("img_url"),
                    size=(self.ICON_SIZE, self.ICON_SIZE),
                    placeholder=None,
                    parent=None,
                    return_pil=True,
                )

                if pil_img is not None:
                    loaded_icons.append(
                        (item["base_name"], pil_img)
                    )

            except Exception:
                continue

        if self.parent:
            try:
                self.parent.after(
                    0,
                    lambda: self._apply_loaded_icons(loaded_icons)
                )
            except Exception:
                pass

    def _apply_loaded_icons(self, loaded_icons):
        if not hasattr(self, "tree"):
            return

        try:
            if not self.tree.winfo_exists():
                return
        except Exception:
            return

        icon_lookup = {
            base_name: pil_img
            for base_name, pil_img in loaded_icons
        }

        for item in self.all_items:
            pil_img = icon_lookup.get(item["base_name"])

            if pil_img is None:
                continue

            try:
                tk_img = ImageTk.PhotoImage(
                    pil_img,
                    master=self.parent
                )

                item["_tk_img"] = tk_img
                self._image_refs.append(tk_img)

            except Exception:
                continue

        self.refresh_tree()

    def open_link(self, event):
        row_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)

        if not row_id:
            return

        item = self._row_item_map.get(row_id)

        if not item:
            return

        self.tree.selection_set(row_id)

        # Name or Wiki column -> Wiki
        if col in ("#0", "#5"):
            open_url(item.get("wiki"))
            return

        # Trade column -> Trade
        if col == "#6":
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

        rows = filtered if filtered is not None else self.all_items

        for i, item in enumerate(rows):
            img = item.get("_tk_img") or self.placeholder

            bg_color = "#2f3136" if i % 2 == 0 else "#383c42"

            wiki_text = "Open" if item.get("wiki") else ""
            trade_text = "Open" if item.get("trade_url") else ""

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
                    wiki_text,
                    trade_text
                ),
                tags=(f"row{i}",)
            )

            self._row_item_map[row_id] = item

            self.tree.tag_configure(
                f"row{i}",
                background=bg_color,
                foreground="#dcddde"
            )

    def filter_items(self):
        query = self.search_var.get().lower().strip()

        filtered = [
            item
            for item in self.all_items
            if query in item["name"].lower()
               or query in str(item["type"]).lower()
               or query in str(item["tier"]).lower()
               or query in str(item["found_count"]).lower()
               or query in item["owned"].lower()
        ]

        self.refresh_tree(filtered)

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

        else:
            key_func = None

        if key_func:
            self.all_items.sort(
                key=key_func,
                reverse=not self._sort_ascending
            )

            self._sort_column = col
            self.refresh_tree()

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
        if not hasattr(self, "tree"):
            return

        try:
            if not self.tree.winfo_exists():
                return
        except Exception:
            return

        for item in self.all_items:
            item["found_count"] = counts.get(
                item["base_name"],
                0
            )

        self.refresh_tree()