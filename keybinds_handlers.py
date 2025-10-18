import sys
import threading
from tkinter import TclError

import config as c
import curio_tracker as tracker
import toasts
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
    duplicated_item = tracker.duplicate_latest_csv_entry(root, c.csv_file_path)

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
        root.after(0, controls.update_total_items_count)
    else:
        if are_toasts_enabled:
            toasts.show_message(root, "Failed to delete latest entry.", duration=3000)


def register_handlers(root, tree_manager, controls):
    return {
        'capture': lambda: handle_capture(root, tree_manager, controls),
        'snippet': lambda: handle_snippet(root, tree_manager, controls),
        'layout_capture': lambda: handle_layout_capture(root, tree_manager, controls),
        'exit': lambda: handle_exit(root),
        'duplicate_latest': lambda: handle_duplicate_latest(root, tree_manager, controls),
        'delete_latest': lambda: handle_delete_latest(root, tree_manager, controls),
        'debug': lambda: handle_debugging_toggle()
    }
