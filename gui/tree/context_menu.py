from tkinter import Menu

from customtkinter import *

import ocr_utils as utils
from config import BP_ENCHANTMENT_OPTIONS, layout_keywords


class TreeContextMenuMixin:
    def show_context_menu(self, event):
        row_id = self.tree.identify_row(event.y)

        if row_id and row_id not in self.tree.selection():
            self.tree.selection_set(row_id)

        if not self.tree.selection():
            return

        menu = Menu(self.tree, tearoff=0)

        menu.add_command(
            label=f"Mass Change ({len(self.tree.selection())} rows)",
            command=self.mass_change
        )

        menu.post(event.x_root, event.y_root)

    def mass_change(self):
        mass_column_map = {
            "Blueprint Type": {
                "tree": "layout",
                "attr": "blueprint_type",
            },
            "BP Enchantment": {
                "tree": "bp_enchantment",
                "attr": "bp_enchantment",
            },
            "League": {
                "tree": "league",
                "attr": "league",
            },
            "Logged By": {
                "tree": "player",
                "attr": "logged_by",
            },
            "Picked": {
                "tree": "picked",
                "attr": "picked",
            },
            "Owned": {
                "tree": "owned",
                "attr": "owned",
            },
            "Area Level": {
                "tree": "area_level",
                "attr": "area_level",
            },
        }

        selected = self.tree.selection()

        if not selected:
            return

        popup = CTkToplevel(self.root)
        popup.title("Mass Change")
        popup.geometry("500x500")

        CTkLabel(
            popup,
            text=f"Selected rows: {len(selected)}",
            font=("Arial", 16)
        ).pack(pady=10)

        # Actual CSV column names
        columns = [
            "Blueprint Type",
            "BP Enchantment",
            "League",
            "Logged By",
            "Picked",
            "Owned",
            "Area Level"
        ]

        column_var = StringVar(value=columns[0])

        column_box = CTkComboBox(
            popup,
            values=columns,
            variable=column_var,
            state="readonly"
        )
        column_box.pack(pady=5)

        # Preview selected rows
        CTkLabel(
            popup,
            text="Rows being changed:"
        ).pack(pady=(15, 5))

        preview = CTkTextbox(
            popup,
            width=450,
            height=150
        )
        preview.pack()

        for row_id in selected:
            item = self.csv_row_map.get(row_id)

            if item:
                record_number = getattr(item, "record_number", None)
                logged_by = getattr(item, "logged_by", "")

                preview.insert(
                    "end",
                    f"#{record_number} - {utils.parse_item_name(item)} - Logged by {logged_by}\n"
                )

        preview.configure(state="disabled")

        CTkLabel(
            popup,
            text="New value:"
        ).pack(pady=(10, 5))

        current_selector = None

        def update_value_options(*args):

            nonlocal current_selector

            if current_selector:
                current_selector.destroy()

            column = column_var.get()

            if column == "Blueprint Type":
                current_selector = CTkComboBox(
                    popup,
                    values=layout_keywords,
                    state="readonly"
                )

            elif column == "BP Enchantment":
                current_selector = CTkComboBox(
                    popup,
                    values=BP_ENCHANTMENT_OPTIONS,
                    state="readonly",
                    width=300
                )

            elif column in ("Picked", "Owned"):
                current_selector = CTkComboBox(
                    popup,
                    values=["True", "False"],
                    state="readonly"
                )

            else:
                current_selector = CTkEntry(
                    popup
                )

            current_selector.pack(pady=10)

        column_var.trace_add(
            "write",
            update_value_options
        )
        update_value_options()

        def apply_change():

            column = column_var.get()

            if not current_selector:
                return

            new_value = current_selector.get().strip()

            if not new_value:
                return

            confirm = self.msgbox.askyesno(
                "Confirm Mass Change",
                f"Change {len(selected)} rows?\n\n"
                f"{column} → {new_value}"
            )

            if not confirm:
                return

            for row_id in selected:

                item = self.csv_row_map.get(row_id)

                if not item:
                    continue

                item_name = utils.parse_item_name(item)

                mapping = mass_column_map[column]

                tree_column = mapping["tree"]
                attribute = mapping["attr"]

                raw_value = current_selector.get().strip()

                if column in ("Picked", "Owned"):
                    new_value = raw_value == "True"
                else:
                    new_value = raw_value

                # Update tree
                self.tree.set(
                    row_id,
                    tree_column,
                    "☑" if new_value is True else "☐" if new_value is False else new_value
                )

                # Update object
                setattr(
                    item,
                    attribute,
                    new_value
                )

                # Update CSV
                self.modify_record(
                    row_id,
                    item_name,
                    updates={
                        column: new_value
                    }
                )

            popup.destroy()

        CTkButton(
            popup,
            text="Apply Changes",
            command=apply_change
        ).pack(pady=15)
