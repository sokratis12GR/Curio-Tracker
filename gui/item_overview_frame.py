from PIL import Image
from customtkinter import *
from customtkinter import CTkImage

from config import IMAGE_COL_WIDTH, ROW_HEIGHT
from ocr_utils import parse_item_name, is_rare
from renderer import render_item
from tree_utils import pad_image


class ItemOverviewFrame:
    def __init__(self, parent, row_index_start=0):

        self.parent = parent
        self.item = None

        self.frame = CTkFrame(
            parent,
            corner_radius=10,
            border_width=3,
            border_color="white"
        )
        self.frame.grid(row=row_index_start, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        self.frame.configure(width=300)
        self.frame.grid_propagate(True)

        parent.rowconfigure(row_index_start, weight=1)
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)


        self.title_label = CTkLabel(
            self.frame,
            text="Item Overview",
            font=("Roboto", 16, "bold"),
            anchor="center",
            justify="center"
        )
        self.title_label.grid(row=0, column=0, columnspan=2, sticky="n", pady=(5, 10))

        self.labels = {}
        self.label_pairs = {}
        self.row_index = 1

        self.image_label = CTkLabel(
            self.frame,
            text="",
            anchor="center",
            justify="center"
        )
        self.image_label.grid(row=self.row_index, column=0, columnspan=2, sticky="n", pady=(0, 10))
        self.labels["Image"] = self.image_label
        self.image_label.grid_remove()
        self.row_index += 1

        # ---- Data Fields ----
        self.fields = ["Name", "Type", "Chaos Value", "Tier", "Stack Size", "Owned?"]

        for field in self.fields:
            lbl_field = CTkLabel(self.frame, text=f"{field}:", anchor="w", width=120)

            if field == "Name":
                lbl_value = CTkLabel(
                    self.frame,
                    text="",
                    anchor="center",
                    justify="center",
                    wraplength=260
                )

                lbl_field.grid_remove()
                lbl_value.grid(row=self.row_index, column=0, columnspan=2, sticky="ew", padx=5, pady=4)
            else:
                lbl_field.grid(row=self.row_index, column=0, sticky="w", padx=10, pady=(0, 5))
                lbl_value = CTkLabel(
                    self.frame,
                    text="",
                    anchor="w",
                    justify="left",
                    wraplength=220
                )
                lbl_value.grid(row=self.row_index, column=1, sticky="w", padx=10, pady=(0, 5))

            self.label_pairs[field] = (lbl_field, lbl_value)
            self.labels[field] = lbl_value

            lbl_field.grid_remove()
            lbl_value.grid_remove()
            self.row_index += 1

        for r in range(self.row_index):
            self.frame.rowconfigure(r, weight=1)

    def update_item(self, item):

        self.item = item
        item_type = getattr(item, "type", None)
        self.image_label.grid_remove()
        for lbl_field, lbl_value in self.label_pairs.values():
            lbl_field.grid_remove()
            lbl_value.grid_remove()

        if item is None:
            return

        try:
            pil_img = render_item(item)
            image_height = ROW_HEIGHT
            pil_img = pil_img.resize((IMAGE_COL_WIDTH, ROW_HEIGHT), Image.LANCZOS)
            pil_img = pad_image(
                pil_img, top_pad=0,
                target_width=IMAGE_COL_WIDTH, target_height=ROW_HEIGHT
            )

            ctk_img = CTkImage(
                light_image=pil_img,
                dark_image=pil_img,
                size=(IMAGE_COL_WIDTH, image_height)
            )
            self.image_label.configure(image=ctk_img, text="")
            self.image_label.image = ctk_img
            self.image_label.grid(sticky="n")
        except Exception as e:
            print(f"[ItemOverview] No image: {e}")

        owned = getattr(item, "owned", False)

        data = {
            "Name": parse_item_name(item),
            "Type": item_type,
            "Chaos Value": getattr(item, "chaos_value", None),
            "Tier": getattr(item, "tier", None),
            "Stack Size": getattr(item, "stack_size", None),
            "Owned?": owned,
        }

        if owned:
            self.frame._border_color="green"

        for field, value in data.items():
            if value not in (None, "", "N/A", 0):
                field_lbl, value_lbl = self.label_pairs[field]
                value_lbl.configure(text=str(value))
                field_lbl.grid()
                value_lbl.grid()
