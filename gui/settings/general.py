import json
import os
import subprocess
import sys
from tkinter import colorchooser, filedialog

import customtkinter as ctk

import config as c
import custom_themes
from fonts import update_all_fonts, make_font
from gui import palette
from gui.ctksimplebox import CTkMessageBox
from logger import log_message
from settings import set_setting
from themes import apply_theme, needs_restart
from win_utils import center_window_on_parent


class GeneralSettingsMixin:
    # -------------------------------
    # General
    # -------------------------------
    def _build_general(self, frame):
        row = 0

        ctk.CTkLabel(frame, text="Theme:").grid(row=row, column=0, sticky="w")

        self.theme_cb = ctk.CTkComboBox(frame, variable=self.theme_selector_var,
                                        values=custom_themes.theme_names(), width=self.width,
                                        state="readonly", command=self._update_application_theme)

        self.theme_cb.grid(row=row, column=1, sticky="w")

        row += 1

        row_pad = (8, 0)
        gap = 6
        theme_tools = ctk.CTkFrame(frame, fg_color="transparent")
        theme_tools.grid(row=row, column=1, sticky="w", pady=row_pad)
        tool_width = (self.width - 2 * gap) // 3
        ctk.CTkButton(theme_tools, text="Editor…", width=tool_width,
                      command=self._open_theme_editor).grid(row=0, column=0, padx=(0, gap))
        ctk.CTkButton(theme_tools, text="Import…", width=tool_width,
                      command=self._import_theme).grid(row=0, column=1, padx=(0, gap))
        ctk.CTkButton(theme_tools, text="Folder", width=self.width - 2 * (tool_width + gap),
                      command=self._open_themes_folder).grid(row=0, column=2)

        row += 1

        ctk.CTkLabel(frame, text="Accent Colour:").grid(row=row, column=0, sticky="w", pady=row_pad)
        accent_row = ctk.CTkFrame(frame, fg_color="transparent")
        accent_row.grid(row=row, column=1, sticky="w", pady=row_pad)
        swatch_width, reset_width = 28, 70
        self.accent_swatch = ctk.CTkButton(accent_row, text="", width=swatch_width, height=28,
                                           border_width=1, command=self._pick_accent)
        self.accent_swatch.grid(row=0, column=0, padx=(0, gap))
        self.accent_label = ctk.CTkLabel(accent_row, text="", anchor="w",
                                         width=self.width - swatch_width - reset_width - 2 * gap)
        self.accent_label.grid(row=0, column=1, padx=(0, gap))
        ctk.CTkButton(accent_row, text="Default", width=reset_width,
                      command=lambda: self._set_accent("")).grid(row=0, column=2)
        self._refresh_accent_widgets()

        row += 1

        ctk.CTkLabel(frame, text="Font Family:").grid(row=row, column=0, sticky="w", pady=row_pad)
        font_cb = ctk.CTkComboBox(frame, variable=self.font_selector_var, values=c.available_fonts, width=self.width)
        font_cb.grid(row=row, column=1, sticky="w", pady=row_pad)
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

        if needs_restart(palette.ACTIVE_THEME, val):
            settings_window.after(100, lambda: self._prompt_theme_restart(val))
            return

        settings_window.after(
            100,
            lambda: self._apply_theme_safely(val)
        )

    def _prompt_theme_restart(self, val, what=None):
        settings_window = self.settings_window
        if not settings_window:
            return

        what = what or f"Switching to the {val} theme"
        restart = CTkMessageBox(settings_window).askyesno(
            "Restart Required",
            f"{what} requires restarting the application.\n\n"
            "Restart now? If you choose No, it will be applied the next time you start the app."
        )

        if restart:
            self._restart_application()
        else:
            self._restore_settings_window()

    def _restart_application(self):
        log_message("Theme Switch", "Restarting application to apply theme")

        if getattr(sys, "frozen", False):
            args = [sys.executable] + sys.argv[1:]
        else:
            args = [sys.executable] + sys.argv

        try:
            env = os.environ.copy()
            if getattr(sys, "frozen", False):
                env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
                for key in ("_MEIPASS2", "_PYI_APPLICATION_HOME_DIR",
                            "_PYI_ARCHIVE_FILE", "_PYI_PARENT_PROCESS_LEVEL"):
                    env.pop(key, None)
            subprocess.Popen(args, env=env)
        except Exception as error:
            log_message("Theme Switch", f"Failed to restart: {error}")
            CTkMessageBox(self.settings_window).showerror(
                "Restart Failed",
                "Could not restart automatically. Please restart the application manually."
            )
            return

        try:
            self.parent.winfo_toplevel().destroy()
        finally:
            os._exit(0)

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

    # -------------------------------
    # User themes & accent colour
    # -------------------------------
    def _refresh_theme_list(self):
        self.theme_cb.configure(values=custom_themes.theme_names())

    def _offer_theme(self, name):
        """Ask whether to switch to a newly saved/imported theme."""
        if not name or name == self.theme_selector_var.get():
            if name and name == palette.ACTIVE_THEME:
                self._prompt_theme_restart(name, f"Applying your changes to {name}")
            else:
                self._restore_settings_window()
            return
        if CTkMessageBox(self.settings_window).askyesno("Use Theme", f"Switch to the \"{name}\" theme now?"):
            self.theme_selector_var.set(name)
            self._update_application_theme(name)
        else:
            self._restore_settings_window()

    def _open_theme_editor(self):
        from gui.popups.theme_editor import ThemeEditorPopup

        try:
            self.settings_window.grab_release()
        except Exception:
            pass

        def on_close(saved_name):
            self._refresh_theme_list()
            current = self.theme_selector_var.get()
            if current not in custom_themes.theme_names():
                self.theme_selector_var.set("DARK")
                self._update_application_theme("DARK")
                return
            self._offer_theme(saved_name)

        ThemeEditorPopup(self.settings_window, start_theme=self.theme_selector_var.get(),
                         on_close=on_close)

    def _import_theme(self):
        path = filedialog.askopenfilename(parent=self.settings_window, title="Import Theme",
                                          filetypes=[("Theme files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            theme = custom_themes.import_theme(path)
        except (OSError, ValueError, json.JSONDecodeError) as e:
            CTkMessageBox(self.settings_window).showerror("Import Failed", f"Not a valid theme file:\n{e}")
            return
        log_message("Theme Import", theme["name"])
        self._refresh_theme_list()
        self._offer_theme(theme["name"])

    def _open_themes_folder(self):
        folder = custom_themes.THEMES_DIR
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            log_message("Theme Folder", f"Could not open {folder}: {e}")

    def _refresh_accent_widgets(self):
        override = custom_themes.accent_override()
        color = override or palette.ACCENT_HEX
        self.accent_swatch.configure(fg_color=color, hover_color=color)
        self.accent_label.configure(text=override or "Theme default")

    def _pick_accent(self):
        current = custom_themes.accent_override() or palette.ACCENT_HEX
        try:
            self.settings_window.grab_release()
        except Exception:
            pass
        _, hex_color = colorchooser.askcolor(color=current, parent=self.settings_window,
                                             title="Accent Colour")
        if hex_color:
            self._set_accent(hex_color.lower())
        else:
            self._restore_settings_window()

    def _set_accent(self, value):
        if (custom_themes.accent_override() or "") == value:
            self._restore_settings_window()
            return
        set_setting("Application", "accent_color", value)
        log_message("Accent Colour", value or "theme default")
        self._refresh_accent_widgets()
        self.settings_window.after(100, lambda: self._prompt_theme_restart(
            value, "Changing the accent colour"))

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
