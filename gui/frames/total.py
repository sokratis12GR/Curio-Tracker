import threading
import webbrowser
from tkinter import StringVar

from PIL import Image
from customtkinter import CTkFrame, CTkLabel, CTkSwitch, CTkButton, CTkImage

import load_utils
from config import CHAOS_COLOR, poe_user, CHAOS_ORB_ICON_URL, DIVINE_ORB_ICON_URL
from fonts import make_font
from gui.palette import CARD_COLOR, MUTED_TEXT, SEPARATOR_COLOR
from img_utils import get_icon
from settings import get_setting, set_setting
from tree_manager import TreeManager

VALUE_ICON_SIZE = (18, 18)
EMPTY_VALUE = "—"


def _add_kofi_button(frame, column):
    def open_kofi():
        webbrowser.open_new("https://ko-fi.com/sofodev")

    try:
        icon_path = load_utils.get_resource_path("assets/kofi1.png")
        img = Image.open(icon_path)
        kofi_img = CTkImage(light_image=img, dark_image=img, size=(120, 30))

        CTkButton(
            frame,
            image=kofi_img,
            text="",
            command=open_kofi,
            fg_color="transparent",
            hover_color=("gray75", "gray30"),
            cursor="hand2",
            width=120,
            height=30,
        ).grid(row=0, column=column, padx=(10, 4), sticky="e")
    except Exception as e:
        print(f"Could not load Ko-fi image: {e}")
        CTkButton(frame, text="Support me on Ko-fi", command=open_kofi, width=120).grid(
            row=0, column=column, padx=(10, 4), sticky="e"
        )


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
        self.frame.grid(row=0, column=0, sticky="we", padx=10, pady=10)

        self.value_mode = StringVar(value=get_setting("Display", "value_mode", "Chaos"))
        self.value_mode.trace_add("write", lambda *_: self.on_value_mode_changed())

        self.player_name = StringVar(value=get_setting("User", "poe_user", poe_user))

        self.currency_icons = {}

        self._create_widgets()
        self._load_currency_icons()

    def _load_currency_icons(self):
        def _to_ctk_icon(name, url):
            pil_icon = get_icon(
                name=name,
                url=url,
                size=VALUE_ICON_SIZE,
                parent=self.frame,
                return_pil=True,
            )
            if isinstance(pil_icon, Image.Image):
                return CTkImage(light_image=pil_icon, dark_image=pil_icon, size=VALUE_ICON_SIZE)
            return None

        def _load():
            self.currency_icons["Chaos"] = _to_ctk_icon("Chaos Orb (Value Icon)", CHAOS_ORB_ICON_URL)
            self.currency_icons["Divine"] = _to_ctk_icon("Divine Orb (Value Icon)", DIVINE_ORB_ICON_URL)
            self.frame.after(0, self._apply_value_icon)

        threading.Thread(target=_load, daemon=True).start()

    def _apply_value_icon(self):
        icon = self.currency_icons.get(self.value_mode.get())
        self.total_value_label.configure(image=icon)
        self.total_picked_label.configure(image=icon)

    def _make_stat_card(self, column, caption):
        card = CTkFrame(self.frame, fg_color=CARD_COLOR, corner_radius=8)
        card.grid(row=0, column=column, padx=5, sticky="ns")

        CTkLabel(
            card,
            text=caption.upper(),
            font=make_font(9, "bold"),
            text_color=MUTED_TEXT,
            height=14,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(6, 0))

        value = CTkLabel(
            card,
            text=EMPTY_VALUE,
            font=make_font(14, "bold"),
            text_color=CHAOS_COLOR,
            compound="left",
            anchor="w",
            padx=4,
            height=24,
        )
        value.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 6))
        return value

    def _create_widgets(self):
        # Player name + Chaos/Divine switch stacked on the left
        player_box = CTkFrame(self.frame, fg_color="transparent")
        player_box.grid(row=0, column=0, padx=(4, 10), sticky="w")

        self.player_label = CTkLabel(
            player_box,
            textvariable=self.player_name,
            font=make_font(12, "bold"),
            height=20,
        )
        self.player_label.grid(row=0, column=0, sticky="w")

        self.mode_switch = CTkSwitch(
            player_box,
            text="Chaos/Divine",
            variable=self.value_mode,
            onvalue="Divine",
            offvalue="Chaos",
            font=make_font(10),
            text_color=MUTED_TEXT,
        )
        self.mode_switch.grid(row=1, column=0, sticky="w")

        # Thin vertical divider (kept as `separator` for compatibility)
        self.separator = CTkFrame(self.frame, width=2, height=1, fg_color=SEPARATOR_COLOR)
        self.separator.grid(row=0, column=1, sticky="ns", padx=(0, 5), pady=4)

        self.total_value_label = self._make_stat_card(2, "Total Value")
        self.total_picked_label = self._make_stat_card(3, "Picked Value")

        # Spacer pushes Ko-fi to the far right
        self.frame.grid_columnconfigure(4, weight=1)
        _add_kofi_button(self.frame, column=5)

    def on_value_mode_changed(self):
        mode = self.value_mode.get()
        set_setting("Display", "value_mode", mode)
        self._apply_value_icon()
        self.tm.update_total_labels()
