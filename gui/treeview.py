from tkinter import ttk

import customtkinter as ctk

from config import ROW_HEIGHT
from fonts import make_font
from gui.palette import tree_palette
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
            tree.heading(col["id"], text=col["label"], anchor="center")
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

        pal = tree_palette(self.theme_mode)
        self.bg = pal["bg"]
        self.alt_bg = pal["alt_bg"]
        self.fg = pal["fg"]
        self.hover_bg = pal["hover_bg"]

        style.configure(
            "Treeview",
            background=pal["bg"],
            fieldbackground=pal["bg"],
            foreground=pal["fg"],
            rowheight=ROW_HEIGHT,
            font=make_font(11),
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
        )
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        style.map(
            "Treeview",
            background=[("selected", pal["sel_bg"])],
            foreground=[("selected", pal["sel_fg"])],
        )

        style.configure(
            "Treeview.Heading",
            background=pal["heading_bg"],
            foreground=pal["heading_fg"],
            font=make_font(11, "bold"),
            borderwidth=0,
            relief="flat",
            padding=(6, 8),
        )
        # Without this the default theme flashes headings light grey on hover.
        style.map(
            "Treeview.Heading",
            background=[("pressed", pal["heading_hover_bg"]), ("active", pal["heading_hover_bg"])],
            foreground=[("active", pal["fg"])],
            relief=[("pressed", "flat"), ("active", "flat")],
        )

    def _add_scrollbars(self):
        v_scroll = ctk.CTkScrollbar(self.parent, command=self.tree.yview)
        h_scroll = ctk.CTkScrollbar(self.parent, command=self.tree.xview, orientation="horizontal")

        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

    def _setup_tags(self):
        self.tree.tag_configure("hover", background=self.hover_bg)
        self.tree.tag_configure("odd", background=self.bg, foreground=self.fg)
        self.tree.tag_configure("even", background=self.alt_bg, foreground=self.fg)

        self._hover_iid = None
        self.tree.bind("<Motion>", self._on_motion, add="+")
        self.tree.bind("<Leave>", lambda e: self._set_hover(None), add="+")
        self.tree.bind("<ButtonRelease-1>", lambda e: self._set_hover(None), add="+")

    def _on_motion(self, event):
        iid = self.tree.identify_row(event.y)
        if iid and iid in self.tree.selection():
            iid = None  # keep the selection colour visible
        self._set_hover(iid or None)

    def _set_hover(self, iid):
        if iid == self._hover_iid:
            return
        call, widget = self.tree.tk.call, self.tree._w
        if self._hover_iid and self.tree.exists(self._hover_iid):
            call(widget, "tag", "remove", "hover", self._hover_iid)
        self._hover_iid = iid
        if iid:
            call(widget, "tag", "add", "hover", iid)

    def insert_row(self, values: dict, iid=None, tags=None):
        row_count = len(self.tree.get_children())
        tag = "even" if row_count % 2 == 0 else "odd"

        vals = [values.get(col["id"], "") for col in self.columns_config]

        self.tree.insert("", "end", iid=iid, values=vals, tags=tags or (tag,))

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
