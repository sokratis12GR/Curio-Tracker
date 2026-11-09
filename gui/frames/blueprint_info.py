import customtkinter as ctk

import config
from config import layout_keywords, BP_ENCHANTMENT_OPTIONS
from settings import set_setting
from win_utils import center_window_on_parent


class BlueprintInfoPopup:
    def __init__(self, parent=None, tracker=None, title="Blueprint Info"):
        self.parent = parent
        self.tracker = tracker
        self.title = title
        self.updating_from_popup = False

        self.blueprint_var = ctk.StringVar()
        self.area_level_var = ctk.StringVar()
        self.bp_enchantment_var = ctk.StringVar()

    def show(self):
        popup = ctk.CTkToplevel(self.parent)
        popup.title(self.title)
        popup.minsize(300, 350)
        popup.resizable(False, False)

        popup.transient(self.parent.winfo_toplevel())

        frame = ctk.CTkFrame(popup)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        # --- Blueprint Type ---
        ctk.CTkLabel(frame, text="Blueprint Type:").pack(anchor="w", pady=(0, 3))
        blueprint_cb = ctk.CTkComboBox(frame, variable=self.blueprint_var, values=layout_keywords, width=150)
        blueprint_cb.pack(anchor="w", pady=(0, 10))
        self.blueprint_var.trace_add("write", self.update_tracker_from_popup)

        # --- Area Level ---
        ctk.CTkLabel(frame, text="Area Level:").pack(anchor="w", pady=(0, 3))
        allowed_ilvl = [str(i) for i in range(48, 84)]
        allowed_ilvl.reverse()
        area_cb = ctk.CTkComboBox(frame, variable=self.area_level_var, values=allowed_ilvl, width=150)
        area_cb.pack(anchor="w", pady=(0, 10))
        self.area_level_var.trace_add("write", self.update_tracker_from_popup)

        # --- BP Enchantment ---
        ctk.CTkLabel(frame, text="BP Enchantment:").pack(anchor="w", pady=(0, 3))
        enchant_cb = ctk.CTkComboBox(
            frame,
            variable=self.bp_enchantment_var,
            values=BP_ENCHANTMENT_OPTIONS,
            width=300
        )
        enchant_cb.pack(anchor="w", pady=(0, 10))
        self.bp_enchantment_var.trace_add("write", self.update_tracker_from_popup)

        # --- Info Labels ---
        info_texts = [
            "Changes are saved automatically to the tracker and settings."
        ]
        for text in info_texts:
            lbl = ctk.CTkLabel(frame, text=text, anchor="w", justify="left", wraplength=260)
            lbl.pack(anchor="w", pady=2)

        # --- Buttons ---
        ctk.CTkButton(frame, text="Refresh", width=100, command=self.refresh_info).pack(pady=(10, 5))
        ctk.CTkButton(frame, text="OK", width=100, command=popup.destroy).pack(pady=(0, 0))

        # Center popup on main application
        center_window_on_parent(
            popup,
            self.parent
        )

        popup.grab_set()
        popup.focus_force()

        # Initialize dropdowns from tracker
        self.refresh_info()

        popup.wait_window()

    def update_tracker_from_popup(self, *args):
        if self.updating_from_popup or not self.tracker:
            return

        self.updating_from_popup = True
        try:
            layout = self.blueprint_var.get()
            level = int(self.area_level_var.get() or 0)
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
