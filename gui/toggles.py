from tkinter import BooleanVar

from customtkinter import CTkFrame, CTkButton, CTkCheckBox, CTkToplevel

from settings import get_setting, set_setting


class TreeToggles:
    def __init__(self, parent_frame, tree, tree_manager, theme_manager=None):
        self.tree = tree
        self.tm = tree_manager
        self.theme_manager = theme_manager
        self.frame = CTkFrame(parent_frame)
        self.frame.grid(row=0, column=0, sticky="w", pady=(5, 0))
        self.col_vars = {}
        self.toggle_img_btn = None
        self.menu_popup = None
        self._track_popup = False
        self._create_widgets()

    def _create_widgets(self):
        self.columns_btn = CTkButton(self.frame, text="Columns", command=self.open_menu_popup)
        self.columns_btn.grid(row=0, column=0, padx=0)

    def open_menu_popup(self):
        if self.menu_popup and self.menu_popup.winfo_exists():
            self._track_popup = False
            self.menu_popup.destroy()
            return

        self.menu_popup = CTkToplevel(self.frame)
        self.menu_popup.overrideredirect(True)
        self.menu_popup.attributes("-topmost", True)
        self.menu_popup.lift()
        self.menu_popup.title("Columns")
        self._position_popup()
        self._track_popup = True
        self._update_popup_position()
        self.menu_popup.bind("<FocusOut>", lambda e: self.close_menu_popup())

        for idx, col in enumerate(self.tm.tree_columns):
            col_name = col["id"]
            if col_name == "numeric_value" or (not get_setting("Application", "enable_poeladder", False) and col_name == "owned"):
                continue
            saved_state = get_setting("Columns", col_name, True)
            var = BooleanVar(value=saved_state)
            self.col_vars[col_name] = var
            chk = CTkCheckBox(
                self.menu_popup,
                text=col["label"],
                variable=var,
                command=lambda c=col_name, v=var: self.toggle_column(c, v.get())
            )
            chk.pack(anchor="w", padx=10, pady=2)
            self.toggle_column(col_name, saved_state, save=False)

        self.menu_popup.update_idletasks()
        self._position_popup()

    def _position_popup(self):
        try:
            self.menu_popup.update_idletasks()
            popup_height = self.menu_popup.winfo_height()
            screen_height = self.menu_popup.winfo_screenheight()
            x = self.columns_btn.winfo_rootx()
            btn_y = self.columns_btn.winfo_rooty()
            btn_height = self.columns_btn.winfo_height()
            below_y = btn_y + btn_height
            above_y = btn_y - popup_height
            if below_y + popup_height > screen_height and above_y >= 0:
                y = above_y
            else:
                y = below_y
            self.menu_popup.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _update_popup_position(self):
        if not self._track_popup or not self.menu_popup.winfo_exists():
            return
        self._position_popup()
        self.menu_popup.after(100, self._update_popup_position)

    def close_menu_popup(self):
        if self.menu_popup and self.menu_popup.winfo_exists():
            self._track_popup = False
            self.menu_popup.destroy()

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
