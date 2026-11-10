import time

from customtkinter import CTkInputDialog

from gui.ctksimplebox import CTkMessageBox
from tree_manager import TreeManager, format_load_estimate
from win_utils import center_window_on_parent


class CustomLoader:
    def __init__(self, root, controls, tree_manager: TreeManager, tracker):
        self.root = root
        self.controls = controls
        self.tree_manager = tree_manager
        self.tracker = tracker
        self.msgbox = CTkMessageBox(root)

        # import tkinter.messagebox as messagebox
        # self.msgbox = CTkMessageBox(root)
        # messagebox.showinfo = self.msgbox.showinfo
        # messagebox.showwarning = self.msgbox.showwarning
        # messagebox.showerror = self.msgbox.showerror
        # messagebox.askyesno = self.msgbox.askyesno

    def run(self):
        try:
            dialog = CTkInputDialog(
                text="Enter the number of entries to load:",
                title="Load Entries"
            )

            center_window_on_parent(
                dialog,
                self.root
            )

            max_items = dialog.get_input()

            if max_items is None:
                return  # user cancelled

            max_items = int(max_items)
            if max_items < 1:
                raise ValueError
        except Exception:
            self.msgbox.showerror("Invalid Input", "Please enter a valid number.")
            return

        confirm = self.msgbox.askyesno(
            "Load Entries",
            f"Load approximately:\n\n"
            f"• Entries: {max_items:,}\n"
            f"• Estimated Time: {format_load_estimate(max_items)}\n\n"
            "Large loads may temporarily reduce responsiveness.\n\n"
            "Continue?"
        )

        if not confirm:
            return

        self.load_start_time = time.perf_counter()
        tm = self.tree_manager

        def prepare():
            # Newest first, keep max_items, then back to file order
            all_items = self.tracker.load_all_parsed_items(tm.data_mgr)
            newest_first = tm._dedupe_by_record(all_items[::-1][:max_items])
            return newest_first[::-1]

        def on_done(count):
            tm.filter_tree_by_time()
            self.controls.update_total_items_count()
            elapsed = time.perf_counter() - self.load_start_time
            if count:
                text = f"Loaded {count:,} entries successfully.\n\n"
            else:
                text = "No items available to load.\n\n"
            self.msgbox.showinfo("Load Entries", text + f"Completed in {elapsed:.1f} seconds.")

        tm.load_in_background(prepare, on_done)
