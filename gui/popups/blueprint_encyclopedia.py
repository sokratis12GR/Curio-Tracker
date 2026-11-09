from tkinter import ttk

import customtkinter as ctk

from fonts import make_font
from settings import get_setting
from win_utils import center_window_on_parent

# Sourced from https://www.poewiki.net/wiki/Heist and https://www.poewiki.net/wiki/Blueprint
LOCATIONS = [
    {
        "name": "Bunker",
        "jobs": "Agility, Counter-thaumaturgy, Engineering, Demolition, Lockpicking, Perception, Trap disarmament",
        "monster_type": "Templars",
        "damage_type": "Physical, Lightning",
    },
    {
        "name": "Records Office",
        "jobs": "Brute force, Counter-thaumaturgy, Deception, Demolition, Lockpicking, Trap disarmament",
        "monster_type": "",
        "damage_type": "",
    },
    {
        "name": "Mansion",
        "jobs": "Agility, Brute force, Deception, Lockpicking, Perception",
        "monster_type": "",
        "damage_type": "",
    },
    {
        "name": "Smuggler's Den",
        "jobs": "Brute force, Deception, Demolition, Perception, Trap disarmament",
        "monster_type": "Smuggler",
        "damage_type": "Physical, Fire",
    },
    {
        "name": "Underbelly",
        "jobs": "Agility, Brute force, Deception, Demolition, Engineering",
        "monster_type": "",
        "damage_type": "",
    },
    {
        "name": "Laboratory",
        "jobs": "Counter-thaumaturgy, Engineering, Deception, Demolition, Perception",
        "monster_type": "Scientists",
        "damage_type": "Physical, Chaos",
    },
    {
        "name": "Prohibited Library",
        "jobs": "Counter-thaumaturgy, Deception, Engineering, Lockpicking, Perception",
        "monster_type": "",
        "damage_type": "",
    },
    {
        "name": "Repository",
        "jobs": "Agility, Demolition, Lockpicking, Perception, Trap disarmament",
        "monster_type": "Constructs",
        "damage_type": "Physical, Fire, Cold",
    },
    {
        "name": "Tunnels",
        "jobs": "Agility, Brute force, Counter-thaumaturgy, Demolition, Engineering, Trap disarmament",
        "monster_type": "",
        "damage_type": "",
    },
]

JOBS = [
    {"name": "Lockpicking", "chest_types": "Currency, Map Fragments, Jewellery"},
    {"name": "Counter-thaumaturgy", "chest_types": "Currency, Gems, Jewellery"},
    {"name": "Trap disarmament", "chest_types": "Currency, Armour, Weapons, Gold"},
    {"name": "Deception", "chest_types": "Divination Cards, Armour"},
    {"name": "Agility", "chest_types": "Armour, Essences"},
    {"name": "Perception", "chest_types": "Divination Cards, Jewellery, Random"},
    {"name": "Engineering", "chest_types": "Maps, Uniques, Essences, Random"},
    {"name": "Brute force", "chest_types": "Uniques, Weapons"},
    {"name": "Demolition", "chest_types": "Delirium, Blight, Random"},
]

CHEST_TYPES = [
    {"name": "Currency", "typical_drops": "Basic currency", "skill": "Lockpicking, Counter-thaumaturgy, Trap disarmament"},
    {"name": "Divination Cards", "typical_drops": "2x Stacked Decks, Divination Scarabs", "skill": "Deception, Perception"},
    {"name": "Maps", "typical_drops": "Maps, basic currency usable with maps, Cartography Scarabs", "skill": "Engineering"},
    {"name": "Map Fragments", "typical_drops": "Scarabs, Sacrifice/Offering fragments, small chance for valuable map fragments", "skill": "Lockpicking"},
    {"name": "Gems", "typical_drops": "Skill gems (may have levels/quality), Gemcutter's Prisms", "skill": "Counter-thaumaturgy"},
    {"name": "Uniques", "typical_drops": "Unique items, Titanic Scarabs", "skill": "Brute force, Engineering"},
    {"name": "Jewellery", "typical_drops": "Rings, amulets, jewels, belts (some veiled/fractured/corrupted/influenced), jewellery divination cards", "skill": "Lockpicking, Perception, Counter-thaumaturgy"},
    {"name": "Armour", "typical_drops": "Armour (some veiled/fractured/20% quality/influenced/unique), armour divination cards and currency", "skill": "Deception, Agility, Trap disarmament"},
    {"name": "Weapons", "typical_drops": "Weapons (some veiled/fractured/20% quality/influenced/unique), weapon divination cards and currency", "skill": "Brute force, Trap disarmament"},
    {"name": "Delirium", "typical_drops": "Simulacrum Splinters, cluster jewels, delirium orbs, maps with delirium layers", "skill": "Demolition"},
    {"name": "Gold", "typical_drops": "Gold", "skill": "Trap disarmament"},
    {"name": "Blight", "typical_drops": "Oils, Blighted Maps, Blight Scarabs, maps with a Blight encounter", "skill": "Demolition"},
    {"name": "Essences", "typical_drops": "Essences, Essence Scarabs", "skill": "Engineering, Agility"},
    {"name": "Random", "typical_drops": "Items that can drop from any reward chest type", "skill": "Demolition, Engineering, Perception"},
]

MECHANICS = [
    {
        "name": "Infiltration",
        "description": "Initial phase. A few guards and patrols are present. Opening chests raises the Alert Level.",
    },
    {
        "name": "Imminent Lockdown",
        "description": "Starts once Alert is maxed. A countdown (default 22s) begins before Lockdown; opening chests during this phase reduces the timer by 3s.",
    },
    {
        "name": "Lockdown",
        "description": "Triggered once the target is taken or the countdown expires. More enemies spawn, unopened chests lock, and some doors/obstacles rearm.",
    },
    {
        "name": "Revealing wings/rooms",
        "description": "Blueprints start with only one wing revealed. Whakano, Niles, or Gianna can use Blueprint Reveals plus Rogue's Markers to reveal more wings and reward rooms before planning.",
    },
]


class BlueprintEncyclopediaPopup:
    def __init__(self, parent=None, tracker=None, title="Blueprint Encyclopedia"):
        self.parent = parent
        self.tracker = tracker
        self.title = title
        self.search_var = ctk.StringVar()

        self.theme_mode = str(
            get_setting("Application", "theme_mode", "DARK")
        ).upper()

        self.tree_bg = None
        self.tree_alt_bg = None
        self.tree_fg = None

    def show(self):
        popup = ctk.CTkToplevel(self.parent)
        popup.title(self.title)

        popup.geometry("800x600")
        popup.minsize(700, 400)
        popup.resizable(False, False)
        popup.transient(self.parent.winfo_toplevel())

        main_frame = ctk.CTkFrame(popup)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        search_entry = ctk.CTkEntry(
            main_frame,
            placeholder_text="Search...",
            textvariable=self.search_var
        )
        search_entry.pack(fill="x", pady=(0, 10))
        self.search_var.trace_add("write", lambda *args: self.filter_tree())

        columns = ("Info",)

        self._apply_tree_theme()

        self.tree = ttk.Treeview(
            main_frame,
            columns=columns,
            show="tree headings",
            height=24,
            style="Encyclopedia.Treeview"
        )

        self.tree.heading("#0", text="Name")
        self.tree.column("#0", width=220, anchor="w")

        self.tree.heading("Info", text="Details")
        self.tree.column("Info", width=500, anchor="w")

        scrollbar = ttk.Scrollbar(
            main_frame,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        scrollbar.configure(style="Encyclopedia.Vertical.TScrollbar")

        self.refresh_tree()

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

        if self.theme_mode == "DARK":
            bg = "#2f3136"
            alt_bg = "#383c42"
            fg = "#dcddde"
            sel_bg = "#5865f2"
            sel_fg = "#ffffff"

            heading_bg = "#40444b"
            heading_fg = "#dcddde"

            border_color = "#40444b"

            scrollbar_bg = "#5865f2"
            scrollbar_trough = "#2f3136"
            scrollbar_arrow = "#dcddde"

        else:
            bg = "#ffffff"
            alt_bg = "#f0f1f3"
            fg = "#202124"
            sel_bg = "#0078d7"
            sel_fg = "#ffffff"

            heading_bg = "#f5f5f5"
            heading_fg = "#202124"

            border_color = "#d6d6d6"

            scrollbar_bg = "#c7c7c7"
            scrollbar_trough = "#f0f0f0"
            scrollbar_arrow = "#404040"

        self.tree_bg = bg
        self.tree_alt_bg = alt_bg
        self.tree_fg = fg

        style.configure(
            "Encyclopedia.Treeview",
            background=bg,
            fieldbackground=bg,
            foreground=fg,
            rowheight=28,
            font=make_font(10),
            borderwidth=1,
            relief="solid"
        )

        style.map(
            "Encyclopedia.Treeview",
            background=[("selected", sel_bg)],
            foreground=[("selected", sel_fg)]
        )

        style.configure(
            "Encyclopedia.Treeview.Heading",
            background=heading_bg,
            foreground=heading_fg,
            font=make_font(10, "bold"),
            borderwidth=1,
            relief="solid"
        )

        style.map(
            "Encyclopedia.Treeview.Heading",
            background=[
                ("active", heading_bg),
                ("pressed", heading_bg)
            ],
            foreground=[
                ("active", heading_fg),
                ("pressed", heading_fg)
            ]
        )

        style.configure(
            "Encyclopedia.Vertical.TScrollbar",
            troughcolor=scrollbar_trough,
            background=scrollbar_bg,
            arrowcolor=scrollbar_arrow,
            bordercolor=border_color,
            relief="flat"
        )

    def _build_categories(self, query=""):
        categories = [
            (
                "Blueprint Locations",
                [
                    (
                        entry["name"],
                        ", ".join(
                            part for part in (
                                f"Jobs: {entry['jobs']}" if entry["jobs"] else "",
                                f"Monsters: {entry['monster_type']}" if entry["monster_type"] else "",
                                f"Damage: {entry['damage_type']}" if entry["damage_type"] else "",
                            ) if part
                        )
                    )
                    for entry in LOCATIONS
                ]
            ),
            (
                "Heist Jobs",
                [
                    (entry["name"], f"Chest types: {entry['chest_types']}")
                    for entry in JOBS
                ]
            ),
            (
                "Reward Chest Types",
                [
                    (entry["name"], f"{entry['typical_drops']} (Skill: {entry['skill']})")
                    for entry in CHEST_TYPES
                ]
            ),
            (
                "Mechanics",
                [
                    (entry["name"], entry["description"])
                    for entry in MECHANICS
                ]
            ),
        ]

        if not query:
            return categories

        filtered = []

        for category_name, entries in categories:
            matching_entries = [
                (name, info)
                for name, info in entries
                if query in name.lower() or query in info.lower()
            ]

            if matching_entries:
                filtered.append((category_name, matching_entries))

        return filtered

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())

        query = self.search_var.get().lower().strip()

        for category_name, entries in self._build_categories(query):
            category_id = self.tree.insert(
                "",
                "end",
                text=category_name,
                open=True
            )

            for i, (name, info) in enumerate(entries):
                row_tag = "even" if i % 2 == 0 else "odd"

                self.tree.insert(
                    category_id,
                    "end",
                    text=name,
                    values=(info,),
                    tags=(row_tag,)
                )

        self.tree.tag_configure(
            "even",
            background=self.tree_bg,
            foreground=self.tree_fg
        )

        self.tree.tag_configure(
            "odd",
            background=self.tree_alt_bg,
            foreground=self.tree_fg
        )

    def filter_tree(self):
        self.refresh_tree()


def show_blueprint_encyclopedia_popup(parent, tracker=None):
    BlueprintEncyclopediaPopup(parent=parent, tracker=tracker).show()
