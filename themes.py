import tkinter as tk
from tkinter import ttk

class Themes:
    def __init__(self, root, style, console_output=None, menu=None, menu_indices=None, menu_btn=None):
        self.root = root
        self.style = style
        self.console_output = console_output
        self.menu = menu
        self.menu_indices = menu_indices or {}
        self.menu_btn = menu_btn

        self.is_dark_mode = True
        self.widgets = {
            "buttons": [],
            "comboboxes": [],
            "sliders": [],
            "spinboxes": [],
            "entries": [],
            "labels": [],
            "headers": [],
            "menus": [],
            "frames": [],
            "labelframes": []
        }

    def set_header_widgets(self, header_widgets):
        self.widgets["headers"].extend(header_widgets)

    def register(self, widget, widget_type=None):
        if widget_type is None:
            cls_name = widget.winfo_class()
            if cls_name in ("TButton", "Button"):
                widget_type = "buttons"
            elif cls_name in ("TCombobox", "Combobox"):
                widget_type = "comboboxes"
            elif cls_name in ("Scale", "TScale"):
                widget_type = "sliders"
            elif cls_name in ("Spinbox", "TSpinbox"):
                widget_type = "spinboxes"
            elif cls_name in ("Entry", "TEntry"):
                widget_type = "entries"
            elif cls_name in ("TLabel", "Label"):
                widget_type = "labels"
            elif cls_name in ("TFrame", "Frame"):
                widget_type = "frames"
            elif cls_name in ("TLabelframe", "Labelframe"):
                widget_type = "labelframes"
            elif cls_name == "Menu":
                widget_type = "menus"
            else:
                return
        self.widgets[widget_type].append(widget)

    def style_combobox_popup(self, combobox, widget_bg, fg, accent):
        def fix_colors():
            try:
                combobox.tk.call("ttk::combobox::PopdownWindow", combobox, "f.l").configure(background=widget_bg)
            except Exception:
                pass

        combobox.configure(postcommand=fix_colors)

    def apply_theme(self, is_dark_mode=True):
        self.is_dark_mode = is_dark_mode

        # --- Old colors ---
        if is_dark_mode:
            app_bg, panel_bg, widget_bg, accent, fg = "#2f3136", "#36393f", "#40444b", "#5865f2", "#dcddde"
        else:
            app_bg, panel_bg, widget_bg, accent, fg = "#f4f6f8", "#f4f6f8", "white", "#0078d7", "black"

        # --- Root ---
        self.root.configure(bg=app_bg)

        # --- ttk Styles ---
        self.style.configure("TFrame", background=panel_bg)
        self.style.configure("TLabel", background=panel_bg, foreground=fg)
        self.style.configure("TLabelframe", background=panel_bg)  # dark default
        self.style.configure("TLabelframe.Label", background=panel_bg, foreground=fg)  # label text
        self.style.configure("Header.TLabel", background=panel_bg, foreground=fg)
        self.style.configure("TButton", background=widget_bg, foreground=fg, relief="flat", padding=4)
        self.style.map("TButton", background=[("active", accent)], foreground=[("active", "white")])
        self.style.configure("TEntry", fieldbackground=widget_bg, foreground=fg, borderwidth=0, insertcolor=fg)
        self.style.configure("TCombobox", fieldbackground=widget_bg, background=widget_bg, foreground=fg, arrowcolor=fg)
        self.style.map("TCombobox",
                       fieldbackground=[("readonly", widget_bg)],
                       foreground=[("readonly", fg)],
                       selectbackground=[("readonly", accent)],
                       selectforeground=[("readonly", "white")])

        # --- Buttons ---
        for btn in self.widgets["buttons"]:
            try:
                btn.configure(bg=widget_bg, fg=fg, activebackground=accent)
            except tk.TclError:
                pass

        # --- Entries ---
        for entry in self.widgets["entries"]:
            try:
                entry.configure(bg=widget_bg, fg=fg, insertbackground=fg)
            except tk.TclError:
                pass

        # --- Comboboxes ---
        for cb in self.widgets["comboboxes"]:
            try:
                cb.configure(background=widget_bg, foreground=fg)
            except tk.TclError:
                pass
            self.style_combobox_popup(cb, widget_bg, fg, accent)

        # --- Sliders ---
        for slider in self.widgets["sliders"]:
            slider.configure(background=panel_bg, troughcolor=widget_bg,
                             fg=fg, highlightbackground=panel_bg,
                             activebackground=accent, bd=0, relief="flat")

        # --- Spinboxes ---
        for sb in self.widgets["spinboxes"]:
            try:
                if isinstance(sb, tk.Spinbox):
                    sb.configure(bg=widget_bg, fg=fg, relief="flat",
                                 highlightthickness=0, justify="center", insertbackground=fg)
            except tk.TclError:
                pass

        # --- Headers ---
        for lbl in self.widgets["headers"]:
            try:
                lbl.configure(bg=panel_bg, fg=fg)
            except tk.TclError:
                lbl_style = lbl.cget("style") or "Header.TLabel"
                self.style.configure(lbl_style, background=panel_bg, foreground=fg)

            if isinstance(lbl, tk.Label):
                lbl.bind("<Enter>", lambda e, w=lbl: w.configure(bg=accent))
                lbl.bind("<Leave>", lambda e, w=lbl: w.configure(bg=panel_bg))

        # --- Frames ---
        for frame in self.widgets["frames"]:
            try:
                frame.configure(bg=panel_bg)
            except tk.TclError:
                pass

        # --- LabelFrames ---
        for lf in self.widgets["labelframes"]:
            try:
                lf.configure(bg=panel_bg)
            except tk.TclError:
                pass

        # --- Menus ---
        for menu in self.widgets["menus"]:
            for i in range(menu.index("end") + 1 if menu.index("end") is not None else 0):
                menu.entryconfig(i, background=widget_bg, foreground=fg,
                                 activebackground=accent, activeforeground="white")

        # --- Menu button ---
        if self.menu_btn and hasattr(self.menu_btn, "configure"):
            self.menu_btn.configure(style="MenuButton.TMenubutton")
            self.style.configure("MenuButton.TMenubutton", background=widget_bg, foreground=fg)
            self.style.map("MenuButton.TMenubutton",
                           background=[("active", accent)],
                           foreground=[("active", "white")])

        # --- Console Output ---
        if isinstance(self.console_output, tk.Text):
            self.console_output.config(bg=widget_bg, fg=fg, insertbackground=fg,
                                       highlightthickness=0 if self.is_dark_mode else 1,
                                       relief="flat" if self.is_dark_mode else "solid")

        # --- Treeview ---
        self.style.configure("Treeview",
                             background=widget_bg,
                             fieldbackground=widget_bg,
                             foreground=fg,
                             bordercolor=panel_bg,
                             borderwidth=0,
                             rowheight=40)
        self.style.map("Treeview",
                       background=[("selected", accent)],
                       foreground=[("selected", "white")])

        self.style.configure("Treeview.Heading",
                             background=panel_bg if is_dark_mode else "#e0e0e0",
                             foreground=fg,
                             relief="flat")
        self.style.map("Treeview.Heading",
                       background=[("active", accent), ("!active", panel_bg if is_dark_mode else "#e0e0e0")],
                       foreground=[("active", "white"), ("!active", fg)])

        self.style.configure(
            "Toasts.TCheckbutton",
            background=panel_bg,
            foreground=fg,
        )
        self.style.map(
            "Toasts.TCheckbutton",
            background=[("active", accent)],
            foreground=[("active", "white")],
        )

        # --- Scrollbars ---
        self.style.configure(
            "Vertical.TScrollbar",
            gripcount=0,
            background=widget_bg,
            darkcolor=widget_bg,
            lightcolor=widget_bg,
            troughcolor=panel_bg,
            bordercolor=panel_bg,
            arrowcolor=fg,
            relief="flat",
        )
        self.style.map(
            "Vertical.TScrollbar",
            background=[("active", accent)],
            troughcolor=[("!disabled", panel_bg)],
            arrowcolor=[("active", "white")],
        )
        self.style.configure(
            "Horizontal.TScrollbar",
            gripcount=0,
            background=widget_bg,
            darkcolor=widget_bg,
            lightcolor=widget_bg,
            troughcolor=panel_bg,
            bordercolor=panel_bg,
            arrowcolor=fg,
            relief="flat",
        )
        self.style.map(
            "Horizontal.TScrollbar",
            background=[("active", accent)],
            troughcolor=[("!disabled", panel_bg)],
            arrowcolor=[("active", "white")],
        )

        for cb in self.widgets["comboboxes"]:
            try:
                cb.configure(background=widget_bg, foreground=fg)
            except tk.TclError:
                pass
            self.style_combobox_popup(cb, widget_bg, fg, accent)

        # --- Spinbox ---
        self.style.configure(
            "TSpinbox",
            fieldbackground=widget_bg,
            background=widget_bg,
            foreground=fg,
            arrowcolor=fg,
        )

        self.style.configure(
            "MenuButton.TMenubutton",
            background=widget_bg,
            foreground=fg,
            relief="flat",
            padding=4
        )
        self.style.map(
            "MenuButton.TMenubutton",
            background=[("active", accent)],
            foreground=[("active", "white")]
        )

        self.style.configure(
            "TSpinbox",
            fieldbackground=widget_bg,
            background=widget_bg,
            foreground=fg,
            arrowcolor=fg,
        )

        if self.menu_btn:
            self.menu_btn.configure(style="MenuButton.TMenubutton")

        if self.menu and self.menu_indices:
            for col, idx in self.menu_indices.items():
                try:
                    self.menu.entryconfig(
                        idx,
                        background=widget_bg,
                        foreground=fg,
                        activebackground=accent,
                        activeforeground="white",
                    )
                except Exception:
                    pass

        if hasattr(self, 'tree_toggles') and self.tree_toggles:
            self.tree_toggles.apply_theme(widget_bg, fg, accent)

def style_combobox_popup(self, combobox, widget_bg, fg, accent):
    def fix_colors():
        try:
            # configure the popdown list
            combobox.tk.call("ttk::combobox::PopdownWindow", combobox, "f.l").configure(
                background=widget_bg,
                foreground=fg
            )
        except Exception:
            pass

    combobox.configure(postcommand=fix_colors)

class ThemedMessageBox:
    def __init__(self, root, theme_manager):
        self.root = root
        self.theme_manager = theme_manager

    def _show(self, title, message, icon=None, buttons=("OK",)):
        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.resizable(False, False)

        # Use theme colors
        if self.theme_manager.is_dark_mode:
            bg = "#36393f"
            fg = "#dcddde"
            accent = "#5865f2"
        else:
            bg = "#f4f6f8"
            fg = "black"
            accent = "#0078d7"

        popup.configure(bg=bg)

        # Message
        lbl = ttk.Label(popup, text=message, style="TLabel", wraplength=300, justify="center")
        lbl.pack(padx=20, pady=20)

        # Buttons
        result = {}

        def click(val):
            result['value'] = val
            popup.destroy()

        btn_frame = ttk.Frame(popup, style="TFrame")
        btn_frame.pack(pady=(0, 20))
        for b in buttons:
            ttk.Button(btn_frame, text=b, command=lambda v=b: click(v)).pack(side="left", padx=5)

        # Center popup
        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (w // 2)
        y = (popup.winfo_screenheight() // 2) - (h // 2)
        popup.geometry(f"{w}x{h}+{x}+{y}")

        popup.transient(self.root)
        popup.grab_set()
        self.root.wait_window(popup)

        return result.get('value', None)

    def showinfo(self, title, message):
        return self._show(title, message, icon="info")

    def showwarning(self, title, message):
        return self._show(title, message, icon="warning")

    def showerror(self, title, message):
        return self._show(title, message, icon="error")

    def askyesno(self, title, message):
        result = self._show(title, message, buttons=("Yes", "No"))
        return result == "Yes"
