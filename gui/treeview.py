import tkinter as tk
from tkinter import ttk
from config import IMAGE_COL_WIDTH

tree_columns = [
    {"id": "item", "label": "Item / Enchant", "width": 400, "sort_reverse": False, "visible": True},
    {"id": "value", "label": "Estimated Value", "width": 120, "sort_reverse": False, "visible": True},
    {"id": "numeric_value", "label": "Numeric Value", "width": 100, "sort_reverse": False, "visible": False},
    {"id": "type", "label": "Type", "width": 120, "sort_reverse": True, "visible": True},
    {"id": "stack_size", "label": "Stack Size", "width": 100, "sort_reverse": False, "visible": True},
    {"id": "tier", "label": "Tier", "width": 100, "sort_reverse": False, "visible": True},
    {"id": "area_level", "label": "Area Level", "width": 100, "sort_reverse": False, "visible": True},
    {"id": "layout", "label": "BP Layout", "width": 120, "sort_reverse": False, "visible": True},
    {"id": "player", "label": "Found by", "width": 120, "sort_reverse": False, "visible": True},
    {"id": "league", "label": "League", "width": 100, "sort_reverse": False, "visible": True},
    {"id": "time", "label": "Time", "width": 150, "sort_reverse": True, "visible": True},
    {"id": "record", "label": "Record", "width": 100, "sort_reverse": True, "visible": True},
]

def setup_tree(tree_frame):
    columns = tuple(col["id"] for col in tree_columns)
    tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings")

    # Image column
    tree.heading("#0", text="Image")
    tree.column("#0", width=IMAGE_COL_WIDTH, anchor="center", stretch=False)

    # Configure columns
    for col in tree_columns:
        tree.heading(col["id"], text=col["label"])  # sorting can be bound later
        tree.column(col["id"], width=col["width"], anchor="center", stretch=True)

    display_cols = [col["id"] for col in tree_columns if col["id"] != "numeric_value"]
    tree["displaycolumns"] = tuple(display_cols)

    # Scrollbars
    v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

    tree.grid(row=0, column=0, sticky="nsew")
    v_scroll.grid(row=0, column=1, sticky="ns")
    h_scroll.grid(row=1, column=0, sticky="ew")

    # Row tags
    tree.tag_configure("odd", background="#2f3136", foreground="#dcddde")
    tree.tag_configure("even", background="#36393f", foreground="#dcddde")
    tree.tag_configure("light_odd", background="#f4f6f8", foreground="black")
    tree.tag_configure("light_even", background="#e8eaed", foreground="black")

    return tree