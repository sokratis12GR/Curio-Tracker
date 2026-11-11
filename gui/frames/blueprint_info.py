import threading

import customtkinter as ctk
from PIL import Image

import config
from config import layout_keywords, BP_ENCHANTMENT_OPTIONS
from fonts import make_font
from gui.heist_icons import BP_ENCHANTMENT_ICONS, location_icon
from img_utils import get_cached_icon, get_icon
from settings import set_setting
from gui.palette import POE_PALETTE, themed
from win_utils import center_window_on_parent, prepare_popup

MUTED_TEXT = themed(("gray35", "gray65"), POE_PALETTE["muted"])
CARD_COLOR = themed(("#f4f6f8", "#2b2d31"), POE_PALETTE["panel_bg"])

HEADER_ICON = 52
FIELD_ICON = 26


class BlueprintInfoPopup:
    def __init__(self, parent=None, tracker=None, title="Blueprint Info"):
        self.parent = parent
        self.tracker = tracker
        self.title = title
        self.updating_from_popup = False

        self.blueprint_var = ctk.StringVar()
        self.area_level_var = ctk.StringVar()
        self.bp_enchantment_var = ctk.StringVar()

        # slot -> (label, size)
        self._icon_slots = {}
        self._blank_icons = {}

    def show(self):
        popup = ctk.CTkToplevel(self.parent)
        prepare_popup(popup)
        popup.title(self.title)
        popup.resizable(False, False)
        popup.transient(self.parent.winfo_toplevel())
        popup.bind("<Escape>", lambda e: popup.destroy())

        outer = ctk.CTkFrame(popup, fg_color="transparent")
        outer.pack(padx=16, pady=16, fill="both", expand=True)

        # --- Header card: current blueprint summary ---
        header = ctk.CTkFrame(outer, fg_color=CARD_COLOR, corner_radius=10)
        header.pack(fill="x")
        header.grid_columnconfigure(1, weight=1)

        self._icon_label(header, "header", HEADER_ICON).grid(
            row=0, column=0, rowspan=2, padx=(14, 12), pady=12
        )
        self.header_title = ctk.CTkLabel(header, text="", font=make_font(16, "bold"), anchor="w")
        self.header_title.grid(row=0, column=1, sticky="sw", pady=(12, 0))
        self.header_subtitle = ctk.CTkLabel(
            header, text="", font=make_font(10), text_color=MUTED_TEXT,
            anchor="w", justify="left", wraplength=330
        )
        self.header_subtitle.grid(row=1, column=1, sticky="nw", pady=(0, 12), padx=(0, 12))

        # --- Form ---
        form = ctk.CTkFrame(outer, fg_color=CARD_COLOR, corner_radius=10)
        form.pack(fill="x", pady=(10, 0))
        form.grid_columnconfigure(2, weight=1)

        allowed_ilvl = [str(i) for i in range(83, 47, -1)]

        fields = (
            ("Blueprint", "blueprint", ctk.CTkComboBox(
                form, variable=self.blueprint_var, values=layout_keywords,
                width=320, state="readonly")),
            ("Area Level", None, ctk.CTkComboBox(
                form, variable=self.area_level_var, values=allowed_ilvl, width=320)),
            ("Enchantment", "enchantment", ctk.CTkComboBox(
                form, variable=self.bp_enchantment_var, values=BP_ENCHANTMENT_OPTIONS,
                width=320, state="readonly")),
        )

        for row, (label_text, slot, widget) in enumerate(fields):
            pad = (14 if row == 0 else 6, 14 if row == len(fields) - 1 else 6)

            ctk.CTkLabel(form, text=label_text, font=make_font(11, "bold"), anchor="w", width=90).grid(
                row=row, column=0, sticky="w", padx=(14, 6), pady=pad
            )

            if slot:
                icon = self._icon_label(form, slot, FIELD_ICON)
            else:
                icon = ctk.CTkLabel(form, text="", width=FIELD_ICON)
            icon.grid(row=row, column=1, padx=(0, 8), pady=pad)

            widget.grid(row=row, column=2, sticky="ew", padx=(0, 14), pady=pad)

        # --- Footer ---
        footer = ctk.CTkFrame(outer, fg_color="transparent")
        footer.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(footer, text="Changes save automatically.", font=make_font(10),
                     text_color=MUTED_TEXT).pack(side="left")
        ctk.CTkButton(footer, text="Done", width=90, command=popup.destroy).pack(side="right")
        ctk.CTkButton(
            footer, text="Reload", width=90, fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"), command=self.refresh_info
        ).pack(side="right", padx=(0, 8))

        # Fill values before the popup is revealed so nothing pops in afterwards.
        self.refresh_info()

        for var in (self.blueprint_var, self.area_level_var, self.bp_enchantment_var):
            var.trace_add("write", self.update_tracker_from_popup)
            var.trace_add("write", lambda *_: self._refresh_view())

        self._refresh_view()

        center_window_on_parent(popup, self.parent)

        popup.grab_set()
        popup.focus_force()
        popup.wait_window()

    # ------------------------------------------------------------- display

    def _refresh_view(self):
        layout = self.blueprint_var.get() or "No blueprint set"
        level = self.area_level_var.get()
        enchant = self.bp_enchantment_var.get()

        self.header_title.configure(text=layout)

        parts = [f"Area Level {level}" if level else "Area level not set"]
        if enchant and enchant != "None":
            parts.append(enchant.replace("Heist Targets are always ", "Targets: "))
        else:
            parts.append("No enchantment")
        self.header_subtitle.configure(text="  •  ".join(parts))

        self._refresh_icons()

    def _blank(self, size):
        if size not in self._blank_icons:
            blank = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            self._blank_icons[size] = ctk.CTkImage(light_image=blank, dark_image=blank, size=(size, size))
        return self._blank_icons[size]

    def _icon_label(self, parent, slot, size):
        label = ctk.CTkLabel(parent, text="", image=self._blank(size), width=size, height=size)
        self._icon_slots[slot] = (label, size)
        return label

    def _current_icons(self):
        location = location_icon(self.blueprint_var.get())
        return {
            "header": location,
            "blueprint": location,
            "enchantment": BP_ENCHANTMENT_ICONS.get(self.bp_enchantment_var.get()),
        }

    def _set_icon(self, slot, pil_img):
        label, size = self._icon_slots.get(slot, (None, None))
        if label is None:
            return
        try:
            if not label.winfo_exists():
                return
        except Exception:
            return

        if pil_img is None:
            label.configure(image=self._blank(size))
        else:
            label.configure(image=ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(size, size)))

    def _refresh_icons(self):
        for slot, icon in self._current_icons().items():
            if slot not in self._icon_slots:
                continue
            size = (self._icon_slots[slot][1],) * 2

            if not icon:
                self._set_icon(slot, None)
                continue

            name, url = icon
            cached = get_cached_icon(name, size)
            if cached is not None:
                self._set_icon(slot, cached)
                continue

            self._set_icon(slot, None)

            def _load(slot=slot, name=name, url=url, size=size):
                pil_img = get_icon(name=name, url=url, size=size, return_pil=True)
                if pil_img is None:
                    return
                label = self._icon_slots[slot][0]
                try:
                    label.after(0, lambda: self._apply_if_current(slot, name, pil_img))
                except Exception:
                    pass

            threading.Thread(target=_load, daemon=True).start()

    def _apply_if_current(self, slot, name, pil_img):
        current = self._current_icons().get(slot)
        if current and current[0] == name:
            self._set_icon(slot, pil_img)

    # ---------------------------------------------------------------- data

    def update_tracker_from_popup(self, *args):
        if self.updating_from_popup or not self.tracker:
            return

        try:
            level = int(self.area_level_var.get() or 0)
        except ValueError:
            return  # still typing a non-numeric area level

        self.updating_from_popup = True
        try:
            layout = self.blueprint_var.get()
            enchantment = self.bp_enchantment_var.get()

            self.tracker.blueprint_layout = layout
            self.tracker.blueprint_area_level = level
            self.tracker.bp_enchantment = enchantment

            config.SET_BP_ENCHANTMENT_FOR_RUNS = enchantment

            set_setting("Blueprint", "layout", layout)
            set_setting("Blueprint", "area_level", level)
            set_setting("Blueprint", "bp_enchantment", enchantment)
        finally:
            self.updating_from_popup = False

    def refresh_info(self):
        if not self.tracker:
            return

        self.updating_from_popup = True
        try:
            self.blueprint_var.set(self.tracker.blueprint_layout)
            self.area_level_var.set(str(self.tracker.blueprint_area_level))
            self.bp_enchantment_var.set(self.tracker.bp_enchantment)
        finally:
            self.updating_from_popup = False
