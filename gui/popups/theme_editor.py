"""Create, edit and delete user themes (see custom_themes.py)."""

from tkinter import colorchooser

import customtkinter as ctk

import custom_themes as ct
from fonts import make_font
from gui.ctksimplebox import CTkMessageBox
from win_utils import center_window_on_parent, prepare_popup

NEW_THEME = "(new theme)"


class ThemeEditorPopup:
    """on_close(saved_name_or_None) runs when the editor closes."""

    def __init__(self, parent, start_theme=None, on_close=None):
        self.parent = parent
        self.on_close = on_close
        self.saved_name = None
        self.themes = ct.list_themes()

        self.popup = ctk.CTkToplevel(parent)
        prepare_popup(self.popup)
        self.popup.title("Theme Editor")
        self.popup.resizable(False, False)
        self.popup.transient(parent.winfo_toplevel())
        self.popup.protocol("WM_DELETE_WINDOW", self._close)
        self.popup.bind("<Escape>", lambda e: self._close())

        frame = ctk.CTkFrame(self.popup)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Edit theme:").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.source_var = ctk.StringVar(value=NEW_THEME)
        ctk.CTkOptionMenu(frame, variable=self.source_var, values=[NEW_THEME] + sorted(self.themes),
                          width=200, command=self._load_source
                          ).grid(row=0, column=1, columnspan=3, sticky="w", padx=10, pady=(10, 4))

        ctk.CTkLabel(frame, text="Name:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.name_var = ctk.StringVar()
        ctk.CTkEntry(frame, textvariable=self.name_var, width=200
                     ).grid(row=1, column=1, columnspan=3, sticky="w", padx=10, pady=4)

        ctk.CTkLabel(frame, text="Based on:").grid(row=2, column=0, sticky="w", padx=10, pady=4)
        self.base_var = ctk.StringVar(value="DARK")
        ctk.CTkOptionMenu(frame, variable=self.base_var, values=list(ct.BUILTIN_MODES), width=200,
                          command=lambda _v: self._refresh_rows()
                          ).grid(row=2, column=1, columnspan=3, sticky="w", padx=10, pady=4)

        ctk.CTkLabel(frame, text="Colours (leave blank to keep the base colour)",
                     font=make_font(11), text_color="gray60"
                     ).grid(row=3, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 2))

        self.color_vars = {}
        self.swatches = {}
        for i, (role, (label, _)) in enumerate(ct.ROLES.items(), start=4):
            ctk.CTkLabel(frame, text=label).grid(row=i, column=0, sticky="w", padx=10, pady=2)
            var = ctk.StringVar()
            var.trace_add("write", lambda *_a, r=role: self._update_swatch(r))
            self.color_vars[role] = var
            entry = ctk.CTkEntry(frame, textvariable=var, width=100)
            entry.grid(row=i, column=1, sticky="w", padx=(10, 4), pady=2)
            swatch = ctk.CTkButton(frame, text="", width=28, height=24, border_width=1,
                                   command=lambda r=role: self._pick(r))
            swatch.grid(row=i, column=2, padx=4, pady=2)
            self.swatches[role] = swatch
            ctk.CTkButton(frame, text="Reset", width=56, height=24, fg_color="transparent",
                          border_width=1, command=lambda v=var: v.set("")
                          ).grid(row=i, column=3, padx=(4, 10), pady=2)

        row = 4 + len(ct.ROLES)
        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.grid(row=row, column=0, columnspan=4, sticky="we", padx=10, pady=(12, 10))
        buttons.grid_columnconfigure(1, weight=1)
        self.delete_btn = ctk.CTkButton(buttons, text="Delete", width=80, fg_color="transparent",
                                        border_width=1, text_color=("#c62828", "#ed4245"),
                                        command=self._delete)
        self.delete_btn.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(buttons, text="Cancel", width=80, command=self._close).grid(row=0, column=2, padx=(0, 6))
        ctk.CTkButton(buttons, text="Save", width=80, command=self._save).grid(row=0, column=3)

        if start_theme in self.themes:
            self.source_var.set(start_theme)
            self._load_source(start_theme)
        else:
            self._load_source(NEW_THEME)

        center_window_on_parent(self.popup, parent)
        self.popup.after(50, self._grab)

    def _grab(self):
        try:
            self.popup.grab_set()
            self.popup.focus_force()
        except Exception:
            pass

    # ---------- State ----------
    def _load_source(self, value):
        theme = self.themes.get(value)
        if theme is None:
            self.name_var.set("")
            self.base_var.set("DARK")
            colors = {}
            self.delete_btn.grid_remove()
        else:
            self.name_var.set(theme["name"])
            self.base_var.set(theme["base"])
            colors = theme["colors"]
            self.delete_btn.grid()
        for role, var in self.color_vars.items():
            var.set(colors.get(role, ""))
        self._refresh_rows()

    def _refresh_rows(self):
        for role in self.color_vars:
            self._update_swatch(role)

    def _effective(self, role):
        value = self.color_vars[role].get().strip()
        if ct.is_hex(value):
            return value
        return ct.default_color(role, self.base_var.get())

    def _update_swatch(self, role):
        color = self._effective(role)
        swatch = self.swatches.get(role)
        if swatch is None:
            return
        if color:
            swatch.configure(fg_color=color, hover_color=color, state="normal")
        else:
            swatch.configure(fg_color="transparent", hover_color="gray40")

    def _pick(self, role):
        initial = self._effective(role) or "#808080"
        _, hex_color = colorchooser.askcolor(color=initial, parent=self.popup,
                                             title=ct.ROLES[role][0])
        if hex_color:
            self.color_vars[role].set(hex_color.lower())

    # ---------- Actions ----------
    def _collect(self):
        colors, bad = {}, []
        for role, var in self.color_vars.items():
            value = var.get().strip()
            if not value:
                continue
            if not ct.is_hex(value):
                bad.append(ct.ROLES[role][0])
            else:
                colors[role] = value.lower()
        if bad:
            raise ValueError("Use #rrggbb colours for: " + ", ".join(bad))
        return {"name": self.name_var.get().strip(), "base": self.base_var.get(), "colors": colors}

    def _save(self):
        try:
            theme = ct.validate_theme(self._collect())
            old = self.source_var.get()
            if theme["name"] != old and theme["name"] in self.themes:
                if not CTkMessageBox(self.popup).askyesno(
                        "Overwrite Theme", f"A theme called \"{theme['name']}\" already exists. Overwrite it?"):
                    return
            ct.save_theme(theme)
        except (ValueError, OSError) as e:
            CTkMessageBox(self.popup).showerror("Can't Save Theme", str(e))
            return
        self.saved_name = theme["name"]
        self._close()

    def _delete(self):
        name = self.source_var.get()
        if name not in self.themes:
            return
        if not CTkMessageBox(self.popup).askyesno("Delete Theme", f"Delete the theme \"{name}\"?"):
            return
        try:
            ct.delete_theme(name)
        except OSError as e:
            CTkMessageBox(self.popup).showerror("Can't Delete Theme", str(e))
            return
        self._close()

    def _close(self):
        try:
            self.popup.grab_release()
            self.popup.destroy()
        except Exception:
            pass
        if self.on_close:
            self.on_close(self.saved_name)
