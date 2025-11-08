import sys
import threading
from tkinter import TclError

import config as c
import curio_tracker as tracker
import toasts
from csv_manager import CSVManager
from logger import log_message
from ocr_utils import parse_item_name
from settings import get_setting
from tree_manager import TreeManager

exit_event = threading.Event()
are_toasts_enabled = get_setting('Application', 'are_toasts_enabled', True)  # default: toasts enabled


def handle_capture(root, tree_manager: TreeManager, controls):
    tracker.capture_once(root)

    if c.DEBUGGING:
        print(f"[DEBUG] Parsed items after capture: {len(tracker.parsed_items)}")

    for item in tracker.parsed_items:
        if not item.duplicate:
            if are_toasts_enabled:
                toasts.show(root, item)
            tree_manager.add_item_to_tree(item)

    # Controls now manage the total count label
    root.after(0, controls.update_total_items_count)


def handle_snippet(root, tree_manager: TreeManager, controls):
    def process_items(items):
        items = items or []
        if not items:
            if c.DEBUGGING:
                print("[INFO] No items parsed during snippet capture.")
            return

        def show_items():
            for item in items:
                if not item.duplicate:
                    if are_toasts_enabled:
                        root.after(0, lambda i=item: toasts.show(root, i))
                    tree_manager.add_item_to_tree(item)

            # Updated: use controls for total count
            root.after(0, controls.update_total_items_count)

        root.after(0, show_items)

    def run_capture():
        tracker.capture_snippet(root, on_done=process_items)

    root.after(0, run_capture)


def handle_layout_capture(root, tree_manager, controls):
    tracker.capture_layout(root)
    root.after(0, controls.refresh_blueprint_info)


def handle_exit(root):
    tracker.log_message(c.exiting_prompt)

    exit_event.set()

    try:
        def safe_quit_destroy(*args):
            try:
                root.quit()
                root.destroy()
            except TclError:
                pass

        if threading.current_thread() is threading.main_thread():
            safe_quit_destroy()
        else:
            root.after(0, safe_quit_destroy)
    except Exception as e:
        if c.DEBUGGING:
            print(f"[WARN] handle_exit GUI shutdown failed: {e}")

    try:
        sys.exit(0)
    except SystemExit:
        pass


def handle_debugging_toggle():
    c.DEBUGGING = not c.DEBUGGING
    if c.ENABLE_LOGGING:
        tracker.log_message(f"Debugging Mode: {"Enabled" if c.DEBUGGING else "Disabled"}")


def handle_duplicate_latest(root, tree_manager: TreeManager, controls):
    csv_manager = CSVManager()
    latest_dupe = csv_manager.duplicate_latest(root)
    duplicated_item = tracker.parse_items_from_rows([latest_dupe])[0]

    if are_toasts_enabled:
        toasts.show(root, duplicated_item)
    tree_manager.add_item_to_tree(duplicated_item)
    root.after(0, controls.update_total_items_count)


def handle_delete_latest(root, tree_manager: TreeManager, controls):
    if not tree_manager.all_item_iids:
        toasts.show_message(root, "No entries available to delete.", duration=3000)
        return

    latest_iid = max(
        tree_manager.all_item_iids,
        key=lambda iid: tree_manager.item_time_map.get(iid, None) or 0
    )

    item = tree_manager.csv_row_map.get(latest_iid)
    if not item:
        print(f"[WARN] Could not find item object for {latest_iid}")
        return

    record_number = getattr(item, "record_number", None)
    item_name = parse_item_name(item)

    deleted = tree_manager.delete_item_from_tree(
        record_number=record_number,
        item_name=item_name,
        confirm=False
    )

    if deleted:
        if are_toasts_enabled:
            toasts.show_message(root, f"Deleted latest entry: {item_name}", duration=3000)
        csv_manager = CSVManager()
        csv_manager.recalculate_record_number()
        root.after(0, controls.update_total_items_count)
    else:
        if are_toasts_enabled:
            toasts.show_message(root, "Failed to delete latest entry.", duration=3000)



def handle_show_highest_value(root, tree_manager, controls):
    csv_manager = CSVManager()
    rows = csv_manager.load_csv_dict()

    if not rows:
        toasts.show_message(root, "No data found in CSV.", duration=3000)
        log_message("[DEBUG] CSV is empty or failed to load.")
        return

    from datetime import datetime
    dupe_duration = int(c.time_last_dupe_check_seconds or 60)

    parsed_rows = []
    for row in rows:
        ts_str = row.get(c.csv_time_header)
        if not ts_str:
            continue
        try:
            entry_time = datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S")
            parsed_rows.append((row, entry_time))
        except ValueError:
            continue

    if not parsed_rows:
        toasts.show_message(root, "No valid timestamps found in CSV.", duration=3000)
        log_message("[DEBUG] No rows with valid timestamps.")
        return

    # Find the latest timestamp in the CSV
    latest_time = max(ts for _, ts in parsed_rows)
    log_message(f"[DEBUG] Latest CSV timestamp: {latest_time}")
    log_message(f"[DEBUG] Using a dupe_duration of {dupe_duration} seconds to filter recent entries.")

    # Filter rows relative to the latest timestamp
    recent_entries = [row for row, ts in parsed_rows if (latest_time - ts).total_seconds() <= dupe_duration]

    if not recent_entries:
        toasts.show_message(root, "No recent entries found.", duration=3000)
        log_message("[DEBUG] No entries within dupe_duration of the latest timestamp.")
        return

    def parse_value(row):
        val = row.get("estimated_value_chaos") or row.get("chaos_value") or "0"
        try:
            return float(val)
        except ValueError:
            return 0.0

    highest_entry = max(recent_entries, key=parse_value, default=None)

    if not highest_entry:
        toasts.show_message(root, "No valid chaos values found in recent entries.", duration=3000)
        log_message("[DEBUG] No valid chaos values found after parsing recent entries.")
        return

    item = tracker.parse_items_from_rows([highest_entry])[0]

    if are_toasts_enabled:
        try:
            toasts.show_custom(root, item, toasts.CustomToastOptions(
                is_highlight=True,
                headline="HIGHEST VALUE"
            ))
        except Exception as e:
            log_message(f"[WARN] Failed to show custom toast: {e}")

    log_message(f"[DEBUG] Highest value recent item: {item.item_name} ({parse_value(highest_entry)} chaos)")


def register_handlers(root, tree_manager, controls):
    return {
        'capture': lambda: handle_capture(root, tree_manager, controls),
        'snippet': lambda: handle_snippet(root, tree_manager, controls),
        'layout_capture': lambda: handle_layout_capture(root, tree_manager, controls),
        'exit': lambda: handle_exit(root),
        'duplicate_latest': lambda: handle_duplicate_latest(root, tree_manager, controls),
        'delete_latest': lambda: handle_delete_latest(root, tree_manager, controls),
        'show_highest_value': lambda: handle_show_highest_value(root, tree_manager, controls),
        'debug': lambda: handle_debugging_toggle()
    }
