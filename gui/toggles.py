import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

import toasts
from logger import log_message
from settings import get_setting, set_setting  # replace with your actual settings module
import config as c

class TreeToggles:
    def __init__(self, parent_frame, tree, tree_manager, theme_manager=None):
        self.tree = tree
        self.tm = tree_manager
        self.theme_manager = theme_manager
        self.frame = ttk.Frame(parent_frame)
        self.frame.grid(row=0, column=0, sticky="ew", pady=(5, 0))
        self.col_vars = {}
        self.menu_indices = {}
        self.toggle_img_btn = None
        self.menu_btn = None
        self.menu = None
        self._create_widgets()

    def _create_widgets(self):
        menu_btn = ttk.Menubutton(self.frame, text="Columns")
        menu = tk.Menu(menu_btn, tearoff=False)
        menu_btn["menu"] = menu
        menu_btn.grid(row=0, column=0, padx=5)

        self.menu_btn = menu_btn
        self.menu = menu

        for idx, col in enumerate(self.tm.tree_columns):
            col_name = col["id"]

            if col_name == "numeric_value":
                continue

            saved_state = get_setting("Columns", col_name, True)
            var = tk.BooleanVar(value=saved_state)
            self.col_vars[col_name] = var

            menu.add_checkbutton(
                label=col["label"],
                variable=var,
                command=lambda c=col_name, v=var: self.toggle_column(c, v.get())
            )
            self.menu_indices[col_name] = idx

            # Apply saved state immediately
            self.toggle_column(col_name, saved_state, save=False)

        # Image toggle button
        img_visible = get_setting("Columns", "img", True)
        self.tm.images_visible = img_visible
        self.toggle_img_btn = ttk.Button(self.frame, text="Toggle Images", command=self.toggle_images)
        self.toggle_img_btn.grid(row=0, column=1, padx=5)
        self.update_img_column_state(img_visible)

    def toggle_column(self, col_name, show, save=True):
        if col_name == "img":
            self.update_img_column_state(show)
        else:
            current_displayed = list(self.tree["displaycolumns"])
            if show and col_name not in current_displayed:
                idx = self.tm.columns.index(col_name)
                insert_at = 0
                for i, c in enumerate(current_displayed):
                    if self.tm.columns.index(c) > idx:
                        insert_at = i
                        break
                else:
                    insert_at = len(current_displayed)
                current_displayed.insert(insert_at, col_name)
            elif not show and col_name in current_displayed:
                current_displayed.remove(col_name)
            self.tree["displaycolumns"] = current_displayed

        if save:
            set_setting("Columns", col_name, show)

    def update_img_column_state(self, show_column: bool):
        self.tree.column("#0", width=self.tm.image_col_width if show_column else 0, minwidth=20 if show_column else 0)

        for iid in self.tree.get_children():
            if show_column and iid in self.tm.original_img_cache:
                photo = ImageTk.PhotoImage(self.tm.original_img_cache[iid])
                self.tree.item(iid, image=photo)
                self.tm.image_cache[iid] = photo
            else:
                self.tree.item(iid, image='')

        # Save setting
        set_setting("Columns", "img_visible", show_column)

    def toggle_images(self):
        self.tm.images_visible = not self.tm.images_visible
        set_setting("Columns", "img", self.tm.images_visible)
        self.update_img_column_state(self.tm.images_visible)

    def apply_theme(self, widget_bg, fg, accent):
        # Menubutton
        if self.menu_btn:
            self.menu_btn.configure(style="MenuButton.TMenubutton")

        # Menu entries
        if self.menu:
            for i in range(self.menu.index("end") + 1 if self.menu.index("end") is not None else 0):
                self.menu.entryconfig(i, background=widget_bg, foreground=fg,
                                      activebackground=accent, activeforeground="white")

        # Image toggle button
        if self.toggle_img_btn:
            try:
                self.toggle_img_btn.configure(bg=widget_bg, fg=fg, activebackground=accent)
            except tk.TclError:
                pass

# class ToastsToggles:
#     def __init__(self, parent_frame):
#         self.frame = ttk.Frame(parent_frame)
#         self.frame.grid(row=0, column=0, sticky="w", pady=(5, 0))
#
#         # Toasts enabled checkbox
#         self.toasts_var = tk.BooleanVar(value=get_setting('Application', 'are_toasts_enabled', True))
#         self.toasts_checkbox = ttk.Checkbutton(
#             self.frame,
#             text="Enable Toasts",
#             variable=self.toasts_var,
#             command=self.toggle_toasts
#         )
#         self.toasts_checkbox.grid(row=0, column=0, padx=5, sticky="w")
#         self.toasts_checkbox.configure(style="Toasts.TCheckbutton")
#
#         # Toasts duration label
#         ttk.Label(self.frame, text="Toasts Duration:").grid(
#             row=0, column=1, sticky="w", padx=(10, 2)
#         )
#
#         # Toasts duration spinbox
#         self.toasts_duration_var = tk.StringVar(
#             value=str(get_setting('Application', 'toasts_duration_seconds', 5))
#         )
#
#         self.toasts_duration_spinbox = ttk.Spinbox(
#             self.frame,
#             from_=1,
#             to=30,
#             textvariable=self.toasts_duration_var,
#             width=5,
#             validate='all',
#             validatecommand=(self.frame.register(self.validate_duration), '%P')
#         )
#         self.toasts_duration_spinbox.grid(row=0, column=2, sticky="w")
#
#         # Trace changes
#         self.toasts_duration_var.trace_add("write", self.update_toasts_duration)
#
#         # Initialize toasts duration
#         duration = int(self.toasts_duration_var.get())
#         toasts.TOASTS_DURATION = max(1, min(duration, 30))
#
#     def toggle_toasts(self):
#         enabled = self.toasts_var.get()
#         set_setting('Application', 'are_toasts_enabled', enabled)
#         if c.DEBUGGING:
#             print(f"[DEBUG] Toasts enabled: {enabled}")
#
#     def validate_duration(self, new_value):
#         if not new_value:
#             return True
#         if new_value.isdigit():
#             value = int(new_value)
#             return 1 <= value <= 30
#         return False
#
#     def update_toasts_duration(self, *args):
#         try:
#             duration = int(self.toasts_duration_var.get())
#         except ValueError:
#             duration = 5
#             self.toasts_duration_var.set(str(duration))
#
#         duration = max(1, min(duration, 30))
#         self.toasts_duration_var.set(str(duration))
#         toasts.TOASTS_DURATION = duration
#         set_setting('Application', 'toasts_duration_seconds', duration)
#
#         if c.DEBUGGING:
#             print(f"[DEBUG] Toasts Duration set to: {duration}s")
#
# class LeagueSelector:
#     def __init__(self, parent_frame, on_league_change_callback=None):
#         self.frame = ttk.Frame(parent_frame)
#         self.frame.grid(row=0, column=1, sticky="e", padx=10, pady=(5, 0))
#
#         self.league_options = c.LEAGUES_TO_FETCH
#         current_league = get_setting("Application", "data_league", c.LEAGUE)
#         if current_league not in self.league_options:
#             current_league = c.LEAGUE
#
#         ttk.Label(self.frame, text="League:").grid(row=0, column=0, sticky="w", padx=(0, 5))
#
#         self.league_var = tk.StringVar(value=current_league)
#         self.league_dropdown = ttk.Combobox(
#             self.frame,
#             textvariable=self.league_var,
#             values=self.league_options,
#             state="readonly",
#             width=20
#         )
#         self.league_dropdown.grid(row=0, column=1, sticky="w")
#
#         self.callback = on_league_change_callback
#         self.league_dropdown.bind("<<ComboboxSelected>>", self._on_change)
#
#     def _on_change(self, event=None):
#         new_league = self.league_var.get()
#         set_setting("Application", "data_league", new_league)
#         if self.callback:
#             self.callback(new_league)