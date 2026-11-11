# controls.py

from customtkinter import *

from config import layout_keywords, time_options
from gui.frames.blueprint_info import BlueprintInfoPopup
from gui.popups.custom_load import CustomLoader
from gui.frames.info import InfoPanelPopup
from fonts import make_font
from gui.palette import DANGER_COLOR, DANGER_HOVER, MUTED_TEXT, SEPARATOR_COLOR
from settings import set_setting


class LeftFrameControls:
    def __init__(self, parent, tracker, tree_manager, tree):
        self.parent = parent
        self.tracker = tracker
        self.tree_manager = tree_manager
        self.tree = tree

        self.row_index = 0
        self.updating_from_tracker = False

        # --- StringVars
        self.vars = {
            "poe_player": StringVar(value=getattr(tracker, "poe_user", "")),
            "search": StringVar(value=""),
            "search_count": StringVar(value="Found: 0")
        }

        self.vcmd = (self.parent.register(self.validate_area_level), "%P")
        self.widgets = {}
        self.header_widgets = []

        self.parent.grid_columnconfigure((0, 1), weight=1, uniform="controls")

        # --- Setup UI
        self._add_section_header("Filter", first=True)
        self._setup_time_filter()
        self._add_section_header("Load")
        self._setup_buttons()
        self._add_section_header("Search")
        self._setup_search_and_info()
        self._add_section_header("Info")
        self._setup_info()

    # --- Validation ---
    def validate_area_level(self, value):
        return value == "" or value.isdigit()

    # --- Time Filter
    def _setup_time_filter(self):
        lbl = CTkLabel(self.parent, text="Time Filter:")
        lbl.grid(row=self.row_index, column=0, sticky="w", pady=4, padx=8)
        self.header_widgets.append(lbl)

        time_filter_dropdown = CTkComboBox(
            master=self.parent,
            variable=self.tree_manager.time_filter_var,
            values=time_options,
            width=150,
            corner_radius=6,
            state="readonly",
        )
        time_filter_dropdown.grid(row=self.row_index, column=1, sticky="ew", pady=4, padx=(0, 8))

        self.row_index += 1
        # Filtering and the custom range popup are driven by TreeManager's
        # own trace on time_filter_var (see filter_tree_by_time).

    # --- Buttons
    def _setup_buttons(self):
        btns = [
            ("Load Latest 1 Item", lambda: self.load_latest_item_wrapper(1)),
            ("Load Latest Wing", lambda: self.load_latest_item_wrapper(5)),
            ("Load Custom Amount", self.load_custom_amount_wrapper),
            ("Load All Data", self.load_all_data_wrapper),
            ("Clear Tree", self.tree_manager.force_clear_tree)
        ]

        rows_used = 0

        for i, (text, cmd) in enumerate(btns):
            if i < 4:
                btn = CTkButton(self.parent, text=text, command=cmd)
                row = self.row_index + (i // 2)
                col = i % 2
                btn.grid(row=row, column=col, pady=4, padx=(8, 4) if col == 0 else (4, 8), sticky="ew")
                rows_used = max(rows_used, (i // 2) + 1)
            else:
                # Destructive action: outlined red so it stands apart
                btn = CTkButton(
                    self.parent,
                    text=text,
                    command=cmd,
                    fg_color="transparent",
                    border_width=1,
                    border_color=DANGER_COLOR,
                    text_color=DANGER_COLOR,
                    hover_color=DANGER_HOVER,
                )
                row = self.row_index + rows_used
                btn.grid(row=row, column=0, columnspan=2, pady=(8, 4), padx=8, sticky="ew")
                rows_used += 1

            self.widgets[text] = btn

        self.row_index += rows_used

    def _add_separator(self):
        separator = CTkFrame(self.parent, height=1, fg_color=SEPARATOR_COLOR)
        separator.grid(row=self.row_index, column=0, columnspan=2, sticky="ew", padx=8, pady=(10, 4))
        self.row_index += 1

    def _add_section_header(self, title, first=False):
        if not first:
            self._add_separator()
        lbl = CTkLabel(self.parent, text=title.upper(), font=make_font(9, "bold"),
                       text_color=MUTED_TEXT, height=16)
        lbl.grid(row=self.row_index, column=0, columnspan=2, sticky="w", padx=8,
                 pady=(8 if first else 0, 2))
        self.row_index += 1

    # --- Search & Info
    def _setup_search_and_info(self):
        lbl = CTkLabel(self.parent, text="Search:")
        lbl.grid(row=self.row_index, column=0, sticky="w", pady=4, padx=8)
        self.header_widgets.append(lbl)

        search_entry = CTkEntry(self.parent, textvariable=self.vars['search'], width=150)
        search_entry.grid(row=self.row_index, column=1, sticky="ew", pady=4, padx=(0, 8))
        self.vars['search'].trace_add("write", self.search_items)
        self.widgets['search_entry'] = search_entry
        self.row_index += 1

        total_items_label = CTkLabel(self.parent, text="Total: 0", text_color=MUTED_TEXT, height=20)
        total_items_label.grid(row=self.row_index, column=0, sticky="w", padx=8, pady=(0, 4))
        self.widgets['total_items_label'] = total_items_label

        # Counter below search bar
        self.vars['search_count'] = StringVar(value="Found: 0")
        search_count_label = CTkLabel(self.parent, textvariable=self.vars['search_count'],
                                      text_color=MUTED_TEXT, height=20)
        search_count_label.grid(row=self.row_index, column=1, sticky="w", pady=(0, 4))
        self.widgets['search_count_label'] = search_count_label

        self.row_index += 1

    def _open_blueprint_info(self):
        popup = BlueprintInfoPopup(parent=self.parent, tracker=self.tracker)
        popup.show()

    def _open_info(self):
        popup = InfoPanelPopup(self.parent, title="Curio Hotkey Info")
        popup.show()

    # --- Search & Info
    def _setup_info(self):
        how_to_use_btn = CTkButton(self.parent, text="Info (Usage)", command=self._open_info)
        how_to_use_btn.grid(row=self.row_index, column=0, sticky="ew", padx=(8, 4), pady=(4, 8))
        self.widgets['how_to_use_btn'] = how_to_use_btn

        blueprint_info_btn = CTkButton(
            self.parent, text="Blueprint Info", command=self._open_blueprint_info
        )
        blueprint_info_btn.grid(row=self.row_index, column=1, sticky="ew", padx=(4, 8), pady=(4, 8))
        self.widgets['blueprint_info_btn'] = blueprint_info_btn
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
            label.configure(text=f"Total: {count}")

    def get_current_row(self):
        return self.row_index

    def refresh_ui(self):
        self.updating_from_tracker = True

        self.vars['poe_player'].set(getattr(self.tracker, "poe_user", ""))

        self.updating_from_tracker = False
