import json
import threading
import urllib.parse
import webbrowser
import os

import customtkinter as ctk
from PIL import Image
from customtkinter import CTkImage

from img_utils import get_icon

TRADE_URL_BASE = "https://www.pathofexile.com/trade/search"

# ---------------- ENCHANT MAPPING ----------------
ENCHANT_MODS = {
    "enchant.stat_4168369352": "Heist Targets are always Currency or Scarabs",
    "enchant.stat_2619914138": "Heist Targets are always Replica Unique Items",
    "enchant.stat_3709545805": "Heist Targets are always Enchanted Armaments",
    "enchant.stat_1123534836": "Heist Targets are always Thieves' Trinkets",
    "enchant.stat_4182516619": "Heist Targets are always Experimented Items",
}

ENCHANT_DISPLAY = list(ENCHANT_MODS.keys())

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

# ---------------- TRADE URL | QUERY ----------------
def build_blueprint_trade_url(
    blueprint_type,
    league="Mirage",
    wings_min=4,
    wings_max=4,
    ilvl_min=83,
    ilvl_max=83,
    enchant=None,
    exclude_enchants=False
):

    stats = [
        {
            "type": "and",
            "filters": [],
            "disabled": False
        }
    ]

    # ---------------- HEIST ENCHANTS ----------------

    if enchant:
        stats.append({
            "type": "and",
            "filters": [
                {
                    "id": enchant,
                    "disabled": False
                }
            ],
            "disabled": False
        })

    elif exclude_enchants:
        stats.append({
            "type": "not",
            "filters": [
                {"id": eid, "disabled": False}
                for eid in ENCHANT_MODS.keys()
            ],
            "disabled": False
        })

    query = {
        "query": {
            "status": {
                "option": "securable"
            },

            "type": blueprint_type,

            "stats": stats,

            "filters": {
                "heist_filters": {
                    "disabled": False,
                    "filters": {
                        "heist_wings": {
                            "min": wings_min,
                            "max": wings_max
                        },
                        "heist_max_wings": {
                            "min": wings_min,
                            "max": wings_max
                        }
                    }
                },

                "misc_filters": {
                    "disabled": False,
                    "filters": {
                        "ilvl": {
                            "min": ilvl_min,
                            "max": ilvl_max
                        }
                    }
                }
            }
        },

        "sort": {
            "price": "asc"
        }
    }

    return (
        f"{TRADE_URL_BASE}/"
        f"{urllib.parse.quote(league)}"
        f"?q={urllib.parse.quote(json.dumps(query))}"
    )

# ---------------- UI ----------------

class QuickTradePopup:

    ICON_SIZE = 32
    CARD_W = 100
    CARD_H = 78

    COLLAPSED_HEIGHT = 390
    EXPANDED_HEIGHT = 640

    def __init__(self, parent):

        self.popup = ctk.CTkToplevel(parent)
        self.popup.title("Quick Trade")
        self.popup.geometry(f"500x{self.EXPANDED_HEIGHT}")
        self.popup.grab_set()

        self.main = ctk.CTkScrollableFrame(self.popup)
        self.main.pack(fill="both", expand=True, padx=8, pady=8)

        self.filters_open = True

        self.placeholder = CTkImage(
            light_image=Image.new("RGBA", (32, 32), (150, 150, 150, 255)),
            dark_image=Image.new("RGBA", (32, 32), (150, 150, 150, 255)),
            size=(32, 32)
        )

        self.icons = {}
        threading.Thread(target=self._wait_and_load_icons, daemon=True).start()

        self._build()

    # ---------------- ICON SAFE LOAD ----------------

    def _wait_and_load_icons(self):
        self.all_icons = {}

        for k, url in BLUEPRINT_ICONS.items():
            tk_img = get_icon(
                name=k,
                url=url,
                size=(self.ICON_SIZE, self.ICON_SIZE),
                placeholder=self.placeholder,
                parent=self.popup,
                return_pil=False,
            )

            self.all_icons[k] = tk_img or self.placeholder

        self.popup.after(0, self._apply_icons)

    def _apply_icons(self):
        self.icons = self.all_icons
        self._build()

    # ---------------- BUILD UI ----------------

    def _build(self):

        row = 0

        # HEADER
        header = ctk.CTkFrame(self.main, corner_radius=10)
        header.grid(row=row, column=0, sticky="ew", pady=(0, 6))

        ctk.CTkLabel(header, text="Quick Search", font=("Segoe UI", 16, "bold")).pack(
            anchor="w", padx=12, pady=(6, 0)
        )

        ctk.CTkLabel(header, text="iLvl 83 with 4/4 revealed wings", font=("Segoe UI", 10),
                     text_color=("gray45", "gray70")).pack(anchor="w", padx=12, pady=(0, 6))

        row += 1

        # GRID
        grid = ctk.CTkFrame(self.main, fg_color="transparent")
        grid.grid(row=row, column=0, sticky="ew")
        row += 1

        for i in range(3):
            grid.grid_columnconfigure(i, weight=1, uniform="tiles")

        for i, b in enumerate(BLUEPRINT_LAYOUTS):
            r, c = divmod(i, 3)

            frame = ctk.CTkFrame(
                grid,
                corner_radius=10,
                fg_color=("gray90", "gray13")
            )

            frame.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")

            icon = self.icons.get(b, self.placeholder)

            icon_label = ctk.CTkLabel(frame, text="", image=icon)
            icon_label.pack(expand=True)

            text_label = ctk.CTkLabel(
                frame,
                text=b.replace("Blueprint: ", ""),
                font=("Segoe UI", 9)
            )
            text_label.pack()

            def bind_tile(widget, name=b):
                widget.bind("<Button-1>", lambda e, n=name: self._select_blueprint(n))
                widget.configure(cursor="hand2")

            def on_enter(e, f=frame):
                f.configure(fg_color=("gray80", "gray25"))

            def on_leave(e, f=frame):
                f.configure(fg_color=("gray90", "gray13"))

            for w in (frame, icon_label, text_label):
                bind_tile(w)
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)


        # ---------------- FILTER TOGGLE ----------------

        self.toggle = ctk.CTkButton(
            self.main,
            text="Filters ▼",
            command=self._toggle_filters
        )
        self.toggle.grid(row=row, column=0, sticky="ew")
        row += 1

        # ---------------- FILTER PANEL ----------------

        self.filter_frame = ctk.CTkFrame(self.main, corner_radius=12)
        self.filter_frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        self.filter_row = row

        # Blueprint
        ctk.CTkLabel(self.filter_frame, text="Blueprint", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14)

        self.layout_var = ctk.StringVar(value=BLUEPRINT_LAYOUTS[0])

        ctk.CTkComboBox(
            self.filter_frame,
            values=BLUEPRINT_LAYOUTS,
            variable=self.layout_var
        ).pack(fill="x", padx=14, pady=(4, 10))

        # ---------------- WINGS ----------------

        ctk.CTkLabel(
            self.filter_frame,
            text="Number of revealed wings (1–4)",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", padx=14)

        w = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        w.pack(fill="x", padx=14)

        self.wings_min = ctk.CTkEntry(w, width=80)
        self.wings_max = ctk.CTkEntry(w, width=80)

        self.wings_min.insert(0, "4")
        self.wings_max.insert(0, "4")

        ctk.CTkLabel(w, text="Min").pack(side="left")
        self.wings_min.pack(side="left", padx=(5, 15))

        ctk.CTkLabel(w, text="Max").pack(side="left")
        self.wings_max.pack(side="left", padx=(5, 0))

        # ---------------- WING PRESETS ----------------

        presets = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        presets.pack(fill="x", padx=14, pady=(6, 0))

        ctk.CTkLabel(
            presets,
            text="Quick:",
            font=("Segoe UI", 10)
        ).pack(side="left", padx=(0, 6))

        for n in range(3, 5):
            ctk.CTkButton(
                presets,
                text=f"{n}/{n}",
                width=55,
                command=lambda x=n: self._set_wings(x)
            ).pack(side="left", padx=3)

        # ---------------- ILVL (REAL 50–100) ----------------

        ctk.CTkLabel(self.filter_frame, text="Item Level (50–100)", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", padx=14, pady=(10, 0)
        )

        il = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        il.pack(fill="x", padx=14)

        self.ilvl_min = ctk.CTkEntry(il)
        self.ilvl_max = ctk.CTkEntry(il)

        self.ilvl_min.insert(0, "83")

        self.ilvl_max.insert(0, "83")

        ctk.CTkLabel(il, text="Min").pack(side="left")
        self.ilvl_min.pack(side="left", padx=(5, 15))

        ctk.CTkLabel(il, text="Max").pack(side="left")
        self.ilvl_max.pack(side="left", padx=(5, 0))

        # ---------------- ENCHANT ----------------

        self.enchant_var = ctk.BooleanVar()
        self.enchant_select = ctk.StringVar()

        e = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        e.pack(fill="x", padx=14, pady=(10, 0))

        self.enchant_cb = ctk.CTkCheckBox(
            e,
            text="Enchanted",
            variable=self.enchant_var,
            command=self._toggle_enchant
        )
        self.enchant_cb.pack(side="left")

        self.enchant_menu = ctk.CTkComboBox(
            e,
            values=list(ENCHANT_MODS.values()),
            state="disabled",
            variable=self.enchant_select,
            width=280
        )
        self.enchant_menu.pack(side="left", padx=10)

        # ---------------- SEARCH ----------------

        ctk.CTkButton(
            self.filter_frame,
            text="Search",
            command=self.search
        ).pack(fill="x", padx=14, pady=10)

    # ---------------- LOGIC ----------------

    def _toggle_filters(self):

        if self.filters_open:

            self.filter_frame.grid_remove()
            self.toggle.configure(text="Filters ▶")

            self.popup.geometry(f"500x{self.COLLAPSED_HEIGHT}")

        else:

            self.filter_frame.grid(
                row=self.filter_row,
                column=0,
                sticky="ew",
                pady=(0, 10)
            )

            self.toggle.configure(text="Filters ▼")

            self.popup.geometry(f"500x{self.EXPANDED_HEIGHT}")

        self.filters_open = not self.filters_open

    def _toggle_enchant(self):
        self.enchant_menu.configure(state="normal" if self.enchant_var.get() else "disabled")

    def _wmin(self, v):
        v = int(round(v))
        self.wmin_val.configure(text=str(v))

    def _wmax(self, v):
        v = int(round(v))
        self.wmax_val.configure(text=str(v))

    def search(self):
        try:
            wings_min = int(self.wings_min.get())
            wings_max = int(self.wings_max.get())
        except:
            wings_min = wings_max = 4

        enchant_text = self.enchant_select.get()

        enchant = None
        for k, v in ENCHANT_MODS.items():
            if v == enchant_text:
                enchant = k
                break

        url = build_blueprint_trade_url(
            self.layout_var.get(),
            wings_min=wings_min,
            wings_max=wings_max,
            ilvl_min=int(self.ilvl_min.get()),
            ilvl_max=int(self.ilvl_max.get()),
            enchant=enchant if self.enchant_var.get() else None,
            exclude_enchants=not self.enchant_var.get()
        )
        webbrowser.open(url)

    def _select_blueprint(self, blueprint):

        # Quick-search defaults
        self.layout_var.set(blueprint)

        self.wings_min.delete(0, "end")
        self.wings_max.delete(0, "end")

        self.wings_min.insert(0, "4")
        self.wings_max.insert(0, "4")

        self.ilvl_min.delete(0, "end")
        self.ilvl_max.delete(0, "end")

        self.ilvl_min.insert(0, "83")
        self.ilvl_max.insert(0, "83")

        self._open_search()

    def _open_search(self):
        try:
            wings_min = int(self.wings_min.get())
            wings_max = int(self.wings_max.get())
        except:
            wings_min = wings_max = 4

        enchant = None

        if self.enchant_var.get():

            enchant_text = self.enchant_select.get()

            for k, v in ENCHANT_MODS.items():
                if v == enchant_text:
                    enchant = k
                    break

        url = build_blueprint_trade_url(
            self.layout_var.get(),
            wings_min=wings_min,
            wings_max=wings_max,
            ilvl_min=int(self.ilvl_min.get()),
            ilvl_max=int(self.ilvl_max.get()),
            enchant=enchant,
            exclude_enchants=not self.enchant_var.get()
        )

        webbrowser.open(url)

    def _set_wings(self, value):
        self.wings_min.delete(0, "end")
        self.wings_max.delete(0, "end")

        self.wings_min.insert(0, str(value))
        self.wings_max.insert(0, str(value))

def show_quick_trade_popup(parent):
    QuickTradePopup(parent)