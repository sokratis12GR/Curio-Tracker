from tkinter import StringVar
from customtkinter import CTkFrame, CTkLabel, CTkSwitch
from config import CHAOS_COLOR, poe_user
from fonts import make_font
from settings import get_setting, set_setting
from tree_manager import TreeManager


class TotalFrame:
    def __init__(self, parent, tree_manager: TreeManager, theme_manager=None):
        self.tm = tree_manager
        self.theme_manager = theme_manager
        self.frame = CTkFrame(
            parent,
            corner_radius=15,
            fg_color="transparent",
            bg_color="transparent"
        )
        self.frame.grid(row=0, column=0, sticky="w", padx=10, pady=10)

        self.value_mode = StringVar(value=get_setting("Display", "value_mode", "Chaos"))
        self.value_mode.trace_add("write", lambda *_: self.on_value_mode_changed())

        self.player_name = StringVar(value=get_setting("User", "poe_user", poe_user))

        self._create_widgets()

    def _create_widgets(self):
        # Player name
        self.player_label = CTkLabel(
            self.frame,
            textvariable=self.player_name,
            font=make_font(12, "bold"),
            text_color="#ffffff"
        )
        self.player_label.grid(row=0, column=0, padx=(10, 10))

        # Chaos/Divine Switch
        self.mode_switch = CTkSwitch(
            self.frame,
            text="Chaos/Divine",
            variable=self.value_mode,
            onvalue="Divine",
            offvalue="Chaos",
            font=make_font(10)
        )
        self.mode_switch.grid(row=0, column=1, padx=(10, 10))

        # Total Value label
        self.total_value_label = CTkLabel(
            self.frame,
            text="Total Value: 0 Chaos",
            font=make_font(12, "bold"),
            text_color=CHAOS_COLOR
        )
        self.total_value_label.grid(row=0, column=2, padx=(10, 5))

        # Separator
        self.separator = CTkLabel(
            self.frame,
            text="|",
            font=make_font(12, "bold"),
            text_color="#ffffff"
        )
        self.separator.grid(row=0, column=3, padx=5)

        # Picked Value label
        self.total_picked_label = CTkLabel(
            self.frame,
            text="Picked Value: 0 Chaos",
            font=make_font(12, "bold"),
            text_color=CHAOS_COLOR
        )
        self.total_picked_label.grid(row=0, column=4, padx=(5, 10))

    def on_value_mode_changed(self):
        mode = self.value_mode.get()
        set_setting("Display", "value_mode", mode)
        self.tm.update_total_labels()
