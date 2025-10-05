import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, messagebox

from PIL import Image, ImageTk
from pytz import InvalidTimeError

import ocr_utils as utils
from config import IMAGE_COL_WIDTH, ROW_HEIGHT, layout_keywords
from csv_manager import CSVManager
from gui.custom_hours_popup import CustomHoursPopup
from gui.treeview import tree_columns
from renderer import render_item
from tree_utils import get_item_name_str, generate_item_id, pad_image


class TreeManager:
    def __init__(self, tree, is_dark_mode):
        self.tree = tree
        self.csv_manager = CSVManager()
        self.tree_columns = tree_columns
        self.columns = [col["id"] for col in tree_columns]
        self.display_columns = [
            col["id"]
            for col in tree_columns
            if col.get("visible", True) and col["id"] != "numeric_value"
        ]
        self.tree["displaycolumns"] = tuple(self.display_columns)
        self.image_col_width = IMAGE_COL_WIDTH
        self.row_height = ROW_HEIGHT
        self.is_dark_mode = is_dark_mode
        # Image caches
        self.original_img_cache = {}
        self.image_cache = {}
        self._custom_popup_open = False
        self.time_filter_var = tk.StringVar(value="All")
        self.custom_hours_var = tk.DoubleVar(value=1)
        self.time_filter_var.trace_add("write", self.filter_tree_by_time)
        self.search_var = tk.StringVar(value="")
        self.search_var.trace_add("write", lambda *args: self.apply_filters())

        # Data trackers
        self.global_item_tracker = []
        self.sorted_item_keys = []
        self.item_time_map = {}
        self.all_item_iids = set()
        self.csv_row_map = {}
        self._last_visible_iids = set()
        self.sort_reverse = {col["id"]: col.get("sort_reverse", False) for col in tree_columns}
        self.images_visible = True

        # Row tags
        self.tree.tag_configure("odd", background="#2f3136", foreground="#dcddde")
        self.tree.tag_configure("even", background="#36393f", foreground="#dcddde")
        self.tree.tag_configure("light_odd", background="#f4f6f8", foreground="black")
        self.tree.tag_configure("light_even", background="#e8eaed", foreground="black")

        # Bind events
        self.tree.bind("<Configure>", lambda e: self.update_visible_images())
        self.tree.bind("<Motion>", lambda e: self.update_visible_images())
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Delete>", self.delete_selected_items)

        self.toggle_frame = None
        self.col_vars = {}  # track visibility of each column
        self.toggle_img_btn = None

    def add_item_to_tree(self, item, render_image=False, insert_at_top=True):

        item_name_str = get_item_name_str(item)
        record_number = getattr(item, "record_number", None)
        if record_number:
            item_key = f"rec_{record_number}"
        else:
            item_key = generate_item_id(item)

        # Avoid duplicate insert for same record
        if record_number and self.tree.exists(f"rec_{record_number}"):
            return

        # ---- Render image ----
        if item_key not in self.original_img_cache:
            img = render_item(item)
            img = img.resize((IMAGE_COL_WIDTH - 4, ROW_HEIGHT), Image.LANCZOS)
            img = pad_image(img, left_pad=-20, top_pad=0,
                            target_width=IMAGE_COL_WIDTH, target_height=ROW_HEIGHT)
            self.original_img_cache[item_key] = img.copy()

        # ---- Item text ----
        item_text = utils.parse_item_name(item)

        # ---- Parse timestamp ----
        item_time_obj = getattr(item, "time", None)
        if isinstance(item_time_obj, str):
            try:
                # Expect format like "YYYY-MM-DD_HH-MM-SS"
                item_time_obj = datetime.strptime(item_time_obj, "%Y-%m-%d_%H-%M-%S")
            except (ValueError, InvalidTimeError):
                item_time_obj = None
        elif not isinstance(item_time_obj, datetime):
            item_time_obj = None

        self.item_time_map[item_key] = item_time_obj
        display_time = item_time_obj.strftime("%d %b %Y - %H:%M") if item_time_obj else "Unknown"

        chaos_value = getattr(item, "chaos_value", "")
        item_type = getattr(item, "type", "N/A")

        display_value = utils.calculate_estimate_value(item)
        numeric_value = utils.convert_to_float(chaos_value)

        _, stack_size_txt = utils.get_stack_size(item)

        item_tier = getattr(item, "tier", "")
        area_level = getattr(item, "area_level", "83")
        blueprint_type = getattr(item, "blueprint_type", "Prohibited Library")
        logged_by = getattr(item, "logged_by", "")
        league = getattr(item, "league", "3.26")

        # ---- Insert into Treeview ----
        iid = item_key
        self.csv_row_map[iid] = item
        values_map = {
            "item": item_text,
            "value": display_value,
            "numeric_value": numeric_value,
            "type": item_type,
            "stack_size": stack_size_txt,
            "tier": item_tier,
            "area_level": area_level,
            "layout": blueprint_type,
            "player": logged_by,
            "league": league,
            "time": display_time,
            "record": record_number,
        }

        # Build values tuple in order of self.columns
        values = tuple(values_map.get(col, "") for col in self.columns)

        # Insert into Treeview
        if insert_at_top:
            self.tree.insert("", 0, iid=iid, image="", values=values)
        else:
            self.tree.insert("", "end", iid=iid, image="", values=values)

        self.all_item_iids.add(iid)

        # ---- Track globally ----
        self.global_item_tracker.append({
            "iid": iid,
            "csv_index": len(self.global_item_tracker),
            "name": item_name_str,
            "item_obj": item
        })

        if render_image:
            self.update_visible_images()

    def clear_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.all_item_iids.clear()
        self.csv_row_map.clear()
        self.original_img_cache.clear()
        self.image_cache.clear()
        self.sorted_item_keys.clear()
        self.item_time_map.clear()
        self._last_visible_iids.clear()
        self.global_item_tracker.clear()

    def delete_selected_items(self, item_name, event=None):
        selected = self.tree.selection()
        if not selected:
            return

        if len(selected) == 1:
            msg = "Are you sure you want to delete this record?"
        else:
            msg = f"Are you sure you want to delete these {len(selected)} records?"

        confirm = messagebox.askyesno("Confirm Deletion", msg)
        if not confirm:
            return

        for iid in selected:
            row_values = self.tree.item(iid)['values']

            item_index = self.columns.index("item")
            item_value = row_values[item_index]
            self.modify_csv_record(iid, item_value, delete=True)
            self.tree.delete(iid)
            self.all_item_iids.discard(iid)
            self.original_img_cache.pop(iid, None)
            self.image_cache.pop(iid, None)
            self.item_time_map.pop(iid, None)
            self.csv_row_map.pop(iid, None)

    def _add_items_in_batches(self, items, batch_size=200, start_index=0, render_images=False, post_callback=None):
        end_index = min(start_index + batch_size, len(items))
        batch = items[start_index:end_index]

        for item in batch:
            self.add_item_to_tree(item, render_image=render_images, insert_at_top=False)

        if end_index < len(items):
            self.tree.after(
                15,
                self._add_items_in_batches,
                items,
                batch_size,
                end_index,
                render_images,
                post_callback
            )
        else:
            self.update_visible_images()
            self.filter_tree_by_time()
            if post_callback:
                post_callback()

    def load_all_items_threaded(self, tracker, post_callback=None):
        self.clear_tree()

        def worker():
            all_items = tracker.load_all_parsed_items_from_csv()
            all_items.sort(key=lambda item: getattr(item, "time", datetime.min), reverse=True)

            self.tree.after(
                50,
                self._add_items_in_batches,
                all_items,
                200,
                0,
                False,
                post_callback
            )

        threading.Thread(target=worker, daemon=True).start()

    def load_latest_items(self, tracker):
        self.clear_tree()
        parsed = tracker.load_recent_parsed_items_from_csv()
        print(f"[DEBUG] Loaded {len(parsed)} items")  # <--- check this
        if not parsed:
            return

        for item in parsed:
            self.add_item_to_tree(item, render_image=True)

        self.filter_tree_by_time()
        self.update_visible_images()

    def load_latest_item(self, tracker):
        self.clear_tree()
        parsed = tracker.load_recent_parsed_items_from_csv(max_items=1)
        if not parsed:
            return

        item = parsed[0]
        self.add_item_to_tree(item, render_image=True)

        self.filter_tree_by_time()
        self.update_visible_images()

    def on_tree_double_click(self, event):
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if not row_id or not col_id or col_id == "#0":
            return

        # Get column index in displayed columns
        col_idx = int(col_id.replace("#", "")) - 1  # #1 is first displayed column
        displayed_columns = self.tree["displaycolumns"]
        if col_idx >= len(displayed_columns):
            return
        col_name = displayed_columns[col_idx]

        bbox = self.tree.bbox(row_id, col_name)
        if not bbox:
            return
        x, y, w, h = bbox

        item = self.csv_row_map.get(row_id)
        if not item:
            return

        item_type = getattr(item, "type", None)
        if getattr(item, "enchants", None) and len(item.enchants) > 0:
            item_text = "\n".join([str(e) for e in item.enchants])
        else:
            item_text = getattr(item, "itemName", "Unknown")
            if hasattr(item_text, "lines"):
                item_text = "\n".join([str(line) for line in item_text.lines])

        old_value = self.tree.set(row_id, col_name)

        # ---- STACK SIZE (only Currency/Scarab) ----
        if col_name == "stack_size" and item_type in {"Currency", "Scarab"}:
            edit_entry = ttk.Entry(self.tree, justify="center")
            edit_entry.place(x=x, y=y, width=w, height=h)
            if old_value:
                edit_entry.insert(0, old_value)
            edit_entry.focus()

            def save_stack(event=None):
                new_value = edit_entry.get().strip()
                edit_entry.destroy()

                # Validate and update
                stack_val = utils.convert_to_int(new_value) if new_value != "" else ""
                if stack_val != "" and not (1 <= stack_val <= 40):
                    messagebox.showerror("Invalid Stack Size", "Enter a number between 1–40 or leave blank.")
                    return

                self.tree.set(row_id, col_name, stack_val)
                if item:
                    item.stack_size = stack_val if stack_val != "" else None

                    # Reuse utils.calculate_estimate_value
                    display_value = utils.calculate_estimate_value(item)
                    numeric_value = utils.convert_to_float(getattr(item, "chaos_value", 0)) * (item.stack_size or 1)

                    self.tree.set(row_id, "value", display_value)
                    self.tree.set(row_id, "numeric_value", numeric_value)

                self.modify_csv_record(row_id, item_text, updates={"Stack Size": new_value})

            edit_entry.bind("<Return>", save_stack)
            edit_entry.bind("<FocusOut>", save_stack)

        # ---- BLUEPRINT TYPE EDIT ----
        elif col_name == "layout":
            combo = ttk.Combobox(self.tree, values=layout_keywords, state="readonly")
            combo.place(x=x, y=y, width=w, height=h)
            combo.set(old_value or layout_keywords[0])
            combo.focus()

            def save_blueprint(event=None):
                new_value = combo.get()
                combo.destroy()

                self.tree.set(row_id, col_name, new_value)
                if item:
                    setattr(item, "blueprint_type", new_value)

                self.modify_csv_record(row_id, item_text, updates={"Blueprint Type": new_value})

            combo.bind("<<ComboboxSelected>>", save_blueprint)
            combo.bind("<FocusOut>", save_blueprint)

    def modify_csv_record(self, row_id, item_name, updates=None, delete=False):
        item = self.csv_row_map.get(row_id)
        if not item:
            return

        record_number = getattr(item, "record_number", None)
        if not record_number:
            print("[WARN] Item has no Record #, cannot modify CSV")
            return

        self.csv_manager.modify_record(record_number, item_name, updates=updates, delete=delete)

    # ---------- Sorting ----------
    def sort_tree(self, column):
        children = self.tree.get_children()
        reverse = self.sort_reverse.get(column, False)

        def sort_key(iid):
            val = self.tree.set(iid, column)
            if val in ("", None):
                # Place empty/None values at the end
                return float('inf') if not reverse else float('-inf')

            if column == "value":
                return float(self.tree.set(iid, "numeric_value") or 0.0)
            elif column == "time":
                dt = self.item_time_map.get(iid)
                if dt is None:
                    return float('inf') if not reverse else float('-inf')
                return dt
            elif column == "record":
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return float('inf') if not reverse else float('-inf')
            elif column == "tier":
                import re
                s = str(val).strip() if val else ""
                if s == "":
                    numeric = 999
                else:
                    try:
                        numeric = int(s)
                    except ValueError:
                        m = re.search(r"\d+", s)
                        numeric = int(m.group()) if m else 999
                return numeric
            else:
                return str(val).lower()

        # Sort all iids by the key
        sorted_iids = sorted(children, key=sort_key, reverse=reverse)

        # Reinsert in sorted order
        for index, iid in enumerate(sorted_iids):
            self.tree.move(iid, "", index)
            tag = "odd" if index % 2 == 0 else "even"
            if not self.is_dark_mode:
                tag = "light_odd" if index % 2 == 0 else "light_even"
            self.tree.item(iid, tags=(tag,))

        # Toggle sort direction for next click
        self.sort_reverse[column] = not reverse

    # ---------- Filtering ----------
    def apply_filters(self, search_query=None, *args):
        if search_query is None:
            search_query = self.search_var.get()
        search_query = search_query.lower().strip()

        selected_time = self.time_filter_var.get()
        now = datetime.now()

        # Collect iids that should be visible
        visible_iids = []

        for iid in self.all_item_iids:
            if not self.tree.exists(iid) or self.tree.parent(iid) != "":
                continue

            # Search match
            values = self.tree.item(iid, "values")
            text = " ".join(str(v).lower() for v in values)
            matches_search = search_query in text if search_query else True

            # Time match
            dt = self.item_time_map.get(iid)
            matches_time = False
            if dt is None:
                matches_time = False
            else:
                delta = now - dt
                if selected_time == "All":
                    matches_time = True
                elif selected_time == "Today":
                    matches_time = dt.date() == now.date()
                elif selected_time == "Last hour":
                    matches_time = delta <= timedelta(hours=1)
                elif selected_time == "Last 2 hours":
                    matches_time = delta <= timedelta(hours=2)
                elif selected_time == "Last 12 hours":
                    matches_time = delta <= timedelta(hours=12)
                elif selected_time == "Last 24 hours":
                    matches_time = delta <= timedelta(days=1)
                elif selected_time == "Last week":
                    matches_time = delta <= timedelta(weeks=1)
                elif selected_time == "Last 2 weeks":
                    matches_time = delta <= timedelta(weeks=2)
                elif selected_time == "Last month":
                    matches_time = delta <= timedelta(days=30)
                elif selected_time == "Last year":
                    matches_time = delta <= timedelta(days=365)
                elif selected_time == "Custom...":
                    if not getattr(self, "_custom_popup_open", False):
                        self.open_custom_hours_popup()
                    return

            if matches_search and matches_time:
                visible_iids.append((dt or datetime.min, iid))

        # Sort visible rows by timestamp descending
        visible_iids.sort(key=lambda x: x[0], reverse=True)

        # Reattach in correct order
        for _, iid in visible_iids:
            self.tree.reattach(iid, "", "end")

        # Detach invisible rows
        invisible_iids = set(self.all_item_iids) - {iid for _, iid in visible_iids}
        for iid in invisible_iids:
            if self.tree.exists(iid):
                self.tree.detach(iid)

    def open_custom_hours_popup(self):
        if getattr(self, "_custom_popup_open", False):
            return  # already open
        self._custom_popup_open = True

        def on_apply(hours):
            self.custom_hours_var.set(hours)
            self.time_filter_var.set("Custom")
            self.filter_tree_by_time()
            self._custom_popup_open = False

        CustomHoursPopup(
            parent=self.tree.winfo_toplevel(),
            is_dark_mode=self.is_dark_mode,
            initial_hours=self.custom_hours_var.get(),
            callback=on_apply
        )

    def _close_custom_popup(self, popup):
        self._custom_popup_open = False
        popup.destroy()

    # -------------------
    # Image Virtualization
    # -------------------
    def update_visible_images(self):
        first_frac, last_frac = self.tree.yview()
        children = self.tree.get_children()
        total = len(children)
        if total == 0:
            return

        first_idx = int(first_frac * total)
        last_idx = int(last_frac * total) + 1
        current_visible = set(children[first_idx:last_idx])

        # Remove images no longer visible
        for iid in self._last_visible_iids - current_visible:
            if self.tree.exists(iid):
                self.tree.item(iid, image="")
                self.image_cache.pop(iid, None)

        # Add images for newly visible rows
        for iid in current_visible - self._last_visible_iids:
            if iid in self.original_img_cache:
                self.image_cache[iid] = ImageTk.PhotoImage(self.original_img_cache[iid])
                self.tree.item(iid, image=self.image_cache[iid])

        self._last_visible_iids = current_visible
        self.reapply_row_formatting()

    def reapply_row_formatting(self):
        for index, iid in enumerate(self.tree.get_children()):
            if self.is_dark_mode:
                tag = "odd" if index % 2 == 0 else "even"
            else:
                tag = "light_odd" if index % 2 == 0 else "light_even"
            self.tree.item(iid, tags=(tag,))

    def filter_tree_by_time(self, *args):
        current_search = self.search_var.get()
        self.apply_filters(search_query=current_search)
