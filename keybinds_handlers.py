import sys
import threading

import config as c
import curio_tracker as tracker
import toasts
from settings import get_setting

exit_event = threading.Event()
are_toasts_enabled = get_setting('Application', 'are_toasts_enabled', True)  # default: toasts enabled

def handle_capture(root, tree_manager, controls):
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
    root.after(0, tree_manager.update_visible_images)

def handle_snippet(root, tree_manager, controls):
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
            root.after(0, tree_manager.update_visible_images)

        root.after(0, show_items)

    def run_capture():
        tracker.capture_snippet(root, on_done=process_items)

    root.after(0, run_capture)


def handle_layout_capture(root, tree_manager, controls):
    tracker.capture_layout(root)
    root.after(0, controls.refresh_blueprint_info)

def handle_exit(root, tree_manager=None, controls=None):
    tracker.log_message(c.exiting_prompt)
    exit_event.set()
    try:
        root.quit()
        root.destroy()
    except Exception:
        pass
    sys.exit(0)


def handle_debugging_toggle():
    c.DEBUGGING = not c.DEBUGGING
    tracker.log_message(f"Debugging Mode: {"Enabled" if c.DEBUGGING else "Disabled"}")


def register_handlers(root, tree_manager, controls):
    return {
        'capture': lambda: handle_capture(root, tree_manager, controls),
        'snippet': lambda: handle_snippet(root, tree_manager, controls),
        'layout_capture': lambda: handle_layout_capture(root, tree_manager, controls),
        'exit': lambda: handle_exit(root, tree_manager, controls),
        'debug': lambda: handle_debugging_toggle()
    }
