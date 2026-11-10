import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import TclError
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
from gui.tree.filtering import TreeFilteringMixin, _get_row_tag, row_chaos_value, PICKED_CELL_VALUES
from json_manager import JSONManager
from settings import get_setting
from tree_utils import get_item_name_str, generate_item_id


# Measured cost of a full load (read, parse, build, insert).
SECONDS_PER_ROW = 0.000075
# How long each UI-thread insert slice may run before yielding.
LOAD_SLICE_SECONDS = 0.03


def format_load_estimate(row_count):
    seconds = row_count * SECONDS_PER_ROW
    if seconds < 1:
        return "under a second"
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    return f"{seconds / 60:.1f} minutes"


def _record_key(record_number):
    text = str(record_number).strip() if record_number is not None else ""
    return int(text) if text.isdigit() else None


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
        # Record numbers shift when earlier records are deleted, so rows
        # use stable iids and are looked up by record number through this map.
        self.record_to_iid = {}
        self._next_row_id = 0
        # Bumped on every clear so a running background load stops.
        self._load_generation = 0
        self._last_visible_iids = set()
        # Per-row caches used by totals, filters and striping.
        self._row_totals = {}
        self._search_text = {}
        self._row_tags = {}
        self._hook_tree_writes()
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
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<Delete>", self.delete_selected_items)
        self.tree.bind("<Button-3>", self.show_context_menu) #EXPERIMENTAL

        self.total_frame = None
        self.col_vars = {}
        self.tree_lock = threading.Lock()

    def _hook_tree_writes(self):
        #############################################################
        # Cells are edited from many places (editing, context menu, #
        # record shifts). Wrapping set/delete once keeps the row    #
        # caches correct without touching each of those callers.    #
        #############################################################
        tree = self.tree
        original_set = tree.set
        original_delete = tree.delete

        def tracked_set(item, column=None, value=None):
            if value is not None:
                self._row_totals.pop(item, None)
                self._search_text.pop(item, None)
            return original_set(item, column, value)

        def tracked_delete(*items):
            for iid in items:
                self._row_totals.pop(iid, None)
                self._search_text.pop(iid, None)
                self._row_tags.pop(iid, None)
                self.all_item_iids.discard(iid)
            return original_delete(*items)

        tree.set = tracked_set
        tree.delete = tracked_delete

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

    def get_iid_for_record(self, record_number):
        key = _record_key(record_number)
        return self.record_to_iid.get(key) if key is not None else None

    def add_item_to_tree(self, item, insert_at_top=True, defer_formatting=False):
        #############################################################
        # defer_formatting: skip per-row striping and total updates #
        # (both walk every row). Batch loaders set it and run them  #
        # once at the end instead.                                  #
        #############################################################
        built = self._build_row(item)
        inserted = self._insert_built_row(item, built, 0 if insert_at_top else "end")

        if inserted and not defer_formatting:
            self._stripe_from_neighbor(self.record_to_iid.get(built[0]) if built[0] is not None else None,
                                       insert_at_top)
            self.update_total_labels()

    def _stripe_from_neighbor(self, iid, inserted_at_top):
        # Stripes only need to alternate, so a single new row takes the
        # opposite tag of its neighbour instead of restriping every row.
        if iid is None or not self.tree.exists(iid):
            self.reapply_row_formatting()
            return
        neighbor = self.tree.next(iid) if inserted_at_top else self.tree.prev(iid)
        neighbor_tag = self._row_tags.get(neighbor) if neighbor else "even"
        if neighbor_tag not in ("odd", "even"):
            self.reapply_row_formatting()
            return
        self._set_row_tag(iid, "even" if neighbor_tag == "odd" else "odd")

    def _build_row(self, item):
        #############################################################
        # Computes everything a row needs without touching Tk, so   #
        # background loaders can run it off the UI thread.          #
        # Returns (record_key, time_obj, values).                   #
        #############################################################
        record_number = getattr(item, "record_number", None)
        record_key = _record_key(record_number)

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
        totals_entry = (row_chaos_value(item), picked_text in PICKED_CELL_VALUES)
        return record_key, item_time_obj, values, totals_entry

    def _insert_built_row(self, item, built, index, tags=()):
        record_key, item_time_obj, values, totals_entry = built

        # Avoid duplicate insert for same record
        if record_key is not None and record_key in self.record_to_iid:
            return False

        if record_key is not None:
            self._next_row_id += 1
            iid = f"row_{self._next_row_id}"
            self.record_to_iid[record_key] = iid
        else:
            iid = generate_item_id(item)

        self.item_time_map[iid] = item_time_obj
        self.csv_row_map[iid] = item
        self.tree.insert("", index, iid=iid, image="", values=values, tags=tags)
        self.all_item_iids.add(iid)
        self._row_totals[iid] = totals_entry
        if tags:
            self._row_tags[iid] = tags[0]

        # ---- Track globally ----
        self.global_item_tracker.append({
            "iid": iid,
            "csv_index": len(self.global_item_tracker),
            "name": get_item_name_str(item),
            "item_obj": item
        })
        return True

    def force_clear_tree(self):
        self.should_cancel_process = True
        self.clear_tree()
        self.update_total_labels()

    def clear_tree(self):
        # Include rows detached by a filter; get_children() skips them.
        stale = set(self.tree.get_children()) | self.all_item_iids
        try:
            self.tree.delete(*stale)
        except TclError:
            # Fallback if a tracked iid was already gone.
            self.tree.delete(*[i for i in stale if self.tree.exists(i)])
        self.all_item_iids.clear()
        self._row_totals.clear()
        self._search_text.clear()
        self._row_tags.clear()
        self.csv_row_map.clear()
        self.record_to_iid.clear()
        self.sorted_item_keys.clear()
        self.item_time_map.clear()
        self._last_visible_iids.clear()
        self.global_item_tracker.clear()
        self._load_generation += 1

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
        self.reapply_row_formatting()
        self.update_total_labels()

    # @pyinstrument.profile()
    def delete_item_from_tree(self, record_number=None, item_name=None, confirm=True):
        if record_number is not None:
            iid = self.get_iid_for_record(record_number)
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
        self.reapply_row_formatting()
        self.update_total_labels()

        return True

    def delete_latest_entry(self):
        if not self.all_item_iids:
            self.msgbox.showinfo("Info", "No entries available to delete.")
            return

        max_record_number = max(self.record_to_iid, default=-1)

        if max_record_number == -1:
            self.msgbox.showinfo("Info", "No record entries found to delete.")
            return

        self.delete_item_from_tree(record_number=max_record_number)

    #############################################################
    # Background loading: the worker thread reads, parses,      #
    # orders and builds every row; the UI thread only inserts,  #
    # in short time slices so the window stays responsive.      #
    #############################################################
    def _dedupe_by_record(self, items):
        # Only the first item per record number gets a row.
        seen = set()
        result = []
        for item in items:
            key = _record_key(getattr(item, "record_number", None))
            if key is not None:
                if key in seen:
                    continue
                seen.add(key)
            result.append(item)
        return result

    def _run_in_background(self, work, on_result):
        # Tk calls must stay on the UI thread, so the UI polls for the
        # worker's result instead of the worker scheduling callbacks.
        result = []

        def worker():
            try:
                result.append(work())
            except Exception as e:
                print(f"[ERROR] Background task failed: {e}")
                result.append(None)

        def poll():
            if result:
                on_result(result[0])
            else:
                self.tree.after(20, poll)

        threading.Thread(target=worker, daemon=True).start()
        self.tree.after(20, poll)

    def load_in_background(self, prepare_items, on_done=None):
        self.clear_tree()
        self.should_cancel_process = False
        generation = self._load_generation

        def build():
            return [(item, self._build_row(item)) for item in prepare_items()]

        self._run_in_background(
            build,
            lambda rows: self._insert_rows_in_slices(generation, rows or [], 0, on_done),
        )

    def _insert_rows_in_slices(self, generation, rows, start, on_done):
        if generation != self._load_generation or self.should_cancel_process:
            return

        total = len(rows)
        deadline = time.perf_counter() + LOAD_SLICE_SECONDS
        index = start
        while index < total:
            item, built = rows[index]
            self._insert_built_row(item, built, "end", tags=(_get_row_tag(index),))
            index += 1
            if index % 50 == 0 and time.perf_counter() >= deadline:
                break

        if index < total:
            self._show_load_progress(index, total)
            self.tree.after(1, self._insert_rows_in_slices, generation, rows, index, on_done)
            return

        # A capture inserted while loading shifts the stripes.
        if len(self.tree.get_children()) != total:
            self.reapply_row_formatting()
        self.update_total_labels()
        if on_done:
            on_done(total)

    def _show_load_progress(self, done, total):
        frame = getattr(self, "total_frame", None)
        if frame:
            frame.total_value_label.configure(text=f"Loading {done:,} / {total:,}")

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
        reverse = self.sort_reverse.get("record", False)

        def prepare():
            all_items = tracker.load_all_parsed_items(self.data_mgr)
            all_items.sort(key=lambda item: str(getattr(item, "time", "") or ""), reverse=True)
            if limit is not None:
                all_items = all_items[:limit]
            all_items = self._dedupe_by_record(all_items)
            # Same order sort_tree("record") produces; rows without a
            # number stay at the end.
            numbered = [i for i in all_items if _record_key(getattr(i, "record_number", None)) is not None]
            unnumbered = [i for i in all_items if _record_key(getattr(i, "record_number", None)) is None]
            numbered.sort(key=lambda i: _record_key(i.record_number), reverse=reverse)
            return numbered + unnumbered

        def on_done(count):
            self.sort_reverse["record"] = not reverse
            if ask_confirmation:
                self.msgbox.showinfo("Loading Complete", f"Finished loading {count:,} records.")
            if post_callback:
                post_callback()

        if not ask_confirmation:
            self.load_in_background(prepare, on_done)
            return

        # Count in the background too (JSON has to be parsed to count),
        # then ask on the UI thread.
        def ask(total_lines):
            total_lines = total_lines or 0
            if limit is not None:
                total_lines = min(total_lines, limit)

            confirm = self.msgbox.askyesno(
                "Load All Data",
                f"This operation will load approximately:\n\n"
                f"• Records: {total_lines:,}\n"
                f"• Estimated Time: {format_load_estimate(total_lines)}\n\n"
                "Loading a very large dataset may make the application temporarily less responsive.\n\n"
                "Do you want to continue?"
            )
            if confirm:
                self.load_in_background(prepare, on_done)

        self._run_in_background(self.data_mgr.get_record_count, ask)

    # @pyinstrument.profile()
    def load_latest_items(self, tracker):
        self.clear_tree()
        self.should_cancel_process = True
        parsed = tracker.load_recent_parsed_items(self.data_mgr)
        print(f"[DEBUG] Loaded {len(parsed)} items")
        if not parsed:
            return

        for item in parsed:
            self.add_item_to_tree(item, defer_formatting=True)

        self.sort_tree("record")
        self.reapply_row_formatting()
        self.update_total_labels()

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

        if delete:
            self._shift_records_after_delete(record_number)

        # Match by object: after a delete-shift another item may now carry
        # the deleted record number.
        for i, entry in enumerate(self.global_item_tracker):
            if entry["item_obj"] is item:
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

    def _shift_records_after_delete(self, deleted_record):
        #############################################################
        # Mirrors the data file: every loaded record numbered above #
        # the deleted one moves down by one. Only the "record" cell #
        # of the affected rows is rewritten, no full reload.        #
        #############################################################
        deleted = _record_key(deleted_record)
        if deleted is None:
            return

        self.record_to_iid.pop(deleted, None)
        has_record_column = "record" in self.columns
        new_map = {}

        for number, iid in self.record_to_iid.items():
            if number > deleted:
                number -= 1
                item = self.csv_row_map.get(iid)
                if item is not None:
                    old = getattr(item, "record_number", None)
                    # Keep the attribute's original type (str or int).
                    item.record_number = str(number) if isinstance(old, str) else number
                if has_record_column and self.tree.exists(iid):
                    self.tree.set(iid, "record", number)
            new_map[number] = iid

        self.record_to_iid = new_map

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
        self._restripe(self.tree.get_children())

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
