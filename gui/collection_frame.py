import threading
import customtkinter as ctk
from tkinter import ttk
from PIL import Image
from load_utils import get_datasets
from img_utils import get_icon
from customtkinter import CTkImage


class CollectionPopup:
    ICON_SIZE = 24  # icon width/height

    def __init__(self, parent=None, tracker=None, title="Collection"):
        self.parent = parent
        self.tracker = tracker
        self.title = title
        self.search_var = ctk.StringVar()
        self.all_items = []

        self.placeholder = CTkImage(
            light_image=Image.new("RGBA", (self.ICON_SIZE, self.ICON_SIZE), (150, 150, 150, 255)),
            dark_image=Image.new("RGBA", (self.ICON_SIZE, self.ICON_SIZE), (150, 150, 150, 255)),
            size=(self.ICON_SIZE, self.ICON_SIZE)
        )

        # Sort state
        self._sort_column = "#0"
        self._sort_ascending = True

    def show(self):
        popup = ctk.CTkToplevel(self.parent)
        popup.title(self.title)
        popup.minsize(600, 400)

        main_frame = ctk.CTkFrame(popup)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        search_entry = ctk.CTkEntry(main_frame, placeholder_text="Search...", textvariable=self.search_var)
        search_entry.pack(fill="x", pady=(0, 10))
        self.search_var.trace_add("write", lambda *args: self.filter_items())

        columns = ("Tier", "Owned")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="tree headings", height=20)

        self.tree.heading("#0", text="Name", command=lambda: self.sort_by("#0"))
        self.tree.column("#0", width=250, anchor="w")
        self.tree.heading("Tier", text="Tier", command=lambda: self.sort_by("Tier"))
        self.tree.column("Tier", width=80, anchor="center")
        self.tree.heading("Owned", text="Owned", command=lambda: self.sort_by("Owned"))
        self.tree.column("Owned", width=60, anchor="center")

        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Start loader thread
        threading.Thread(target=self._wait_and_load, daemon=True).start()

        # Center popup
        popup.update_idletasks()
        w, h = popup.winfo_width(), popup.winfo_height()
        x = (popup.winfo_screenwidth() // 2) - (w // 2)
        y = (popup.winfo_screenheight() // 2) - (h // 2)
        popup.geometry(f"{w}x{h}+{x}+{y}")

        popup.grab_set()
        popup.focus_force()
        popup.wait_window()

    def _wait_and_load(self):
        # Wait until collection_dataset exists
        while not getattr(self.tracker, "collection_dataset", None):
            import time
            time.sleep(0.1)
        self._load_items_thread()

    def load_items(self):
        self.all_items.clear()
        datasets = get_datasets(load_external=False)
        collection = self.tracker.collection_dataset or {}
        tiers = datasets.get("tiers", {})

        items_by_name = {}
        for league, items in collection.items():
            for name, data in items.items():
                type_name = datasets["terms"].get(name, "")
                img_url = tiers.get(name, {}).get("img", None)
                owned = "✔" if data.get("owned") else "✖"
                display_name = f"{name} (Replica)" if type_name.lower() == "replica" else name
                items_by_name[name] = {
                    "name": display_name,
                    "tier": tiers.get(name, {}).get("tier", ""),
                    "owned": owned,
                    "img_url": img_url,
                }

        self.all_items = list(items_by_name.values())

    def _load_items_thread(self):
        self.load_items()

        # Preload icons for all items
        for item in self.all_items:
            tk_img = get_icon(
                name=item["name"],
                url=item.get("img_url"),
                size=(self.ICON_SIZE, self.ICON_SIZE),
                placeholder=self.placeholder,
                parent=self.parent,
                return_pil=False,
            )
            item["_tk_img"] = tk_img or self.placeholder

        if self.parent:
            self.parent.after(0, self.refresh_tree)

    def refresh_tree(self, filtered=None):
        self.tree.delete(*self.tree.get_children())
        rows = filtered if filtered is not None else self.all_items

        for i, item in enumerate(rows):
            img = item.get("_tk_img") or self.placeholder

            bg_color = "#2f3136" if i % 2 == 0 else "#383c42"
            self.tree.insert(
                "", "end",
                text=item["name"],
                image=img,
                values=(item["tier"], item["owned"]),
                tags=(f"row{i}",)
            )
            self.tree.tag_configure(f"row{i}", background=bg_color, foreground="#dcddde")

    def filter_items(self):
        query = self.search_var.get().lower().strip()
        filtered = [
            item for item in self.all_items
            if query in item["name"].lower()
            or query in item["tier"].lower()
            or query in item["owned"].lower()
        ]
        self.refresh_tree(filtered)

    def sort_by(self, col):
        reverse = False
        if self._sort_column == col:
            reverse = not self._sort_ascending

        key_func = None
        if col == "#0":
            key_func = lambda x: x["name"].lower()
        elif col == "Tier":
            key_func = lambda x: x["tier"].lower()
        elif col == "Owned":
            key_func = lambda x: 0 if x["owned"] == "✔" else 1

        if key_func:
            self.all_items.sort(key=key_func, reverse=reverse)
            self._sort_column = col
            self._sort_ascending = not reverse
            self.refresh_tree()
