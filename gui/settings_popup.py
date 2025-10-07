# settings_popup.py
import tkinter as tk
from tkinter import ttk
import config as c
import toasts
from settings import get_setting, set_setting


class SettingsPopup:
    def __init__(self, parent, tracker, on_league_change_callback=None):
        self.parent = parent
        self.tracker = tracker
        self.on_league_change_callback = on_league_change_callback

        self.popup = tk.Toplevel(parent)
        self.popup.title("Application Settings")
        self.popup.geometry("280x400")
        self.popup.resizable(False, False)
        self.popup.grab_set()  # make modal

        frame = ttk.Frame(self.popup, padding=15)
        frame.pack(fill="both", expand=True)

        row = 0
        def next_row(increment=1):
            nonlocal row
            row += increment
            return row

        ttk.Label(
            frame,
            text="Configuration",
            font=("Segoe UI", 13, "bold")
        ).grid(row=row, column=0, columnspan=3, sticky="w")

        next_row()
        ttk.Label(frame, text="Player Info", font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(10, 5)
        )

        # --- PoE Player Entry ---
        next_row()
        ttk.Label(frame, text="PoE Player:").grid(row=row, column=0, sticky="w")
        self.poe_player_var = tk.StringVar(value=get_setting("User", "poe_user", ""))
        poe_entry = ttk.Entry(frame, textvariable=self.poe_player_var, width=20)
        poe_entry.grid(row=row, column=1, sticky="w")
        self.poe_player_var.trace_add("write", self._update_tracker_poe_player)

        # --- League Selection for User ---
        next_row()
        ttk.Label(frame, text="League:").grid(row=row, column=0, sticky="w", pady=(5, 5))
        self.user_league_var = tk.StringVar(value=get_setting("User", "poe_league", c.poe_league))
        self.user_league_cb = ttk.Combobox(
            frame,
            textvariable=self.user_league_var,
            values=c.league_versions,
            state="readonly",
            width=20
        )
        self.user_league_cb.grid(row=row, column=1, sticky="w")
        self.user_league_var.trace_add("write", self._update_tracker_league)
        next_row()
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=12
        )
        next_row()

        ttk.Label(frame, text="Toasts:", font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(5, 5)
        )

        next_row()
        self.toasts_var = tk.BooleanVar(value=toasts.ARE_TOASTS_ENABLED)
        self.toasts_checkbox = ttk.Checkbutton(
            frame,
            text="Enable Toasts",
            variable=self.toasts_var,
            command=lambda: toasts.toggle_toasts(self.toasts_var.get())  # module-level function
        )
        self.toasts_checkbox.grid(row=row, column=0, sticky="w")
        self.toasts_checkbox.configure(style="Toasts.TCheckbutton")

        next_row()

        # Spinbox for toast duration
        ttk.Label(frame, text="Duration:").grid(row=row, column=0, sticky="w")
        self.toasts_duration_var = tk.IntVar(value=toasts.TOASTS_DURATION)

        self.toasts_duration_spinbox = ttk.Spinbox(
            frame,
            from_=1,
            to=30,
            width=5,
            textvariable=self.toasts_duration_var,
            validate='all',
            validatecommand=(frame.register(self.validate_duration), '%P')  # optional validation
        )
        self.toasts_duration_spinbox.grid(row=row, column=1, sticky="w")

        # Trace changes to update global toast duration
        self.toasts_duration_var.trace_add(
            "write",
            lambda *args: toasts.set_toast_duration(
                max(1, min(30, self.toasts_duration_var.get()))
            )
        )

        next_row()
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=12
        )

        next_row()
        ttk.Label(frame, text="Data Fetching", font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(5, 5)
        )

        next_row()
        ttk.Label(frame, text="poe.ninja", font=("Segoe UI", 8, "bold")).grid(
            row=row, column=0, columnspan=1, sticky="w", pady=(5, 5)
        )

        next_row()
        ttk.Label(frame, text="Select League:").grid(row=row, column=0, sticky="w")
        self.league_options = c.LEAGUES_TO_FETCH
        current_league = get_setting("Application", "data_league", c.LEAGUE)
        if current_league not in self.league_options:
            current_league = c.LEAGUE

        self.league_var = tk.StringVar(value=current_league)
        self.league_dropdown = ttk.Combobox(
            frame,
            textvariable=self.league_var,
            values=self.league_options,
            state="readonly",
            width=20
        )
        self.league_dropdown.grid(row=row, column=1, columnspan=2, sticky="w")
        self.league_dropdown.bind("<<ComboboxSelected>>", self._on_league_change)

        next_row()
        ttk.Separator(frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=10
        )

        next_row()
        bottom_frame = ttk.Frame(frame)
        bottom_frame.grid(row=row, column=0, columnspan=3, pady=(0, 5))
        ttk.Button(bottom_frame, text="Close", command=self.popup.destroy).pack(side="left", padx=5)

    # --- Methods for updating tracker/user settings ---
    def _update_tracker_poe_player(self, *args):
        value = self.poe_player_var.get()
        if hasattr(self, "tracker"):
            self.tracker.poe_user = value
        set_setting("User", "poe_user", value)

    def _update_tracker_league(self, *args):
        value = self.user_league_var.get()
        if hasattr(self, "tracker"):
            self.tracker.league_version = value
        set_setting("User", "poe_league", value)

    def toggle_toasts(self):
        enabled = self.toasts_var.get()
        set_setting('Application', 'are_toasts_enabled', enabled)
        if c.DEBUGGING:
            print(f"[DEBUG] Toasts enabled: {enabled}")

    def validate_duration(self, new_value):
        if not new_value:
            return True
        if new_value.isdigit():
            value = int(new_value)
            return 1 <= value <= 30
        return False

    def update_toasts_duration(self, *args):
        try:
            duration = int(self.toasts_duration_var.get())
        except ValueError:
            duration = 5
            self.toasts_duration_var.set(str(duration))

        duration = max(1, min(duration, 30))
        self.toasts_duration_var.set(str(duration))
        toasts.TOASTS_DURATION = duration
        set_setting('Application', 'toasts_duration_seconds', duration)

        if c.DEBUGGING:
            print(f"[DEBUG] Toasts Duration set to: {duration}s")

    def _on_league_change(self, event):
        new_league = self.league_var.get()
        set_setting("Application", "data_league", new_league)
        if hasattr(self, "tracker"):
            self.reload_tree_for_league(new_league)

    def reload_tree_for_league(self, new_league):
        self.tracker.on_league_change(new_league)


def show_settings_popup(parent, tracker):
    SettingsPopup(parent, tracker)
