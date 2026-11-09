from customtkinter import *

import currency_utils
import ocr_utils as utils
from config import DEBUGGING, BP_ENCHANTMENT_OPTIONS, layout_keywords


class TreeEditingMixin:
    # @pyinstrument.profile()
    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id or col_id == "#0":
            return

        displayed_columns = self.tree["displaycolumns"]
        col_index = int(col_id.replace("#", "")) - 1
        if col_index >= len(displayed_columns):
            return

        col_name = displayed_columns[col_index]
        if col_name.lower() != "picked":
            return

        new_text = "☐"
        new_state = False

        current_value = str(self.tree.set(row_id, col_name)).strip().lower()
        if current_value in ("TRUE", "true", "yes", "☑"):
            new_state = False
            new_text = "☐"
        elif current_value in ("FALSE", "false", "no", "☐"):
            new_state = True
            new_text = "☑"

        # Update the tree display
        self.tree.set(row_id, col_name, new_text)

        item = self.csv_row_map.get(row_id)
        if not item:
            return

        item_text = utils.parse_item_name(item)

        setattr(item, col_name, new_state)
        self.modify_record(row_id, item_text, updates={"Picked": new_state})
        self.update_total_labels()

    # @pyinstrument.profile()
    def on_tree_double_click(self, event):
        # Identify row and column
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id or col_id == "#0":
            return

        col_idx_displayed = int(col_id.replace("#", "")) - 1
        displayed_columns = self.tree["displaycolumns"]
        if col_idx_displayed >= len(displayed_columns):
            return

        # Map to actual column name
        col_name = displayed_columns[col_idx_displayed]
        if DEBUGGING:
            print(f"row_id: {row_id}, col_id: {col_id}, col_name: {col_name}")

        if col_name.lower() == "item":
            picked_col = None
            for c in displayed_columns:
                if c.lower() == "picked":
                    picked_col = c
                    break
            if not picked_col:
                return  # No "Picked" column found

            current_value = str(self.tree.set(row_id, picked_col)).strip().lower()
            if current_value in ("true", "yes", "☑"):
                new_state = False
                new_text = "☐"
            else:
                new_state = True
                new_text = "☑"

            # Update tree visually
            self.tree.set(row_id, picked_col, new_text)

            item = self.csv_row_map.get(row_id)
            if not item:
                return

            item_text = utils.parse_item_name(item)
            setattr(item, picked_col, new_state)

            # Update CSV record and totals
            self.modify_record(row_id, item_text, updates={"Picked": new_state})
            self.update_total_labels()
            return

        bbox = self.tree.bbox(row_id, col_name)
        if not bbox:
            return
        x, y, w, h = bbox

        item = self.csv_row_map.get(row_id)
        if not item:
            return

        item_type = getattr(item, "type", None)
        item_text = utils.parse_item_name(item)

        old_value = self.tree.set(row_id, col_name)


        # ---- STACK SIZE (only Currency/Scarab) ----
        if col_name == "stack_size" and item_type in {"Currency", "Scarab"}:
            edit_entry = CTkEntry(self.tree, justify="center", width=w, height=h)
            edit_entry.place(x=x, y=y)
            if old_value:
                edit_entry.insert(0, old_value)
            edit_entry.focus()

            def save_stack(event=None):
                new_value = edit_entry.get().strip()
                edit_entry.destroy()

                # Validate and update
                stack_val = currency_utils.convert_to_int(new_value) if new_value != "" else ""
                if stack_val != "" and not (1 <= stack_val <= 40):
                    self.msgbox.showerror("Invalid Stack Size", "Enter a number between 1–40 or leave blank.")
                    return

                self.tree.set(row_id, col_name, stack_val)
                if item:
                    item.stack_size = stack_val if stack_val != "" else None

                    # Reuse utils.calculate_estimate_value
                    display_value = currency_utils.calculate_estimate_value(item)
                    numeric_value = currency_utils.convert_to_float(getattr(item, "chaos_value", 0)) * (item.stack_size or 1)

                    self.tree.set(row_id, "value", display_value)
                    self.tree.set(row_id, "numeric_value", numeric_value)

                self.modify_record(row_id, item_text, updates={"Stack Size": new_value})

            edit_entry.bind("<Return>", save_stack)
            edit_entry.bind("<FocusOut>", save_stack)

        # ---- BLUEPRINT TYPE EDIT ----
        elif col_name == "layout":
            combo = CTkComboBox(self.tree, values=layout_keywords, state="readonly", width=w, height=h)
            combo.place(x=x, y=y)
            combo.set(old_value or layout_keywords[0])
            combo.focus()

            def save_blueprint(event=None):
                new_value = combo.get()
                combo.destroy()

                self.tree.set(row_id, col_name, new_value)
                if item:
                    setattr(item, "blueprint_type", new_value)

                self.modify_record(row_id, item_text, updates={"Blueprint Type": new_value})

            combo.bind("<<ComboboxSelected>>", save_blueprint)
            combo.bind("<FocusOut>", save_blueprint)

        elif col_name == "bp_enchantment":
            combo = CTkComboBox(
                self.tree,
                values=BP_ENCHANTMENT_OPTIONS,
                state="readonly",
                width=w,
                height=h
            )
            combo.place(x=x, y=y)
            combo.set(old_value or BP_ENCHANTMENT_OPTIONS[0])
            combo.focus()

            def save_bp_enchantment(event=None):
                new_value = combo.get()
                combo.destroy()

                self.tree.set(row_id, col_name, new_value)

                if item:
                    setattr(item, "bp_enchantment", new_value)

                self.modify_record(
                    row_id,
                    item_text,
                    updates={"BP Enchantment": new_value}
                )

            combo.bind("<<ComboboxSelected>>", save_bp_enchantment)
            combo.bind("<FocusOut>", save_bp_enchantment)
