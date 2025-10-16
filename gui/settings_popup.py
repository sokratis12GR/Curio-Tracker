from tkinter import colorchooser

import customtkinter as ctk
from customtkinter import CTkFrame

import config as c
import curio_collection_fetch
import toasts
from logger import log_message
from settings import get_setting, set_setting
from themes import apply_theme
from tree_manager import TreeManager


# -------------------------------
# Main Popup
# -------------------------------
class SettingsPopup:
    def __init__(self, parent, tracker, theme_manager, tree_manager):
        self.tracker = tracker
        self.theme_manager = theme_manager
        self.tree_manager = tree_manager

        self.popup = ctk.CTkToplevel(parent)
        self.popup.title("Application Settings")
        self.popup.geometry("420x540")
        self.popup.resizable(False, False)
        self.popup.grab_set()
        self.popup.focus_force()

        # Scrollable frame
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.popup,
            label_text="Configuration",
            label_font=("Segoe UI", 14, "bold"),
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=10)

        # Unified section
        self.app_section = UnifiedSettingsSection(parent, tracker, theme_manager, tree_manager)
        row = 0
        row = self.app_section.build(self.scroll_frame, row)

        # Bottom button
        bottom_frame = ctk.CTkFrame(self.popup, fg_color="transparent")
        bottom_frame.pack(fill="x", pady=(5, 10))
        ctk.CTkButton(bottom_frame, text="Close", command=self.popup.destroy, width=100).pack(pady=5)

        # Center popup
        self.popup.update_idletasks()
        w, h = self.popup.winfo_width(), self.popup.winfo_height()
        x = (self.popup.winfo_screenwidth() // 2) - (w // 2)
        y = (self.popup.winfo_screenheight() // 2) - (h // 2)
        self.popup.geometry(f"{w}x{h}+{x}+{y}")


# -------------------------------
# Unified Section (All Settings)
# -------------------------------
class UnifiedSettingsSection:
    def __init__(self, parent, tracker, theme_manager, tree_manager: TreeManager):
        self.fetch_collection_btn = None
        self.color_preview = None
        self.parent = parent
        self.tracker = tracker
        self.theme_manager = theme_manager
        self.tree_manager = tree_manager

        # Variables
        self.theme_selector_var = ctk.StringVar(value=get_setting("Application", "theme_mode", c.DEFAULT_THEME_MODE))
        self.toasts_var = ctk.BooleanVar(value=toasts.ARE_TOASTS_ENABLED)
        self.toasts_duration_var = ctk.StringVar(value=str(toasts.TOASTS_DURATION))
        self.is_ssf_league_var = ctk.BooleanVar(value=get_setting("Application", "is_ssf", c.IS_SSF))
        self.enable_poeladder_var = ctk.BooleanVar(
            value=get_setting("Application", "enable_poeladder", c.ENABLE_POELADDER))
        self.data_league_var = ctk.StringVar(value=get_setting("Application", "data_league", c.LEAGUE))
        self.poe_player_var = ctk.StringVar(value=get_setting("User", "poe_user", ""))
        self.user_league_var = ctk.StringVar(value=get_setting("User", "poe_league", c.poe_league))
        self.dupe_duration = ctk.IntVar(value=get_setting("Application", "time_last_dupe_check_seconds", 60))
        self.collection_missing_color_var = ctk.StringVar(
            value=get_setting("Application", "collection_missing_color", "#FF0000")  # default red
        )

        self.dupe_label = None

    def build(self, frame, row_start):
        row = row_start

        # ---- Header ----
        ctk.CTkLabel(frame, text="Application Settings", font=("Segoe UI", 15, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(5, 10)
        )
        row += 1

        # ---- Theme ----
        ctk.CTkLabel(frame, text="Theme (requires restart):").grid(row=row, column=0, sticky="w")
        theme_cb = ctk.CTkComboBox(frame, variable=self.theme_selector_var, values=c.theme_modes, width=170)
        theme_cb.grid(row=row, column=1, sticky="w")
        self.theme_selector_var.trace_add("write", self._update_application_theme)
        row += 1
        add_separator(frame, row)
        row += 1

        # ---- Player ----
        ctk.CTkLabel(frame, text="Player & League Setup", font=("Segoe UI", 13, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(5, 5)
        )
        row += 1

        ctk.CTkLabel(frame, text="PoE Profile (player#1234):").grid(row=row, column=0, sticky="w")
        poe_entry = ctk.CTkEntry(frame, textvariable=self.poe_player_var, width=170)
        poe_entry.grid(row=row, column=1, sticky="w")
        self.poe_player_var.trace_add("write", self._update_tracker_poe_player)
        row += 1

        # ---- Player League ----
        ctk.CTkLabel(frame, text="League Version:").grid(row=row, column=0, sticky="w")
        league_cb = ctk.CTkComboBox(frame, variable=self.user_league_var, values=c.league_versions, width=170)
        league_cb.grid(row=row, column=1, sticky="w")
        self.user_league_var.trace_add("write", self._update_tracker_league)
        row += 1

        # ---- Data League ----
        ctk.CTkLabel(frame, text="Data League:").grid(row=row, column=0, sticky="w")
        league_cb2 = ctk.CTkComboBox(frame, variable=self.data_league_var, values=c.LEAGUES_TO_FETCH, width=170)
        league_cb2.grid(row=row, column=1, sticky="w")
        self.data_league_var.trace_add("write", self._on_data_league_change)
        row += 1
        fetch_btn_state = "normal" if self.enable_poeladder_var.get() else "disabled"
        self.fetch_collection_btn = ctk.CTkButton(frame, text="Fetch Collection", state=fetch_btn_state,
                                                  command=self._fetch_poeladder,
                                                  width=370)
        self.fetch_collection_btn.grid(row=row, column=0, columnspan=2, sticky="w", pady=(5, 10))
        row += 1

        ctk.CTkCheckBox(frame, text="Enable PoE Ladder", variable=self.enable_poeladder_var,
                        command=self._toggle_poeladder).grid(
            row=row, column=0, columnspan=1, sticky="w"
        )

        ctk.CTkCheckBox(frame, text="SSF", variable=self.is_ssf_league_var, command=self._toggle_ssf_league).grid(
            row=row, column=1, columnspan=1, sticky="w"
        )
        row += 1

        add_separator(frame, row)
        row += 1

        # ---- Toasts ----
        ctk.CTkLabel(frame, text="Toasts / Notifications", font=("Segoe UI", 13, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(5, 5)
        )
        row += 1

        ctk.CTkCheckBox(frame, text="Enable Toasts", variable=self.toasts_var, command=self._toggle_toasts).grid(
            row=row, column=0, columnspan=2, sticky="w"
        )
        row += 1

        ctk.CTkLabel(frame, text="Duration (sec):").grid(row=row, column=0, sticky="w")
        duration_entry = ctk.CTkEntry(frame, textvariable=self.toasts_duration_var, width=170)
        duration_entry.grid(row=row, column=1, sticky="w")
        self.toasts_duration_var.trace_add("write", self._update_toasts_duration)
        row += 1

        # ---- Collection Missing Color ----
        ctk.CTkLabel(frame, text="Collection Missing Color:").grid(row=row, column=0, sticky="w")

        # Preview color box
        self.color_preview = ctk.CTkFrame(frame, width=60, height=25, fg_color=self.collection_missing_color_var.get())
        self.color_preview.grid(row=row, column=1, sticky="w", padx=(0, 10))

        # Button to open color picker
        pick_btn = ctk.CTkButton(frame, text="Pick", width=60, command=self._pick_collection_color)
        pick_btn.grid(row=row, column=1, sticky="e")

        row += 1

        # ---- Duplicate Check ----
        ctk.CTkLabel(frame, text="Seconds Between Dupe Checks:").grid(row=row, column=0, sticky="w")
        row += 1
        dupe_slider = ctk.CTkSlider(
            frame, from_=c.MIN_DUPE_DURATION, to=c.MAX_DUPE_DURATION, variable=self.dupe_duration
        )
        dupe_slider.grid(row=row, column=0, sticky="w", pady=(10, 0))
        dupe_slider.bind("<ButtonRelease-1>", lambda e: self._update_dupe_slider())

        self.dupe_label = ctk.CTkLabel(frame, text=f"{self.dupe_duration.get()}s")
        self.dupe_label.grid(row=row, column=1, sticky="w", padx=10, pady=(10, 0))
        row += 1

        return row

    # ---- Handlers ----
    def _update_application_theme(self, *_):
        val = self.theme_selector_var.get()
        if not val:
            return
        log_message("Theme Selector", val)
        set_setting("Application", "theme_mode", val)
        switch_mode(self.tree_manager, self.tracker, val)

    def _toggle_toasts(self):
        enabled = self.toasts_var.get()
        set_setting("Application", "are_toasts_enabled", enabled)
        toasts.toggle_toasts(enabled)

    def _pick_collection_color(self):
        color_code = colorchooser.askcolor(title="Choose Collection Missing Color")
        if color_code and color_code[1]:
            chosen = color_code[1]
            self.collection_missing_color_var.set(chosen)
            self.color_preview.configure(fg_color=chosen)
            set_setting("Application", "collection_missing_color", chosen)
            log_message("Collection Missing Color set to", chosen)

    def _update_toasts_duration(self, *_):
        val = self.toasts_duration_var.get().strip()
        dur = int(val) if val else 5
        set_setting("Application", "toasts_duration_seconds", dur)
        toasts.set_toast_duration(dur)

    def _toggle_ssf_league(self):
        enabled = self.is_ssf_league_var.get()
        set_setting("Application", "is_ssf", enabled)
        data_league = get_setting("Application", "data_league")
        mutated_val = "SSF " + data_league if enabled else data_league
        for ladder_key, ladder_identifier in c.POELADDER_LADDERS.items():
            if ladder_key == mutated_val:
                set_setting("Application", "poeladder_data_league", ladder_identifier)
        self.tracker.on_league_change()
        self.tree_manager.refresh_treeview(self.tracker)

    def _toggle_poeladder(self):
        enabled = self.enable_poeladder_var.get()
        set_setting("Application", "enable_poeladder", enabled)
        log_message("poeladder", enabled)
        fetch_btn_state = "normal" if enabled else "disabled"
        if hasattr(self, "fetch_collection_btn"):
            self.fetch_collection_btn.configure(state=fetch_btn_state)
        # self.tree_manager.refresh_treeview(self.tracker)

    def _fetch_poeladder(self):
        player = self.poe_player_var.get()
        log_message(f"Fetching poeladder collection for {player}")
        curio_collection_fetch.run_fetch_curios_threaded(player)

    def _update_dupe_slider(self):
        val = int(self.dupe_duration.get())
        if val == 0:
            return
        set_setting("Application", "time_last_dupe_check_seconds", val)
        self.dupe_label.configure(text=f"{val}s")
        self.tracker.set_duplicate_duration(val)

    def _on_data_league_change(self, *_):
        val = self.data_league_var.get()
        if not val:
            return
        set_setting("Application", "data_league", val)
        is_ssf = get_setting("Application", "is_ssf")
        mutated_val = "SSF " + val if is_ssf else val
        for ladder_key, ladder_identifier in c.POELADDER_LADDERS.items():
            if ladder_key == mutated_val:
                set_setting("Application", "poeladder_data_league", ladder_identifier)
        self.tracker.on_league_change()
        self.tree_manager.refresh_treeview(self.tracker)

    def _update_tracker_poe_player(self, *_):
        val = self.poe_player_var.get()
        if not val:
            return
        set_setting("User", "poe_user", val)
        self.tracker.poe_user = val

    def _update_tracker_league(self, *_):
        val = self.user_league_var.get()
        if not val:
            return
        set_setting("User", "poe_league", val)
        self.tracker.league_version = val


# -------------------------------
# Helper functions
# -------------------------------
def switch_mode(tree_manager: TreeManager, tracker, mode=c.DEFAULT_THEME_MODE):
    apply_theme(mode=mode)


def add_separator(parent, row_index):
    separator = CTkFrame(parent, height=2, fg_color="#a0a0a0")
    separator.grid(row=row_index, column=0, columnspan=2, sticky="ew", pady=(10, 10))


def show_settings_popup(parent, tracker, theme_manager, tree_manager):
    SettingsPopup(parent, tracker, theme_manager, tree_manager)
