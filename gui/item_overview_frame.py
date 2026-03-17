import threading
import webbrowser
from PIL import Image, ImageTk
from customtkinter import *
from customtkinter import CTkImage
from io import BytesIO

import currency_utils
from config import IMAGE_COL_WIDTH, ROW_HEIGHT
from fonts import make_font
from ocr_utils import parse_item_name
from renderer import render_item
from tree_utils import pad_image
from img_utils import get_icon


class ItemOverviewFrame:
    def __init__(self, parent, row_index_start=0):
        self.parent = parent
        self.item = None

        self.frame = CTkFrame(
            parent,
            corner_radius=6,
            border_width=1,
            border_color=("#e0e0e0", "#40444b"),
            fg_color=("#f4f6f8", "#2f3136")
        )
        self.frame.grid(row=row_index_start, column=0, columnspan=2, sticky="new", padx=5, pady=5)
        self.frame.configure(width=300)
        self.frame.grid_propagate(True)

        parent.rowconfigure(row_index_start, weight=1)
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)

        # Title
        self.title_label = CTkLabel(
            self.frame,
            text="Item Overview",
            font=make_font(16, "bold"),
            anchor="center",
            justify="center"
        )
        self.title_label.grid(row=0, column=0, columnspan=2, sticky="n", pady=(5, 10))

        # Image/Icon
        self.labels = {}
        self.label_pairs = {}
        self.row_index = 1
        self.image_label = CTkLabel(self.frame, text="", anchor="center", justify="center")
        self.image_label.grid(row=self.row_index, column=0, columnspan=2, sticky="n", pady=(0, 10))
        self.labels["Image"] = self.image_label
        self.image_label.grid_remove()
        self.row_index += 1

        self.icon_label = CTkLabel(self.frame, text="", anchor="center", justify="center")
        self.icon_label.grid(row=self.row_index, column=0, columnspan=2, pady=(0, 10))
        self.labels["IconImage"] = self.icon_label
        self.icon_label.grid_remove()
        self.row_index += 1

        # Item Name
        self.item_name_label = CTkLabel(
            self.frame,
            text="",
            font=make_font(11, "bold"),
            anchor="center",
            justify="center",
            wraplength=260
        )
        self.item_name_label.grid(row=self.row_index, column=0, columnspan=2, pady=(0, 8))
        self.item_name_label.grid_remove()
        self.row_index += 1

        # Data Fields
        self.fields = ["Wiki", "Type", "Est. Value", "5-L Value", "6-L Value", "Tier", "Stack Size", "Owned", "Picked"]
        for field in self.fields:
            lbl_field = CTkLabel(self.frame, text=f"{field}:", anchor="w", width=120)
            lbl_field.grid(row=self.row_index, column=0, sticky="w", padx=10, pady=(0, 5))
            lbl_value = CTkLabel(self.frame, text="", anchor="w", justify="left", wraplength=220)
            lbl_value.grid(row=self.row_index, column=1, sticky="w", padx=10, pady=(0, 5))

            self.label_pairs[field] = (lbl_field, lbl_value)
            self.labels[field] = lbl_value
            lbl_field.grid_remove()
            lbl_value.grid_remove()
            self.row_index += 1

        text_rows_count = len(self.fields) + 2  # item name + optional Wiki row
        for r in range(self.row_index):
            if r < self.row_index - text_rows_count:
                self.frame.rowconfigure(r, weight=0)
            else:
                self.frame.rowconfigure(r, weight=1)

    def update_item(self, item):
        self.item = item
        self.image_label.grid_remove()
        self.icon_label.grid_remove()
        for lbl_field, lbl_value in self.label_pairs.values():
            lbl_field.grid_remove()
            lbl_value.grid_remove()

        if item is None:
            return

        # Render main item image
        try:
            pil_img = render_item(item)
            pil_img = pil_img.resize((IMAGE_COL_WIDTH, ROW_HEIGHT), Image.LANCZOS)
            pil_img = pad_image(pil_img, top_pad=0, target_width=IMAGE_COL_WIDTH, target_height=ROW_HEIGHT)
            ctk_img = CTkImage(light_image=pil_img, dark_image=pil_img, size=(IMAGE_COL_WIDTH, ROW_HEIGHT))
            self.image_label.configure(image=ctk_img, text="")
            self.image_label.image = ctk_img
            self.image_label.grid(sticky="n")
        except Exception as e:
            print(f"[ItemOverview] No image: {e}")

        # Update text fields
        owned = getattr(item, "owned", False)
        picked = getattr(item, "picked", False)
        wiki_url = getattr(item, "wiki", None)
        icon_url = getattr(item, "img", None)
        item_type = getattr(item, "type", None)

        display_value = currency_utils.calculate_estimate_value(item)
        five_link_value = currency_utils.calculate_five_link_estimate_value(item)
        six_link_value = currency_utils.calculate_six_link_estimate_value(item)

        data = {
            "Type": item_type,
            "Est. Value": display_value,
            "5-L Value": five_link_value,
            "6-L Value": six_link_value,
            "Tier": getattr(item, "tier", None),
            "Stack Size": getattr(item, "stack_size", None),
            "Owned": owned,
            "Picked": picked
        }

        name = parse_item_name(item) if item else ""
        if name:
            self.item_name_label.configure(text=name)
            self.item_name_label.grid(sticky="n")
        else:
            self.item_name_label.configure(text="")
            self.item_name_label.grid_remove()

        for field, value in data.items():
            if value not in (None, "", "N/A", 0):
                field_lbl, value_lbl = self.label_pairs[field]
                value_lbl.configure(text=str(value))
                field_lbl.grid()
                value_lbl.grid()

        # --- Load icon using global temp cache ---
        if icon_url:
            pil_icon = get_icon(
                name=name,
                url=icon_url,
                size=(ROW_HEIGHT, ROW_HEIGHT),
                placeholder=None,
                parent=self.parent,
                return_pil=True
            )
            if pil_icon:
                ctk_icon = CTkImage(light_image=pil_icon, dark_image=pil_icon, size=(ROW_HEIGHT, ROW_HEIGHT))
                self.icon_label.configure(image=ctk_icon, text="")
                self.icon_label.image = ctk_icon
                self.icon_label.grid(sticky="n", pady=(0, 10))

        # --- Wiki link ---
        if wiki_url:
            field_lbl, value_lbl = self.label_pairs["Wiki"]
            value_lbl.configure(font=make_font(12, underline=True), text="Open Wiki Page", cursor="hand2")
            value_lbl.unbind("<Button-1>")
            value_lbl.bind("<Button-1>", lambda e, url=wiki_url: webbrowser.open(url))
            field_lbl.grid()
            value_lbl.grid()
