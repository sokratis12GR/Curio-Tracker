# controls.py
import tkinter as tk
from tkinter import ttk

from config import league_versions, layout_keywords, time_options
from gui.custom_load_popup import CustomLoader
from settings import set_setting


class LeftFrameControls:
    def __init__(self, parent, theme_manager, tracker, tree_manager, tree):
        self.parent = parent
        self.theme_manager = theme_manager
        self.tracker = tracker
        self.tree_manager = tree_manager
        self.tree = tree

        self.row_index = 0
        self.updating_from_tracker = False

        # --- StringVars
        self.vars = {
            "poe_player": tk.StringVar(value=getattr(tracker, "poe_user", "")),
            "league": tk.StringVar(value=getattr(tracker, "league_version", league_versions[0])),
            "blueprint_type": tk.StringVar(value=tracker.blueprint_layout),
            "area_level": tk.StringVar(value=str(tracker.blueprint_area_level)),
            "search": tk.StringVar(value=""),
            "search_count": tk.StringVar(value="Found: 0")
        }

        self.vcmd = (self.parent.register(self.validate_area_level), "%P")
        self.widgets = {}
        self.header_widgets = []

        # --- Setup UI
        self._setup_time_filter()
        self._add_separator()
        self._setup_buttons()
        self._add_separator()
        # self._setup_player_info()
        # self._setup_league()
        self._setup_blueprint_type()
        self._setup_area_level()
        self._add_separator()
        self._setup_search_and_info()
        self._add_separator()

        # --- Automatic theme registration ---
        self._register_widgets_for_theme()

    # --- Validation ---
    def validate_area_level(self, value):
        return value == "" or value.isdigit()

    # --- Automatic registration method ---
    def _register_widgets_for_theme(self):
        for w in self.widgets.values():
            self.theme_manager.register(w)
        # Register header labels
        for lbl in self.header_widgets:
            self.theme_manager.register(lbl, "headers")

    # --- Time Filter
    def _setup_time_filter(self):
        lbl = ttk.Label(self.parent, text="Time Filter:")
        lbl.grid(row=self.row_index, column=0, sticky="w", pady=(5, 2))
        self.header_widgets.append(lbl)
        self.theme_manager.register(lbl)

        time_filter_dropdown = ttk.Combobox(
            self.parent,
            textvariable=self.tree_manager.time_filter_var,
            values=time_options,
            width=20,
            state="readonly",
            style="TCombobox"
        )
        time_filter_dropdown.grid(row=self.row_index, column=1, sticky="w", pady=(5, 2))
        self.theme_manager.register(time_filter_dropdown)

        self.row_index += 1
        self.tree_manager.time_filter_var.trace_add("write", lambda *args: self.tree_manager.filter_tree_by_time())

        def on_time_change(*args):
            if self.tree_manager.time_filter_var.get() == "Custom...":
                self.tree_manager.open_custom_hours_popup()

        self.tree_manager.time_filter_var.trace_add("write", on_time_change)

    # --- Buttons
    def _setup_buttons(self):
        btns = [
            ("Load Latest 1 Item", lambda: self.load_latest_item_wrapper(1)),
            ("Load Latest Wing", lambda: self.load_latest_item_wrapper(5)),
            ("Load Custom Amount", self.load_custom_amount_wrapper),
            ("Load All Data", self.load_all_data_wrapper),
            ("Clear Tree", self.tree_manager.clear_tree)
        ]

        rows_used = 0

        for i, (text, cmd) in enumerate(btns):
            btn = ttk.Button(self.parent, text=text, command=cmd)

            if i < 4:
                row = self.row_index + (i // 2)
                col = i % 2
                btn.grid(row=row, column=col, pady=5, sticky="ew")
                rows_used = max(rows_used, (i // 2) + 1)
            else:
                row = self.row_index + rows_used
                btn.grid(row=row, column=0, columnspan=2, pady=5, sticky="ew")
                rows_used += 1

            self.theme_manager.register(btn)
            self.widgets[text] = btn

        self.row_index += rows_used

    def _add_separator(self):
        separator = ttk.Separator(self.parent, orient="horizontal")
        separator.grid(row=self.row_index, column=0, columnspan=2, sticky="ew", pady=(10, 10))
        self.row_index += 1

    # # --- Player Info
    # def _setup_player_info(self):
    #     lbl = ttk.Label(self.parent, text="PoE Player:")
    #     lbl.grid(row=self.row_index, column=0, sticky="w", pady=(5, 2))
    #     self.theme_manager.register(lbl)
    #     self.header_widgets.append(lbl)
    #
    #     entry = ttk.Entry(self.parent, textvariable=self.vars['poe_player'], width=20)
    #     entry.grid(row=self.row_index, column=1, sticky="w", pady=(5, 2))
    #     self.theme_manager.register(entry)
    #     self.vars['poe_player'].trace_add("write", self.update_tracker_poe_player)
    #     self.widgets['poe_player_entry'] = entry
    #     self.row_index += 1
    #
    # def update_tracker_poe_player(self, *args):
    #     if self.updating_from_tracker:
    #         return
    #     value = self.vars['poe_player'].get()
    #     self.tracker.poe_user = value
    #     set_setting("User", "poe_user", value)
    #
    # # --- League
    # def _setup_league(self):
    #     lbl = ttk.Label(self.parent, text="League Version:")
    #     lbl.grid(row=self.row_index, column=0, sticky="w", pady=(5, 2))
    #     self.theme_manager.register(lbl)
    #     self.header_widgets.append(lbl)
    #
    #     cb = ttk.Combobox(self.parent, textvariable=self.vars['league'], values=league_versions, width=20)
    #     cb.grid(row=self.row_index, column=1, sticky="w", pady=(5, 2))
    #     self.theme_manager.register(cb)
    #     self.vars['league'].trace_add("write", self.update_tracker_league)
    #     self.widgets['league_cb'] = cb
    #     self.row_index += 1
    #
    # def update_tracker_league(self, *args):
    #     if self.updating_from_tracker:
    #         return
    #     value = self.vars['league'].get()
    #     self.tracker.league_version = value
    #     set_setting("User", "poe_league", value)

    # --- Blueprint Type
    def _setup_blueprint_type(self):
        lbl = ttk.Label(self.parent, text="Blueprint Type:")
        lbl.grid(row=self.row_index, column=0, sticky="w", pady=(5, 2))
        self.theme_manager.register(lbl)
        self.header_widgets.append(lbl)

        cb = ttk.Combobox(self.parent, textvariable=self.vars['blueprint_type'], values=layout_keywords, width=20)
        cb.grid(row=self.row_index, column=1, sticky="w", pady=(5, 2))
        self.theme_manager.register(cb)
        self.vars['blueprint_type'].trace_add("write", self.update_tracker_blueprint)
        self.widgets['blueprint_cb'] = cb
        self.row_index += 1

    # --- Area Level
    def _setup_area_level(self):
        lbl = ttk.Label(self.parent, text="Area Level:")
        lbl.grid(row=self.row_index, column=0, sticky="w", pady=(5, 2))
        self.theme_manager.register(lbl)
        self.header_widgets.append(lbl)

        entry = ttk.Entry(self.parent, textvariable=self.vars['area_level'], width=20, validate="key",
                          validatecommand=self.vcmd)
        entry.grid(row=self.row_index, column=1, sticky="w", pady=(5, 2))
        self.theme_manager.register(entry)
        self.vars['area_level'].trace_add("write", self.update_tracker_blueprint)
        self.widgets['area_level_entry'] = entry
        self.row_index += 1

    def update_tracker_blueprint(self, *args):
        if self.updating_from_tracker:
            return
        layout = self.vars['blueprint_type'].get()
        level = int(self.vars['area_level'].get() or 0)
        self.tracker.blueprint_layout = layout
        self.tracker.blueprint_area_level = level
        set_setting("Blueprint", "layout", layout)
        set_setting("Blueprint", "area_level", level)

    def refresh_blueprint_info(self):
        self.updating_from_tracker = True
        try:
            self.vars['blueprint_type'].set(self.tracker.blueprint_layout)
            self.vars['area_level'].set(str(self.tracker.blueprint_area_level))
        finally:
            self.updating_from_tracker = False

    # --- Search & Info
    def _setup_search_and_info(self):
        lbl = ttk.Label(self.parent, text="Search:")
        lbl.grid(row=self.row_index, column=0, sticky="w", pady=(5, 2))
        self.theme_manager.register(lbl)
        self.header_widgets.append(lbl)

        search_entry = ttk.Entry(self.parent, textvariable=self.vars['search'])
        search_entry.grid(row=self.row_index, column=1, sticky="w", pady=(5, 2))
        self.theme_manager.register(search_entry)
        self.vars['search'].trace_add("write", self.search_items)
        self.widgets['search_entry'] = search_entry
        self.row_index += 1


        total_items_label = ttk.Label(self.parent, text="Total: 0")
        total_items_label.grid(row=self.row_index, column=0, columnspan=2, sticky="w", pady=(0, 5))
        self.theme_manager.register(total_items_label)
        self.widgets['total_items_label'] = total_items_label

        # Counter below search bar
        self.vars['search_count'] = tk.StringVar(value="Found: 0")
        search_count_label = ttk.Label(self.parent, textvariable=self.vars['search_count'])
        search_count_label.grid(row=self.row_index, column=1, columnspan=2, sticky="w", pady=(0, 5))
        self.theme_manager.register(search_count_label)
        self.widgets['search_count_label'] = search_count_label

        self.row_index += 1

    def search_items(self, *args):
        query = self.vars['search'].get().lower().strip()
        self.tree_manager.apply_filters(search_query=query)
        self.tree_manager.search_var.set(self.vars['search'].get())

        # Update count
        matched_count = len(self.tree.get_children())
        self.vars['search_count'].set(f"Found: {matched_count}")
        self.update_total_items_count()

    def load_latest_item_wrapper(self, max_items=1):
        if max_items == 1:
            self.tree_manager.load_latest_item(self.tracker)
        elif max_items == 5:
            self.tree_manager.load_latest_items(self.tracker)
        self.update_total_items_count()

    def load_custom_amount_wrapper(self):
        custom_loader = CustomLoader(
            root=self.parent.winfo_toplevel(),
            controls=self,
            tree_manager=self.tree_manager,
            tracker=self.tracker,
            theme_manager=self.theme_manager
        ).run()
        self.update_total_items_count()

    def load_all_data_wrapper(self):
        self.tree_manager.load_all_items_threaded(
            self.tracker,
            post_callback=self.update_total_items_count
        )

    def get_all_item_iids(self):
        return self.tree_manager.all_item_iids

    def update_total_items_count(self):
        label = self.widgets.get('total_items_label')
        if label and label.winfo_exists():
            count = len(self.tree_manager.all_item_iids)
            label.config(text=f"Total: {count}")

    def get_current_row(self):
        return self.row_index

    def refresh_ui(self):
        self.updating_from_tracker = True

        self.vars['poe_player'].set(getattr(self.tracker, "poe_user", ""))
        self.vars['league'].set(getattr(self.tracker, "league_version", league_versions[0]))
        self.vars['blueprint_type'].set(getattr(self.tracker, "blueprint_layout", layout_keywords[0]))
        self.vars['area_level'].set(str(getattr(self.tracker, "blueprint_area_level", 0)))

        self.updating_from_tracker = False
