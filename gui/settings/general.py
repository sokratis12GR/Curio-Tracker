import customtkinter as ctk

import config as c
from fonts import update_all_fonts, make_font
from logger import log_message
from settings import set_setting
from themes import apply_theme
from win_utils import center_window_on_parent


class GeneralSettingsMixin:
    # -------------------------------
    # General
    # -------------------------------
    def _build_general(self, frame):
        row = 0

        ctk.CTkLabel(frame, text="Theme:").grid(row=row, column=0, sticky="w")

        theme_cb = ctk.CTkComboBox(frame, variable=self.theme_selector_var, values=c.theme_modes, width=self.width,
                                   state="readonly", command=self._update_application_theme)

        theme_cb.grid(row=row, column=1, sticky="w")

        row += 1

        ctk.CTkLabel(frame, text="Font Family:").grid(row=row, column=0, sticky="w")
        font_cb = ctk.CTkComboBox(frame, variable=self.font_selector_var, values=c.available_fonts, width=self.width)
        font_cb.grid(row=row, column=1, sticky="w")
        self.font_selector_var.trace_add("write", self._update_application_font)
        row += 1

        ctk.CTkLabel(frame, text="(Experimental)", font=make_font(12, "bold")).grid(row=row, column=0, sticky="w",
                                                                                    pady=(5, 0))
        row += 1

        ctk.CTkCheckBox(frame, text="Enable HDR Filtering", variable=self.enable_hdr_filtering_var,
                        command=self._toggle_hdr).grid(row=row, column=0, columnspan=2, sticky="w")

    # -------------------------------
    # Application Handlers
    # -------------------------------
    def _update_application_theme(self, val):
        if not val:
            return

        log_message(
            "Theme Selector",
            val
        )

        set_setting(
            "Application",
            "theme_mode",
            val
        )

        settings_window = self.settings_window

        if not settings_window:
            return

        settings_window.after(
            100,
            lambda: self._apply_theme_safely(val)
        )

    def _apply_theme_safely(self, val):
        settings_window = self.settings_window

        if not settings_window:
            return

        try:
            if not settings_window.winfo_exists():
                return
        except Exception:
            return

        try:
            settings_window.grab_release()
        except Exception:
            pass

        apply_theme(val)

        settings_window.after(
            100,
            self._restore_settings_window
        )

    def _restore_settings_window(self):
        settings_window = self.settings_window

        if not settings_window:
            return

        try:
            if not settings_window.winfo_exists():
                return

            settings_window.deiconify()
            settings_window.lift()

            center_window_on_parent(
                settings_window,
                self.parent
            )

            settings_window.grab_set()
            settings_window.focus_force()

        except Exception as error:
            log_message(
                "Theme Switch",
                f"Failed to restore settings window: {error}"
            )

    def _update_application_font(self, *_):
        new_family = self.font_selector_var.get()
        if not new_family:
            return

        set_setting("Application", "font_family", new_family)

        from fonts import font_family_var, _ensure_font_var

        _ensure_font_var(master=self.parent)
        font_family_var.set(new_family)
        update_all_fonts(self.parent)

    def _toggle_hdr(self):
        enabled = self.enable_hdr_filtering_var.get()
        set_setting("Application", "is_hdr_filtering_enabled", enabled)
        log_message("HDR", enabled)
        c.IS_HDR_ENABLED = enabled
