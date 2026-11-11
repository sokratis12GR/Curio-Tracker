from tkinter import BooleanVar

from customtkinter import CTkFrame, CTkButton, CTkSwitch, CTkToplevel, CTkLabel

from fonts import make_font
from gui.palette import POE_PALETTE
from settings import get_setting, set_setting
from tree_manager import TreeManager

# Switch to two columns in the popup when there are more toggles than this.
_SINGLE_COLUMN_MAX = 8


class TreeToggles:
    def __init__(self, parent_frame, tree, tree_manager: TreeManager, theme_manager=None):
        self.tree = tree
        self.tm = tree_manager
        self.theme_manager = theme_manager
        self.frame = CTkFrame(parent_frame)
        self.frame.grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.col_vars = {}
        self.col_switches = {}
        self.toggle_img_btn = None
        self.menu_popup = None
        self._create_widgets()
        self._bind_root_events()

    # --- Setup ---
    def _accent(self):
        mode = getattr(self.theme_manager, "current_mode", "LIGHT").upper()
        return {"DARK": "#5865f2", "POE": POE_PALETTE["gold"]}.get(mode, "#0078d7")

    def _create_widgets(self):
        self.columns_btn = CTkButton(self.frame, command=self.open_menu_popup)
        self.columns_btn.grid(row=0, column=0, sticky="we", padx=10, pady=5)
        self._update_button_label()

    def _bind_root_events(self):
        # Bound once; handlers no-op while the popup is closed.
        root = self.frame.winfo_toplevel()
        root.bind("<Button-1>", self._on_root_click, add="+")
        root.bind("<Configure>", lambda e: self._position_popup(), add="+")
        root.bind("<Escape>", lambda e: self.close_menu_popup(), add="+")

    def _eligible_columns(self):
        enable_ladder = get_setting("Application", "enable_poeladder", False)
        return [
            col for col in self.tm.tree_columns
            if col["id"] != "numeric_value"
            and (enable_ladder or col["id"] != "owned")
        ]

    def _visible_count(self):
        displayed = set(self.tree["displaycolumns"])
        return sum(1 for col in self._eligible_columns() if col["id"] in displayed)

    def _is_open(self):
        return bool(self.menu_popup and self.menu_popup.winfo_exists())

    def _update_button_label(self):
        arrow = "▴" if self._is_open() else "▾"
        total = len(self._eligible_columns())
        self.columns_btn.configure(text=f"Columns ({self._visible_count()}/{total}) {arrow}")

    # --- Popup ---
    def open_menu_popup(self):
        if self._is_open():
            self.close_menu_popup()
            return

        accent = self._accent()
        self.menu_popup = CTkToplevel(self.frame)
        self.menu_popup.overrideredirect(True)
        self.menu_popup.attributes("-topmost", True)
        self.menu_popup.title("Columns")
        self.menu_popup.bind("<Escape>", lambda e: self.close_menu_popup())

        container = CTkFrame(
            self.menu_popup,
            corner_radius=8,
            border_width=1,
            border_color=accent,
        )
        container.pack(fill="both", expand=True)

        CTkLabel(
            container,
            text="Visible columns",
            font=make_font(11, "bold"),
            text_color=accent,
        ).pack(anchor="w", padx=12, pady=(10, 4))

        body = CTkFrame(container, fg_color="transparent")
        body.pack(fill="both", padx=8)

        self.col_vars.clear()
        self.col_switches.clear()
        columns = self._eligible_columns()
        per_column = len(columns) if len(columns) <= _SINGLE_COLUMN_MAX else (len(columns) + 1) // 2

        for idx, col in enumerate(columns):
            col_name = col["id"]
            saved_state = get_setting("Columns", col_name, True)
            var = BooleanVar(value=saved_state)
            self.col_vars[col_name] = var

            switch = CTkSwitch(
                body,
                text=col["label"],
                variable=var,
                progress_color=accent,
                cursor="hand2",
                command=lambda c=col_name, v=var: self._on_switch(c, v.get()),
            )
            switch.grid(row=idx % per_column, column=idx // per_column,
                        sticky="ew", padx=4, pady=3)
            self.col_switches[col_name] = switch
            self.toggle_column(col_name, saved_state, save=False)

        footer = CTkFrame(container, fg_color="transparent")
        footer.pack(fill="x", padx=10, pady=(8, 10))

        CTkButton(
            footer,
            text="Show all",
            height=26,
            fg_color=accent,
            cursor="hand2",
            command=self._show_all,
        ).pack(fill="x")

        self._refresh_lock()
        self._update_button_label()
        self._position_popup()

    def _position_popup(self):
        if not self._is_open():
            return
        try:
            self.menu_popup.update_idletasks()
            popup_height = self.menu_popup.winfo_reqheight()
            screen_height = self.menu_popup.winfo_screenheight()
            x = self.columns_btn.winfo_rootx()
            btn_y = self.columns_btn.winfo_rooty()
            btn_height = self.columns_btn.winfo_height()
            below_y = btn_y + btn_height + 2
            above_y = btn_y - popup_height - 2
            if below_y + popup_height > screen_height and above_y >= 0:
                y = above_y
            else:
                y = below_y
            self.menu_popup.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _on_root_click(self, event):
        if not self._is_open():
            return
        # Clicks on the Columns button are handled by its own command (toggle).
        if str(event.widget).startswith(str(self.columns_btn)):
            return
        self.close_menu_popup()

    def close_menu_popup(self):
        if self._is_open():
            self.menu_popup.destroy()
        self.menu_popup = None
        self._update_button_label()

    # --- Toggling ---
    def _on_switch(self, col_name, show):
        self.toggle_column(col_name, show)
        self._refresh_lock()
        self._update_button_label()

    def _show_all(self):
        for col_name, var in self.col_vars.items():
            if not var.get():
                var.set(True)
                self.toggle_column(col_name, True)
        self._refresh_lock()
        self._update_button_label()

    def _refresh_lock(self):
        """Prevent hiding the last visible column."""
        visible = [c for c, v in self.col_vars.items() if v.get()]
        for col_name, switch in self.col_switches.items():
            locked = len(visible) == 1 and col_name in visible
            switch.configure(state="disabled" if locked else "normal")

    def toggle_column(self, col_name, show, save=True):
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
