import tkinter as tk
from tkinter import ttk

class Themes:
    def __init__(self, root, style, console_output, menu, menu_indices, menu_btn=None):
        self.root = root
        self.style = style
        self.console_output = console_output
        self.menu = menu
        self.menu_indices = menu_indices
        self.menu_btn = menu_btn
        self.header_widgets = []  
        self.is_dark_mode = True
        self.comboboxes = [] 
        self.sliders = []
        self.spinboxes = []

    def set_header_widgets(self, header_widgets):
        self.header_widgets = header_widgets
    
    def register_combobox(self, combobox):
        self.comboboxes.append(combobox)
    
    def register_slider(self, slider: tk.Scale):
        self.sliders.append(slider)

    def register_spinbox(self, spinbox: tk.Spinbox):
        self.spinboxes.append(spinbox)

    def style_combobox_popup(self, combobox, widget_bg, fg, accent):
        def fix_colors():
            combobox.configure(background=widget_bg, foreground=fg)
            try:
                combobox.tk.call("ttk::combobox::PopdownWindow", combobox, "f.l").configure(background=widget_bg)
            except Exception:
                pass  # Some platforms may ignore
        combobox.configure(postcommand=fix_colors)

    def apply_theme(self, is_dark_mode=True):
        self.is_dark_mode = is_dark_mode


        # --- define colors ---
        if is_dark_mode:
            app_bg = "#2f3136"
            panel_bg = "#36393f"
            widget_bg = "#40444b"
            accent = "#5865f2"
            fg = "#dcddde"
        else:
            app_bg = "#f4f6f8"
            panel_bg = "#f4f6f8"
            widget_bg = "white"
            accent = "#0078d7"
            fg = "black"

        # --- App background ---
        self.root.configure(bg=app_bg)

        # --- Frames & Labels ---
        self.style.configure("TFrame", background=panel_bg)
        self.style.configure("TLabel", background=panel_bg, foreground=fg)
        self.style.configure("Header.TLabel", background=panel_bg, foreground=fg)
        self.style.configure("Popup.TFrame", background=panel_bg)
        self.style.configure("Popup.TLabel", background=panel_bg, foreground=fg)
        self.style.configure("Popup.TButton", background=widget_bg, foreground=fg)
        self.style.map("Popup.TButton",
                       background=[("active", accent)],
                       foreground=[("active", "white")])

        # --- Menu Button ---
        if self.menu_btn and hasattr(self.menu_btn, "configure"):
            self.menu_btn.configure(style="MenuButton.TMenubutton")
        self.style.configure("MenuButton.TMenubutton",
                             background=widget_bg,
                             foreground=fg)
        self.style.map("MenuButton.TMenubutton",
                       background=[("active", accent)],
                       foreground=[("active", "white")])

        # --- Buttons, Entry, Combobox, Console ---
        self.style.configure("TButton", background=widget_bg, foreground=fg, relief="flat", padding=4)
        self.style.map("TButton", background=[("active", accent)], foreground=[("active", "white")])
        self.style.configure("TEntry", fieldbackground=widget_bg, foreground=fg, borderwidth=0, insertcolor=fg)
        self.style.configure("TCombobox", fieldbackground=widget_bg, background=widget_bg, foreground=fg, arrowcolor=fg)
        self.style.map("TCombobox",
                       fieldbackground=[("readonly", widget_bg)],
                       foreground=[("readonly", fg)],
                       selectbackground=[("readonly", accent)],
                       selectforeground=[("readonly", "white")])
        if isinstance(self.console_output, tk.Text):
            self.console_output.config(
                bg=widget_bg,
                fg=fg,
                insertbackground=fg,
                highlightthickness=0 if self.is_dark_mode else 1,
                relief="flat" if self.is_dark_mode else "solid"
            )

        # ----- LabelFrame (Info panel) -----
        self.style.configure(
            "Info.TLabelframe",
            background=panel_bg,
            borderwidth=1,
            relief="groove"
        )
        self.style.configure(
            "Info.TLabelframe.Label",
            background=panel_bg,
            foreground=fg
        )

        # ----- Treeview -----
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

        # --- Scrollbar ---
        self.style.configure("Vertical.TScrollbar",
                             gripcount=0,
                             background=widget_bg,
                             darkcolor=widget_bg,
                             lightcolor=widget_bg,
                             troughcolor=panel_bg,
                             bordercolor=panel_bg,
                             arrowcolor=fg,
                             relief="flat")

        self.style.map("Vertical.TScrollbar",
                       background=[("active", accent)],
                       troughcolor=[("!disabled", panel_bg)],
                       arrowcolor=[("active", "white")])

        self.style.configure("Horizontal.TScrollbar",
                     gripcount=0,
                     background=widget_bg,
                     darkcolor=widget_bg,
                     lightcolor=widget_bg,
                     troughcolor=panel_bg,
                     bordercolor=panel_bg,
                     arrowcolor=fg,
                     relief="flat")
        self.style.map("Horizontal.TScrollbar",
                       background=[("active", accent)],
                       troughcolor=[("!disabled", panel_bg)],
                       arrowcolor=[("active", "white")])
        self.style.configure(
            "TSpinbox",
            fieldbackground=widget_bg,
            background=widget_bg,
            foreground=fg,
            arrowcolor=fg,
        )
        # --- Headers ---
        for lbl in self.header_widgets:
            lbl.configure(background=panel_bg, foreground=fg)
            lbl.bind("<Enter>", lambda e, w=lbl: w.configure(background=accent))
            lbl.bind("<Leave>", lambda e, w=lbl: w.configure(background=panel_bg))

        # --- Checkbutton ---
        self.style.configure(
            "TCheckbutton",
            background=panel_bg,
            foreground=fg,
            relief="flat",
            padding=4
        )
        self.style.map(
            "TCheckbutton",
            background=[("active", accent)],
            foreground=[("active", "white")]
        )

        # --- Menu checkbuttons ---
        if self.menu_indices:
            for col, index in self.menu_indices.items():
                self.menu.entryconfig(index,
                                      background=widget_bg,
                                      foreground=fg,
                                      activebackground=accent,
                                      activeforeground="white")

        # --- Combobox popups ---
        for cb in self.comboboxes:
            self.style_combobox_popup(cb, widget_bg, fg, accent)

        # --- Sliders ---
        for slider in self.sliders:
            slider.configure(
                background=panel_bg,
                troughcolor=widget_bg,
                fg=fg,
                highlightbackground=panel_bg,
                activebackground=accent,
                bd=0,
                relief="flat"
            )
            
        for sb in self.spinboxes:
            sb.configure(
                bg=widget_bg,
                fg=fg,
                relief="flat",
                highlightthickness=0,
                justify="center",
                insertbackground=fg
            )
        


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
        result = self._show(title, message, buttons=("Yes","No"))
        return result == "Yes"
