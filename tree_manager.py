import threading
from datetime import datetime, timedelta
from tkinter import messagebox

from customtkinter import *
from pytz import InvalidTimeError

import currency_utils
import ocr_utils as utils
from config import ROW_HEIGHT, layout_keywords, TREE_COLUMNS, DEBUGGING
from csv_manager import CSVManager
from gui.custom_hours_popup import CustomHoursPopup
from gui.item_overview_frame import ItemOverviewFrame
from settings import get_setting
from tree_utils import get_item_name_str, generate_item_id


def _get_row_tag(index):
    return "odd" if index % 2 == 0 else "even"


class TreeManager:
    def __init__(self, root, tree, mode):
        self.root = root
        self.display_columns = None
        self.overview_frame = None
        self.tree = tree
        self.csv_manager = CSVManager()
        self.tree_columns = TREE_COLUMNS
        self.columns = [col["id"] for col in TREE_COLUMNS]
        self.update_visible_columns()
        self.row_height = ROW_HEIGHT
        self.current_mode = mode
        self._custom_popup_open = False
        self.time_filter_var = StringVar(value="All")
        self.custom_hours_var = DoubleVar(value=1)
        self.time_filter_var.trace_add("write", self.filter_tree_by_time)
        self.search_var = StringVar(value="")
        self.search_var.trace_add("write", lambda *args: self.apply_filters())

        self.should_cancel_process = False

        # Data trackers
        self.global_item_tracker = []
        self.sorted_item_keys = []
        self.item_time_map = {}
        self.all_item_iids = set()
        self.csv_row_map = {}
        self._last_visible_iids = set()
        self.sort_reverse = {col["id"]: col.get("sort_reverse", False) for col in TREE_COLUMNS}

        # Row tags
        if self.current_mode == "POE":
            self.tree.tag_configure("poe_odd", background="#2a1a12", foreground="#e6dcc0")
            self.tree.tag_configure("poe_even", background="#3a2618", foreground="#e6dcc0")
        elif self.current_mode == "DARK":
            self.tree.tag_configure("odd", background="#2f3136", foreground="#dcddde")
            self.tree.tag_configure("even", background="#36393f", foreground="#dcddde")
        elif self.current_mode == "LIGHT":
            self.tree.tag_configure("light_odd", background="#f4f6f8", foreground="black")
            self.tree.tag_configure("light_even", background="#e8eaed", foreground="black")

        self.checkbox_states = {}
        # Bind events
        self.tree.bind("<Configure>", lambda e: self.reapply_row_formatting())
        self.tree.bind("<Motion>", lambda e: self.reapply_row_formatting())
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Delete>", self.delete_selected_items)

        self.total_frame = None
        self.col_vars = {}
        self.tree_lock = threading.Lock()

    def update_visible_columns(self):
        enabled_poeladder = get_setting("Application", "enable_poeladder", False)
        self.display_columns = [
            col["id"]
            for col in self.tree_columns
            if get_setting("Columns", col["id"], True)
               and col["id"] != "numeric_value"
               and not (col["id"] == "owned" and not enabled_poeladder)
        ]
        self.tree["displaycolumns"] = tuple(self.display_columns)

    def add_item_to_tree(self, item, insert_at_top=True):

        item_name_str = get_item_name_str(item)
        record_number = getattr(item, "record_number", None)
        if record_number:
            item_key = f"rec_{record_number}"
        else:
            item_key = generate_item_id(item)

        # Avoid duplicate insert for same record
        if record_number and self.tree.exists(f"rec_{record_number}"):
            return

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

        display_value = currency_utils.calculate_estimate_value(item)
        numeric_value = currency_utils.convert_to_float(chaos_value)

        _, stack_size_txt = currency_utils.get_stack_size(item)

        item_tier = getattr(item, "tier", "")
        area_level = getattr(item, "area_level", "83")
        blueprint_type = getattr(item, "blueprint_type", "Prohibited Library")
        logged_by = getattr(item, "logged_by", "")
        league = getattr(item, "league", "3.26")
        owned = getattr(item, "owned", False)
        picked = getattr(item, "picked", False)
        display_text = ""
        if utils.is_unique(item_type):
            display_text = "☑" if owned else "☐"
        picked_text = "☑" if picked in ("True", "TRUE", True) else "☐"

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
            "owned": display_text,
            "picked": picked_text,
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

        self.reapply_row_formatting()
        self.update_total_labels()

    def force_clear_tree(self):
        self.should_cancel_process = True
        self.clear_tree()
        self.update_total_labels()

    def clear_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.all_item_iids.clear()
        self.csv_row_map.clear()
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
            self.item_time_map.pop(iid, None)
            self.csv_row_map.pop(iid, None)
            self.update_total_labels()

    def delete_item_from_tree(self, record_number=None, item_name=None, confirm=True):
        if record_number is not None:
            iid = f"rec_{record_number}"
        else:
            iid = None
            for i in self.all_item_iids:
                item = self.csv_row_map.get(i)
                if not item:
                    continue
                name_str = utils.parse_item_name(item)
                if name_str == item_name:
                    iid = i
                    break

        if not iid or not self.tree.exists(iid):
            print(f"[WARN] Item not found in tree (record={record_number}, name={item_name})")
            return False

        if confirm:
            msg = f"Are you sure you want to delete this record?\n\n{item_name or iid}"
            if not messagebox.askyesno("Confirm Deletion", msg):
                return False

        # Perform the deletion
        row_values = self.tree.item(iid)['values']
        item_index = self.columns.index("item")
        item_value = row_values[item_index]
        self.modify_csv_record(iid, item_value, delete=True)

        self.tree.delete(iid)
        self.all_item_iids.discard(iid)
        self.item_time_map.pop(iid, None)
        self.csv_row_map.pop(iid, None)
        self.update_total_labels()

        return True

    def delete_latest_entry(self):
        if not self.all_item_iids:
            messagebox.showinfo("Info", "No entries available to delete.")
            return

        max_record_number = -1
        for iid in self.all_item_iids:
            if iid.startswith("rec_"):
                try:
                    rec_num = int(iid.replace("rec_", ""))
                    if rec_num > max_record_number:
                        max_record_number = rec_num
                except ValueError:
                    continue

        if max_record_number == -1:
            messagebox.showinfo("Info", "No record entries found to delete.")
            return

        self.delete_item_from_tree(record_number=max_record_number)

    def _add_items_in_batches(self, items, batch_size=200, start_index=0, post_callback=None):
        if self.should_cancel_process:
            return
        end_index = min(start_index + batch_size, len(items))
        batch = items[start_index:end_index]

        for item in batch:
            self.add_item_to_tree(item, insert_at_top=False)

        if end_index < len(items):
            self.tree.after(
                15,
                self._add_items_in_batches,
                items,
                batch_size,
                end_index,
                post_callback
            )
        else:
            self.reapply_row_formatting()
            self.sort_tree("record")
            if post_callback:
                post_callback()

    def load_all_items_threaded(self, tracker, post_callback=None, limit=None):
        self.clear_tree()
        self.should_cancel_process = False

        def worker():
            all_items = tracker.load_all_parsed_items_from_csv()
            all_items.sort(key=lambda item: getattr(item, "time", datetime.min), reverse=True)

            if limit is not None:
                all_items = all_items[:limit]

            self.tree.after(
                50,
                self._add_items_in_batches,
                all_items,
                200,
                0,
                post_callback
            )

        threading.Thread(target=worker, daemon=True).start()

    def load_latest_items(self, tracker):
        self.clear_tree()
        self.should_cancel_process = True
        parsed = tracker.load_recent_parsed_items_from_csv()
        print(f"[DEBUG] Loaded {len(parsed)} items")  # <--- check this
        if not parsed:
            return

        for item in parsed:
            self.add_item_to_tree(item)

        self.sort_tree("record")
        self.reapply_row_formatting()

    def load_latest_item(self, tracker):
        self.clear_tree()
        self.should_cancel_process = True
        parsed = tracker.load_recent_parsed_items_from_csv(max_items=1)
        if not parsed:
            return

        item = parsed[0]
        self.add_item_to_tree(item)

        self.sort_tree("record")
        self.reapply_row_formatting()

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
        self.modify_csv_record(row_id, item_text, updates={"Picked": new_state})
        self.update_total_labels()

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
            self.modify_csv_record(row_id, item_text, updates={"Picked": new_state})
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
                    messagebox.showerror("Invalid Stack Size", "Enter a number between 1–40 or leave blank.")
                    return

                self.tree.set(row_id, col_name, stack_val)
                if item:
                    item.stack_size = stack_val if stack_val != "" else None

                    # Reuse utils.calculate_estimate_value
                    display_value = currency_utils.calculate_estimate_value(item)
                    numeric_value = currency_utils.convert_to_float(getattr(item, "chaos_value", 0)) * (item.stack_size or 1)

                    self.tree.set(row_id, "value", display_value)
                    self.tree.set(row_id, "numeric_value", numeric_value)

                self.modify_csv_record(row_id, item_text, updates={"Stack Size": new_value})

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

        self.csv_manager.modify_record(self.root, record_number, item_name, updates=updates, delete=delete)

    def bind_overview(self, overview_frame: ItemOverviewFrame):
        self.overview_frame = overview_frame
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_selection)

    def on_tree_selection(self, event):
        selected = self.tree.selection()
        if not selected:
            if hasattr(self, "overview_frame"):
                self.overview_frame.update_item(None)
            return

        iid = selected[0]
        item = self.csv_row_map.get(iid)
        if hasattr(self, "overview_frame"):
            self.overview_frame.update_item(item)

    def calculate_totals(self):
        total_chaos = 0.0
        total_divine = 0.0
        picked_chaos = 0.0
        picked_divine = 0.0

        league_divine_equiv = currency_utils.convert_to_float(
            get_setting("Application", "divine_equivalent", 0)
        )

        for iid in self.all_item_iids:
            if not self.tree.exists(iid):
                continue

            item = self.csv_row_map.get(iid)
            if not item:
                continue

            chaos_value = currency_utils.convert_to_float(getattr(item, "chaos_value", 0))
            stack_size, _ = currency_utils.get_stack_size(item)
            chaos_value *= stack_size

            divine_value = chaos_value / league_divine_equiv if league_divine_equiv > 0 else 0

            total_chaos += chaos_value
            total_divine += divine_value

            picked_value = self.tree.set(iid, "picked")
            if str(picked_value).strip() in ("☑", "True", "true", "YES", "yes"):
                picked_chaos += chaos_value
                picked_divine += divine_value

        return total_chaos, total_divine, picked_chaos, picked_divine

    def update_total_labels(self):
        if not hasattr(self, "total_frame") or not self.total_frame:
            return

        total_chaos, total_divine, picked_chaos, picked_divine = self.calculate_totals()

        mode = self.total_frame.value_mode.get()
        if mode == "Divine":
            total_value = total_divine
            total_picked_value = picked_divine
            suffix = " Divines"
        else:
            total_value = total_chaos
            total_picked_value = picked_chaos
            suffix = " Chaos"

        total_text = f"Total Value: {total_value:.2f}{suffix}" if total_value else ""
        picked_text = f"Picked Value: {total_picked_value:.2f}{suffix}" if total_picked_value else ""

        self.total_frame.total_value_label.configure(text=total_text)
        self.total_frame.total_picked_label.configure(text=picked_text)

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
            elif column == "tier" or column == "stack_size":
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
            tag = _get_row_tag(index)
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
            initial_hours=self.custom_hours_var.get(),
            callback=on_apply
        )

    def _close_custom_popup(self, popup):
        self._custom_popup_open = False
        popup.destroy()

    def reapply_row_formatting(self):
        for index, iid in enumerate(self.tree.get_children()):
            tag = _get_row_tag(index)
            self.tree.item(iid, tags=(tag,))

    def refresh_treeview(self, tracker=None):
        print("[DEBUG] Refreshing treeview...")

        previous_count = len(self.all_item_iids)
        print(f"[DEBUG] Previously loaded {previous_count} items")

        self.clear_tree()
        self.update_visible_columns()
        self.update_total_labels()

        if tracker is not None and previous_count > 0:
            self.load_all_items_threaded(tracker, limit=previous_count)
        # elif tracker is not None:
        #     self.load_all_items_threaded(tracker)
        else:
            print("[WARN] No tracker passed to refresh_treeview.")

        self.filter_tree_by_time()
        self.reapply_row_formatting()

        print("[DEBUG] Treeview refresh complete.")

    def filter_tree_by_time(self, *args):
        current_search = self.search_var.get()
        self.apply_filters(search_query=current_search)
