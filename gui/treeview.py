from tkinter import ttk

import customtkinter as ctk

from config import ROW_HEIGHT
from fonts import make_font
from settings import get_setting


class CustomTreeview:
    def __init__(self, parent, theme_mode: str, columns_config: list):
        self.parent = parent
        self.theme_mode = theme_mode.upper()
        self.columns_config = columns_config

        self.tree = self._create_tree()
        self._apply_theme()
        self._add_scrollbars()
        self._setup_tags()

    # ------------------------------------------------------------------
    # Tree setup
    # ------------------------------------------------------------------
    def _create_tree(self):
        columns = tuple(col["id"] for col in self.columns_config)
        tree = ttk.Treeview(self.parent, columns=columns, show="headings")

        # Configure headings and column widths
        for col in self.columns_config:
            tree.heading(col["id"], text=col["label"])
            tree.column(col["id"], width=col["width"], anchor="center", stretch=True)

        display_cols = [
            col["id"]
            for col in self.columns_config
            if col["id"] != "numeric_value"
               and not (col["id"] == "owned" and not get_setting("Application", "enable_poeladder", False))
        ]
        tree["displaycolumns"] = tuple(display_cols)

        tree.grid(row=0, column=0, sticky="nsew")
        self.parent.grid_rowconfigure(0, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

        return tree

    # ------------------------------------------------------------------
    # Theming and style
    # ------------------------------------------------------------------
    def _apply_theme(self):
        style = ttk.Style()
        style.theme_use("default")

        if self.theme_mode == "DARK":
            bg = "#40444b"
            alt_bg = "#36393f"
            fg = "#dcddde"
            sel_bg = "#5865f2"
            sel_fg = "#ffffff"
            border_color = "#36393f"
            heading_bg = "#40444b"
        else:
            bg = "white"
            alt_bg = "#e8eaed"
            fg = "#000000"
            sel_bg = "#0078d7"
            sel_fg = "#ffffff"
            border_color = "#e0e0e0"
            heading_bg = "white"

        self.bg = bg
        self.alt_bg = alt_bg
        self.fg = fg

        style.configure(
            "Treeview",
            background=bg,
            fieldbackground=bg,
            foreground=fg,
            rowheight=ROW_HEIGHT,
            font=make_font(11),
            borderwidth=1,
            relief="solid",
            highlightthickness=1 if self.theme_mode == "LIGHT" else 0,
            highlightbackground=border_color,
            highlightcolor=border_color,
        )

        style.map(
            "Treeview",
            background=[("selected", sel_bg)],
            foreground=[("selected", sel_fg)],
        )

        style.configure(
            "Treeview.Heading",
            background=heading_bg,
            foreground=fg,
            font=make_font(11, "bold"),
            borderwidth=1,
            relief="solid",
        )


    def _add_scrollbars(self):
        v_scroll = ctk.CTkScrollbar(self.parent, command=self.tree.yview)
        h_scroll = ctk.CTkScrollbar(self.parent, command=self.tree.xview, orientation="horizontal")

        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

    def _setup_tags(self):
        self.tree.tag_configure("odd", background=self.bg, foreground=self.fg)
        self.tree.tag_configure("even", background=self.alt_bg, foreground=self.fg)

    def insert_row(self, values: dict, iid=None, tags=None):
        row_count = len(self.tree.get_children())
        tag = "even" if row_count % 2 == 0 else "odd"

        vals = [values.get(col["id"], "") for col in self.columns_config]

        self.tree.insert("", "end", iid=iid, values=vals, tags=tags or (tag,))

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
