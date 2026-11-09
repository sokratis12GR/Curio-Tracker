import math
import threading
from datetime import datetime
from pathlib import Path
from gui.ctksimplebox import CTkMessageBox

from customtkinter import *
from pytz import InvalidTimeError

import currency_utils
import ocr_utils as utils
from config import ROW_HEIGHT, TREE_COLUMNS, data_file_base
from csv_manager import CSVManager
from gui.frames.item_overview import ItemOverviewFrame
from gui.tree.context_menu import TreeContextMenuMixin
from gui.tree.editing import TreeEditingMixin
from gui.tree.filtering import TreeFilteringMixin, _get_row_tag
from json_manager import JSONManager
from settings import get_setting
from tree_utils import get_item_name_str, generate_item_id


class TreeManager(TreeEditingMixin, TreeContextMenuMixin, TreeFilteringMixin):
    def __init__(self, root, tree, mode, tracker=None):
        self.root = root
        self.display_columns = None
        self.overview_frame = None
        self.tree = tree
        self.tracker = tracker
        self.msgbox = CTkMessageBox(self.root)
        saved_mode = get_setting("Application", "export_mode", default="CSV").upper()
        base = Path(data_file_base)

        if saved_mode == "JSON":
            self.data_mgr = JSONManager(base)
        else:
            self.data_mgr = CSVManager(base)
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
        self.tree.bind("<Button-3>", self.show_context_menu) #EXPERIMENTAL

        self.total_frame = None
        self.col_vars = {}
        self.tree_lock = threading.Lock()

    def switch_data_manager(self, new_mgr):
        self.data_mgr = new_mgr
        self.tracker.data_mgr = new_mgr
        self.refresh_treeview(self.tracker)

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
        bp_enchantment = getattr(item, "bp_enchantment", "None")

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
            "bp_enchantment": bp_enchantment
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

        confirm = self.msgbox.askyesno("Confirm Deletion", msg)
        if not confirm:
            return

        for iid in selected:
            row_values = self.tree.item(iid)['values']

            item_index = self.columns.index("item")
            item_value = row_values[item_index]
            self.modify_record(iid, item_value, delete=True)
            self.tree.delete(iid)
            self.all_item_iids.discard(iid)
            self.item_time_map.pop(iid, None)
            self.csv_row_map.pop(iid, None)
            self.update_total_labels()

    # @pyinstrument.profile()
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
            if not self.msgbox.askyesno("Confirm Deletion", msg):
                return False

        # Perform the deletion
        row_values = self.tree.item(iid)['values']
        item_index = self.columns.index("item")
        item_value = row_values[item_index]
        self.modify_record(iid, item_value, delete=True)

        self.tree.delete(iid)
        self.all_item_iids.discard(iid)
        self.item_time_map.pop(iid, None)
        self.csv_row_map.pop(iid, None)
        self.update_total_labels()

        return True

    def delete_latest_entry(self):
        if not self.all_item_iids:
            self.msgbox.showinfo("Info", "No entries available to delete.")
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
            self.msgbox.showinfo("Info", "No record entries found to delete.")
            return

        self.delete_item_from_tree(record_number=max_record_number)

    # @pyinstrument.profile()
    def _add_items_in_batches(self, items, batch_size=200, start_index=0, post_callback=None, ask_for_confirmation=True):
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

            if ask_for_confirmation:
                self.msgbox.showinfo(
                "Loading Complete",
                f"Finished loading {len(items):,} records."
                )

            if post_callback:
                post_callback()

    # @pyinstrument.profile()
    def load_all_items_threaded(
            self,
            tracker,
            post_callback=None,
            limit=None,
            batch_size=200,
            ask_confirmation=True,
    ):
        self.clear_tree()
        self.should_cancel_process = False

        if ask_confirmation:
            try:
                total_lines = self.data_mgr.get_record_count()
            except AttributeError:
                total_lines = len(tracker.load_all_parsed_items(self.data_mgr))

            if limit is not None:
                total_lines = min(total_lines, limit)

            chunks = math.ceil(total_lines / batch_size)

            seconds_per_item = 0.01

            estimated_seconds = total_lines * seconds_per_item

            if estimated_seconds < 60:
                estimate_text = f"{estimated_seconds:.0f} seconds"
            elif estimated_seconds < 3600:
                estimate_text = f"{estimated_seconds / 60:.1f} minutes"
            else:
                estimate_text = f"{estimated_seconds / 3600:.1f} hours"

            confirm = self.msgbox.askyesno(
                "Load All Data",
                f"This operation will load approximately:\n\n"
                f"• Records: {total_lines:,}\n"
                f"• Batches: {chunks:,}\n"
                f"• Batch Size: {batch_size}\n"
                f"• Estimated Time: {estimate_text}\n\n"
                "Loading a very large dataset may make the application temporarily less responsive.\n\n"
                "Do you want to continue?"
            )

            if not confirm:
                return

        def worker():
            all_items = tracker.load_all_parsed_items(self.data_mgr)
            all_items.sort(
                key=lambda item: getattr(item, "time", datetime.min),
                reverse=True
            )

            if limit is not None:
                all_items = all_items[:limit]

            self.tree.after(
                50,
                self._add_items_in_batches,
                all_items,
                batch_size,
                0,
                post_callback,
                ask_confirmation
            )

        threading.Thread(target=worker, daemon=True).start()

    # @pyinstrument.profile()
    def load_latest_items(self, tracker):
        self.clear_tree()
        self.should_cancel_process = True
        parsed = tracker.load_recent_parsed_items(self.data_mgr)
        print(f"[DEBUG] Loaded {len(parsed)} items")
        if not parsed:
            return

        for item in parsed:
            self.add_item_to_tree(item)

        self.sort_tree("record")
        self.reapply_row_formatting()

    # @pyinstrument.profile()
    def load_latest_item(self, tracker):
        self.clear_tree()
        self.should_cancel_process = True
        parsed = tracker.load_recent_parsed_items(self.data_mgr, max_items=1)  # <-- updated call
        if not parsed:
            return

        item = parsed[0]
        self.add_item_to_tree(item)

        self.sort_tree("record")
        self.reapply_row_formatting()

    def modify_record(self, row_id, item_name, updates=None, delete=False):
        item = self.csv_row_map.get(row_id)
        if not item:
            return

        record_number = getattr(item, "record_number", None)
        if not record_number:
            print("[WARN] Item has no Record #, cannot modify CSV")
            return

        self.data_mgr.modify_record(self.root, record_number, item_name, updates=updates, delete=delete)

        for i, entry in enumerate(self.global_item_tracker):
            if getattr(entry["item_obj"], "record_number", None) == record_number:
                if delete:
                    self.global_item_tracker.pop(i)
                else:
                    for attr, value in (updates or {}).items():
                        setattr(entry["item_obj"], attr.lower().replace(" ", "_"), value)
                break
        else:
            if not delete:
                self.global_item_tracker.append({
                    "iid": row_id,
                    "csv_index": len(self.global_item_tracker),
                    "name": item_name,
                    "item_obj": item
                })

    def bind_overview(self, overview_frame: ItemOverviewFrame):
        self.overview_frame = overview_frame
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_selection)

    # @pyinstrument.profile()
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

    def reapply_row_formatting(self):
        for index, iid in enumerate(self.tree.get_children()):
            tag = _get_row_tag(index)
            self.tree.item(iid, tags=(tag,))

    # @pyinstrument.profile()
    def refresh_treeview(self, tracker=None, ask_for_confirmation=False):
        print("[DEBUG] Refreshing treeview...")

        previous_count = len(self.all_item_iids)
        print(f"[DEBUG] Previously loaded {previous_count} items")

        self.clear_tree()
        self.update_visible_columns()
        self.update_total_labels()

        if tracker is not None and previous_count > 0:
            self.load_all_items_threaded(tracker, limit=previous_count, ask_confirmation=ask_for_confirmation)
        # elif tracker is not None:
        #     self.load_all_items_threaded(tracker)
        else:
            print("[WARN] No tracker passed to refresh_treeview.")

        self.filter_tree_by_time()
        self.reapply_row_formatting()

        print("[DEBUG] Treeview refresh complete.")
