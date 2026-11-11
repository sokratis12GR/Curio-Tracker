import threading

import customtkinter as ctk
from PIL import Image

from blueprint_data import BlueprintIndex, CATEGORIES, load_blueprint_info, refresh_blueprint_info
from fonts import make_font
from gui.palette import POE_PALETTE, themed
from img_utils import get_cached_icon, get_icons_parallel
from win_utils import center_window_on_parent, prepare_popup

CATEGORY_LABELS = {
    "locations": "Locations",
    "jobs": "Jobs",
    "chest_types": "Chest Types",
    "mechanics": "Mechanics",
}
CATEGORY_SINGULAR = {
    "locations": "Blueprint Location",
    "jobs": "Heist Job",
    "chest_types": "Reward Chest Type",
    "mechanics": "Mechanic",
}
LABEL_TO_CATEGORY = {v: k for k, v in CATEGORY_LABELS.items()}

DAMAGE_COLORS = {
    "physical": ("#8a6d3b", "#9c7c45"),
    "fire": ("#c0392b", "#c2452f"),
    "cold": ("#2e7fb8", "#3b82b0"),
    "lightning": ("#a8870a", "#b39316"),
    "chaos": ("#8e44ad", "#8e4aa8"),
}

LIST_ICON = 24
CHIP_ICON = 18
HEADER_ICON = 56

CARD_COLOR = themed(("#f4f6f8", "#2b2d31"), POE_PALETTE["panel_bg"])
LIST_COLOR = themed(("#eceff2", "#232428"), POE_PALETTE["window_bg"])
SELECTED_COLOR = themed(("#d0d7e2", "#3a3d44"), POE_PALETTE["select_bg"])
HOVER_COLOR = themed(("#dfe4ea", "#313338"), POE_PALETTE["header_bg"])
CHIP_COLOR = themed(("#e3e7ec", "#383a40"), POE_PALETTE["border_dim"])
CHIP_HOVER = themed(("#cfd6df", "#45474f"), POE_PALETTE["border"])
MUTED_TEXT = themed(("gray35", "gray65"), POE_PALETTE["muted"])

DETAIL_WRAP = 560
CHIPS_PER_ROW = 3


class BlueprintEncyclopediaPopup:
    def __init__(self, parent=None, tracker=None, title="Blueprint Encyclopedia"):
        self.parent = parent
        self.tracker = tracker
        self.title = title

        self.index = BlueprintIndex(load_blueprint_info())

        self.search_var = ctk.StringVar()
        self.category = "locations"
        self.selected = None  # (category, name)

        self._list_buttons = {}
        self._ctk_icons = {}
        self._blank = {}
        self._search_after = None
        self._row = 0

    # ------------------------------------------------------------------ icons

    def _blank_icon(self, size):
        if size not in self._blank:
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            self._blank[size] = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        return self._blank[size]

    @staticmethod
    def _icon_key(category, name):
        return f"Heist {category} - {name}"

    def _icon(self, category, name, size):
        """CTkImage for an entry if it's loaded, else a transparent spacer."""
        key = (category, name, size)
        if key in self._ctk_icons:
            return self._ctk_icons[key]

        pil_img = get_cached_icon(self._icon_key(category, name), (size, size))
        if pil_img is None:
            return self._blank_icon(size)

        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(size, size))
        self._ctk_icons[key] = ctk_img
        return ctk_img

    def _icon_requests(self):
        requests = []
        for category in CATEGORIES:
            for entry in self.index.entries[category]:
                url = self.index.icon_url(category, entry["name"])
                if url:
                    requests.append((self._icon_key(category, entry["name"]), url))
        return requests

    def _load_icons_thread(self):
        requests = self._icon_requests()
        for size in (LIST_ICON, CHIP_ICON, HEADER_ICON):
            get_icons_parallel(requests, size=(size, size))

        self._after(self._on_icons_loaded)

    def _on_icons_loaded(self):
        self._ctk_icons.clear()
        for (category, name), button in self._list_buttons.items():
            try:
                button.configure(image=self._icon(category, name, LIST_ICON))
            except Exception:
                pass
        self._render_detail()

    def _after(self, callback):
        try:
            if self.popup.winfo_exists():
                self.popup.after(0, callback)
        except Exception:
            pass

    # ---------------------------------------------------------------- remote

    def _refresh_remote_thread(self):
        data = refresh_blueprint_info()
        if data is None:
            return

        def _apply():
            self.index = BlueprintIndex(data)
            if self.selected and self.selected[1] not in self.index.by_name.get(self.selected[0], {}):
                self.selected = None
            self._rebuild_list()
            self._render_detail()
            threading.Thread(target=self._load_icons_thread, daemon=True).start()

        self._after(_apply)

    # -------------------------------------------------------------------- UI

    def show(self):
        popup = ctk.CTkToplevel(self.parent)
        prepare_popup(popup)
        self.popup = popup
        popup.title(self.title)
        popup.geometry("960x620")
        popup.resizable(False, False)
        popup.transient(self.parent.winfo_toplevel())
        popup.bind("<Escape>", lambda e: popup.destroy())

        popup.grid_columnconfigure(1, weight=1)
        popup.grid_rowconfigure(1, weight=1)

        # --- Top bar: categories + search ---
        top = ctk.CTkFrame(popup, fg_color="transparent")
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8))
        top.grid_columnconfigure(1, weight=1)

        self.category_switch = ctk.CTkSegmentedButton(
            top,
            values=[CATEGORY_LABELS[c] for c in CATEGORIES],
            command=self._on_category,
        )
        self.category_switch.set(CATEGORY_LABELS[self.category])
        self.category_switch.grid(row=0, column=0, sticky="w")

        search = ctk.CTkEntry(
            top,
            placeholder_text="Search everything (e.g. Currency, Lockpicking, Fire)...",
            textvariable=self.search_var,
        )
        search.grid(row=0, column=1, sticky="ew", padx=(12, 0))
        self.search_var.trace_add("write", lambda *_: self._schedule_search())

        # --- Left list ---
        self.list_frame = ctk.CTkScrollableFrame(popup, width=230, fg_color=LIST_COLOR, corner_radius=10)
        self.list_frame.grid(row=1, column=0, sticky="nsw", padx=(12, 6), pady=(0, 12))
        self.list_frame.grid_columnconfigure(0, weight=1)

        # --- Right detail card ---
        self.detail_frame = ctk.CTkScrollableFrame(popup, fg_color=CARD_COLOR, corner_radius=10)
        self.detail_frame.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 12))
        self.detail_frame.grid_columnconfigure(0, weight=1)

        self._rebuild_list()

        center_window_on_parent(popup, self.parent)

        threading.Thread(target=self._load_icons_thread, daemon=True).start()
        threading.Thread(target=self._refresh_remote_thread, daemon=True).start()

        popup.grab_set()
        popup.focus_force()
        popup.wait_window()

    # ------------------------------------------------------------------ list

    def _on_category(self, label):
        self.category = LABEL_TO_CATEGORY.get(label, "locations")
        if self.search_var.get():
            self.search_var.set("")  # schedules a rebuild
        else:
            self._rebuild_list()

    def _schedule_search(self):
        # Debounce so typing doesn't rebuild the list on every keystroke.
        if self._search_after is not None:
            try:
                self.popup.after_cancel(self._search_after)
            except Exception:
                pass
        self._search_after = self.popup.after(150, self._rebuild_list)

    def _matches(self, category, entry, query):
        if not query:
            return True
        haystack = [entry.get("name", ""), entry.get("description", ""), entry.get("drops", ""),
                    entry.get("monsters", "")]
        for key in ("jobs", "chest_types", "damage", "tips"):
            haystack.extend(entry.get(key) or [])
        if category == "chest_types":
            haystack.extend(self.index.jobs_for_chest.get(entry["name"], []))
        return any(query in str(text).lower() for text in haystack)

    def _rebuild_list(self):
        self._search_after = None
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._list_buttons.clear()

        query = self.search_var.get().strip().lower()
        categories = CATEGORIES if query else (self.category,)

        row = 0
        first = None
        for category in categories:
            entries = [e for e in self.index.entries[category] if self._matches(category, e, query)]
            if not entries:
                continue

            if query:
                ctk.CTkLabel(
                    self.list_frame,
                    text=CATEGORY_LABELS[category].upper(),
                    font=make_font(9, "bold"),
                    text_color=MUTED_TEXT,
                    anchor="w",
                ).grid(row=row, column=0, sticky="ew", padx=8, pady=(8 if row else 2, 2))
                row += 1

            for entry in entries:
                key = (category, entry["name"])
                first = first or key
                button = ctk.CTkButton(
                    self.list_frame,
                    text=entry["name"],
                    image=self._icon(category, entry["name"], LIST_ICON),
                    compound="left",
                    anchor="w",
                    height=34,
                    corner_radius=6,
                    font=make_font(11),
                    text_color=("gray10", "gray90"),
                    fg_color=SELECTED_COLOR if key == self.selected else "transparent",
                    hover_color=HOVER_COLOR,
                    command=lambda k=key: self.select(*k),
                )
                button.grid(row=row, column=0, sticky="ew", padx=4, pady=1)
                self._list_buttons[key] = button
                row += 1

        if first is None:
            ctk.CTkLabel(self.list_frame, text="No matches", text_color=MUTED_TEXT).grid(
                row=0, column=0, pady=20
            )
            return

        if self.selected in self._list_buttons:
            self._render_detail()
        else:
            self.select(*first)

    def select(self, category, name):
        previous = self.selected
        self.selected = (category, name)

        if previous in self._list_buttons:
            self._list_buttons[previous].configure(fg_color="transparent")

        if self.selected not in self._list_buttons and not self.search_var.get():
            # Navigated via a chip to another category.
            self.category = category
            self.category_switch.set(CATEGORY_LABELS[category])
            self._rebuild_list()
            return

        if self.selected in self._list_buttons:
            self._list_buttons[self.selected].configure(fg_color=SELECTED_COLOR)

        self._render_detail()

    # ---------------------------------------------------------------- detail

    def _render_detail(self):
        for child in self.detail_frame.winfo_children():
            child.destroy()

        if not self.selected:
            return

        category, name = self.selected
        entry = self.index.by_name.get(category, {}).get(name)
        if entry is None:
            return

        self._row = 0
        self._header(category, entry)

        if category == "locations":
            self._chips_section("Jobs", "jobs", entry.get("jobs"))
            self._chips_section("Possible reward chests", "chest_types",
                                self.index.chests_for_location.get(name))
            self._text_section("Monsters", entry.get("monsters"))
            self._damage_section(entry.get("damage"))
        elif category == "jobs":
            self._chips_section("Opens reward chests", "chest_types", entry.get("chest_types"))
            self._chips_section("Found in", "locations", self.index.locations_for_job.get(name))
        elif category == "chest_types":
            self._text_section("Typical drops", entry.get("drops"))
            self._chips_section("Opened by", "jobs", self.index.jobs_for_chest.get(name))
            self._best_locations_section(name)
        elif category == "mechanics":
            self._bullets_section("Tips", entry.get("tips"))

        try:
            self.detail_frame._parent_canvas.yview_moveto(0)
        except Exception:
            pass

    def _next_row(self):
        row = self._row
        self._row += 1
        return row

    def _header(self, category, entry):
        header = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        header.grid(row=self._next_row(), column=0, sticky="ew", padx=16, pady=(16, 8))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="", image=self._icon(category, entry["name"], HEADER_ICON)).grid(
            row=0, column=0, rowspan=2, padx=(0, 14)
        )
        ctk.CTkLabel(header, text=entry["name"], font=make_font(18, "bold"), anchor="w").grid(
            row=0, column=1, sticky="sw"
        )
        ctk.CTkLabel(header, text=CATEGORY_SINGULAR[category], font=make_font(10),
                     text_color=MUTED_TEXT, anchor="w").grid(row=1, column=1, sticky="nw")

        description = entry.get("description")
        if description:
            ctk.CTkLabel(
                self.detail_frame, text=description, font=make_font(11),
                wraplength=DETAIL_WRAP, justify="left", anchor="w",
            ).grid(row=self._next_row(), column=0, sticky="ew", padx=16, pady=(0, 6))

        ctk.CTkFrame(self.detail_frame, height=1, fg_color=("gray75", "gray30")).grid(
            row=self._next_row(), column=0, sticky="ew", padx=16, pady=(4, 4)
        )

    def _section_title(self, text):
        ctk.CTkLabel(self.detail_frame, text=text, font=make_font(12, "bold"), anchor="w").grid(
            row=self._next_row(), column=0, sticky="ew", padx=16, pady=(12, 4)
        )

    def _text_section(self, title, text):
        if not text:
            return
        self._section_title(title)
        ctk.CTkLabel(
            self.detail_frame, text=text, font=make_font(11),
            wraplength=DETAIL_WRAP, justify="left", anchor="w",
        ).grid(row=self._next_row(), column=0, sticky="ew", padx=16)

    def _bullets_section(self, title, items):
        if not items:
            return
        self._text_section(title, "\n".join(f"•  {item}" for item in items))

    def _chip_grid(self):
        grid = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        grid.grid(row=self._next_row(), column=0, sticky="ew", padx=12)
        for col in range(CHIPS_PER_ROW):
            grid.grid_columnconfigure(col, weight=1, uniform="chips")
        return grid

    def _chips_section(self, title, target_category, names, suffixes=None):
        names = [n for n in (names or []) if n]
        if not names:
            return

        self._section_title(title)
        grid = self._chip_grid()
        known = self.index.by_name.get(target_category, {})

        for i, name in enumerate(names):
            r, c = divmod(i, CHIPS_PER_ROW)
            label = f"{name}  ({suffixes[name]})" if suffixes and name in suffixes else name
            clickable = name in known
            ctk.CTkButton(
                grid,
                text=label,
                image=self._icon(target_category, name, CHIP_ICON),
                compound="left",
                anchor="w",
                height=30,
                corner_radius=15,
                font=make_font(10),
                text_color=("gray10", "gray90"),
                fg_color=CHIP_COLOR,
                hover_color=CHIP_HOVER if clickable else CHIP_COLOR,
                command=(lambda n=name: self.select(target_category, n)) if clickable else None,
            ).grid(row=r, column=c, sticky="ew", padx=4, pady=3)

    def _damage_section(self, damage_types):
        damage_types = [d for d in (damage_types or []) if d]
        if not damage_types:
            return

        self._section_title("Damage types")
        row = ctk.CTkFrame(self.detail_frame, fg_color="transparent")
        row.grid(row=self._next_row(), column=0, sticky="w", padx=12)

        for damage in damage_types:
            color = DAMAGE_COLORS.get(damage.lower(), CHIP_COLOR)
            ctk.CTkLabel(
                row, text=damage, font=make_font(10, "bold"), text_color="white",
                fg_color=color, corner_radius=12, height=26, width=90,
            ).pack(side="left", padx=4, pady=3)

    def _best_locations_section(self, chest_name):
        ranked = self.index.best_locations_for_chest(chest_name)
        if not ranked:
            return

        suffixes = {
            name: f"{count} job{'s' if count != 1 else ''}"
            for name, count in ranked
        }
        self._chips_section("Best blueprints for this chest", "locations",
                            [name for name, _ in ranked], suffixes=suffixes)
        ctk.CTkLabel(
            self.detail_frame,
            text="Ranked by how many of the blueprint's jobs can open this chest type.",
            font=make_font(9), text_color=MUTED_TEXT, anchor="w",
        ).grid(row=self._next_row(), column=0, sticky="ew", padx=16, pady=(2, 12))


def show_blueprint_encyclopedia_popup(parent, tracker=None):
    BlueprintEncyclopediaPopup(parent=parent, tracker=tracker).show()
