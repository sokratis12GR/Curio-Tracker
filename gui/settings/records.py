import customtkinter as ctk

import config as c
from settings import set_setting


class RecordsSettingsMixin:
    # -------------------------------
    # Records / Duplicates
    # -------------------------------
    def _build_records(self, frame):
        row = 0

        ctk.CTkLabel(frame, text="CSV Current Record:").grid(row=row, column=0, sticky="w")
        csv_record_entry = ctk.CTkEntry(frame, state="disabled", textvariable=self.csv_current_record_number_var,
                                        width=self.width)
        csv_record_entry.grid(row=row, column=1, sticky="w")
        row += 1

        ctk.CTkLabel(frame, text="JSON Current Record:").grid(row=row, column=0, sticky="w")
        json_record_entry = ctk.CTkEntry(frame, state="disabled", textvariable=self.json_current_record_number_var,
                                         width=self.width)
        json_record_entry.grid(row=row, column=1, sticky="w")
        row += 1

        ctk.CTkLabel(frame, text="Seconds Between Dupe Checks:").grid(row=row, column=0, sticky="w")
        row += 1

        dupe_slider = ctk.CTkSlider(frame, from_=c.MIN_DUPE_DURATION, to=c.MAX_DUPE_DURATION,
                                    variable=self.dupe_duration)
        dupe_slider.grid(row=row, column=0, sticky="w", pady=(10, 0))
        dupe_slider.bind("<ButtonRelease-1>", lambda e: self._update_dupe_slider())

        self.dupe_label = ctk.CTkLabel(frame, text=f"{self.dupe_duration.get()}s")
        self.dupe_label.grid(row=row, column=1, sticky="w", padx=10, pady=(10, 0))

    def _update_dupe_slider(self):
        val = int(self.dupe_duration.get())

        if val == 0:
            return

        set_setting("Application", "time_last_dupe_check_seconds", val)
        self.dupe_label.configure(text=f"{val}s")
        self.tracker.set_duplicate_duration(val)
