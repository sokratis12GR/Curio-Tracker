import os
import sys
import threading
from tkinter import TclError, Toplevel

import config as c
import curio_keybinds
import curio_tracker as tracker
import toasts
from logger import log_message
from ocr_utils import parse_item_name
from settings import get_setting
from thread_utils import get_background_worker, ui_call
from tree_manager import TreeManager

exit_event = threading.Event()
are_toasts_enabled = get_setting('Application', 'are_toasts_enabled', True)  # default: toasts enabled


def handle_capture(root, tree_manager: TreeManager, controls):
    try:
        tracker.capture_once(root)
    except Exception:
        # Log the full traceback; otherwise the hotkey thread swallows it.
        # Return early so items from the previous capture aren't re-added.
        import traceback
        log_message(f"[ERROR] Capture failed:\n{traceback.format_exc()}")
        return

    if c.DEBUGGING:
        print(f"[DEBUG] Parsed items after capture: {len(tracker.parsed_items)}")

    # Snapshot now: the next capture rebinds tracker.parsed_items.
    new_items = [item for item in tracker.parsed_items if not item.duplicate]

    def show_results():
        if are_toasts_enabled:
            for item in new_items:
                toasts.show(root, item, tree_manager=tree_manager, tracker=tracker)
        for item in new_items:
            tree_manager.add_item_to_tree(item)
        # Controls manage the total count label
        controls.update_total_items_count()

    root.after(0, show_results)


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
                        root.after(0, lambda i=item: toasts.show(root, i, tree_manager=tree_manager, tracker=tracker))
                    tree_manager.add_item_to_tree(item)

            # Updated: use controls for total count
            root.after(0, controls.update_total_items_count)

        root.after(0, show_items)

    # Win11 waits on the Snipping Tool (up to 30s) and runs OCR, so it
    # stays on this background thread. The fallback draws a Tk overlay,
    # which must be created on the main thread.
    if tracker.is_win11():
        tracker.capture_snippet(root, on_done=process_items)
    else:
        root.after(0, lambda: tracker.capture_snippet(root, on_done=process_items))


def handle_layout_capture(root, tree_manager, controls):
    tracker.capture_layout(root)
    # root.after(0, controls.refresh_blueprint_info)


def _terminate():
    try:
        curio_keybinds.stop_global_listener()
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass
    os._exit(0)


def fast_exit(root):
    """Hide every window at once and end the process without Tk's slow per-widget teardown."""
    try:
        for window in [root, *root.winfo_children()]:
            if isinstance(window, Toplevel) or window is root:
                try:
                    window.withdraw()
                except TclError:
                    pass
        root.update_idletasks()
    except Exception:
        pass
    _terminate()


def handle_exit(root):
    tracker.log_message(c.exiting_prompt)

    exit_event.set()

    if threading.current_thread() is threading.main_thread():
        fast_exit(root)
        return

    threading.Timer(1.0, _terminate).start()
    try:
        root.after(0, lambda: fast_exit(root))
    except Exception:
        _terminate()


def handle_debugging_toggle():
    c.DEBUGGING = not c.DEBUGGING
    if c.ENABLE_LOGGING:
        state = "Enabled" if c.DEBUGGING else "Disabled"
        tracker.log_message(f"Debugging Mode: {state}")


def handle_duplicate_latest(root, tree_manager: TreeManager, controls):
    # Duplicate in backend first
    latest_dupe = tree_manager.data_mgr.duplicate_latest(root)
    if not latest_dupe:
        return

    # Parse to tracker items
    duplicated_item = tracker.parse_items_from_rows([latest_dupe])[0]

    if are_toasts_enabled:
        toasts.show(root, duplicated_item, tree_manager=tree_manager, tracker=tracker)

    # Add to tree and update count
    tree_manager.add_item_to_tree(duplicated_item)
    root.after(0, controls.update_total_items_count)

def handle_delete_latest(root, tree_manager: TreeManager, controls):
    if not tree_manager.all_item_iids:
        toasts.show_message(root, "No entries available to delete.", duration=3000)
        return

    # Find the latest item by timestamp
    latest_iid = max(
        tree_manager.all_item_iids,
        key=lambda iid: tree_manager.item_time_map.get(iid, 0)
    )

    item = tree_manager.csv_row_map.get(latest_iid)
    if not item:
        print(f"[WARN] Could not find item object for {latest_iid}")
        return

    record_number = getattr(item, "record_number", None)
    item_name = parse_item_name(item)

    # Delete from tree & backend
    deleted = tree_manager.delete_item_from_tree(
        record_number=record_number,
        item_name=item_name,
        confirm=False
    )

    if deleted:
        # Recalculate last_record_number in backend
        if hasattr(tree_manager.data_mgr, "recalculate_record_number"):
            tree_manager.data_mgr.recalculate_record_number()

        tracker.remove_recent_term(item_name)
        root.after(0, controls.update_total_items_count)

        if are_toasts_enabled:
            toasts.show_message(root, f"Deleted Record #{record_number} entry: {item_name}", duration=3000)
    else:
        if are_toasts_enabled:
            toasts.show_message(root, "Failed to delete latest entry.", duration=3000)

def handle_show_highest_value(root, tree_manager: TreeManager, controls):
    rows = tree_manager.data_mgr.load_dict()

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

def handle_cycle_bp_enchantment(root):
    try:
        current = c.SET_BP_ENCHANTMENT_FOR_RUNS

        try:
            index = c.BP_ENCHANTMENT_OPTIONS.index(current)
        except ValueError:
            index = 0

        index = (index + 1) % len(c.BP_ENCHANTMENT_OPTIONS)

        new_enchantment = c.BP_ENCHANTMENT_OPTIONS[index]

        c.SET_BP_ENCHANTMENT_FOR_RUNS = new_enchantment

        tracker.bp_enchantment = new_enchantment

        from settings import set_setting
        set_setting("Blueprint","bp_enchantment", new_enchantment)

        if are_toasts_enabled:
            toasts.show_message(
                root,
                f"Blueprint Enchantment: {new_enchantment}",
                duration=2500
            )

        if c.ENABLE_LOGGING:
            tracker.log_message(
                f"Blueprint Enchantment set to: {new_enchantment}"
            )

    except Exception as e:
        if c.DEBUGGING:
            print(e)

#############################################################
# Handlers are invoked on the keyboard/controller listener  #
# thread, which must return quickly (Windows drops slow     #
# low-level hooks). Each handler is therefore routed:       #
#  - in_background: OCR/screen work, serialized on a single #
#    worker so captures never overlap.                      #
#  - on_ui: touches the tree/widgets, run on the Tk thread. #
#############################################################
def register_handlers(root, tree_manager, controls):
    worker = get_background_worker()

    def in_background(name, fn):
        return lambda: worker.submit(fn, label=name)

    def preempting_snippet(name, fn):
        submit = in_background(name, fn)

        def trigger():
            tracker.cancel_pending_snippet()
            submit()
        return trigger

    def on_ui(fn):
        return lambda: ui_call(root, fn)

    return {
        'capture': preempting_snippet('capture', lambda: handle_capture(root, tree_manager, controls)),
        'snippet': preempting_snippet('snippet', lambda: handle_snippet(root, tree_manager, controls)),
        'layout_capture': in_background('layout_capture', lambda: handle_layout_capture(root, tree_manager, controls)),
        'exit': lambda: handle_exit(root),
        'duplicate_latest': on_ui(lambda: handle_duplicate_latest(root, tree_manager, controls)),
        'delete_latest': on_ui(lambda: handle_delete_latest(root, tree_manager, controls)),
        'show_highest_value': on_ui(lambda: handle_show_highest_value(root, tree_manager, controls)),
        'debug': lambda: handle_debugging_toggle(),
        'cycle_bp_enchantment': on_ui(lambda: handle_cycle_bp_enchantment(root))
    }

