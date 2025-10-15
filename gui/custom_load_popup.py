from customtkinter import CTkInputDialog

from gui.ctksimplebox import CTkMessageBox
from tree_manager import TreeManager


class CustomLoader:
    def __init__(self, root, controls, tree_manager: TreeManager, tracker):
        self.root = root
        self.controls = controls
        self.tree_manager = tree_manager
        self.tracker = tracker

        import tkinter.messagebox as messagebox
        self.msgbox = CTkMessageBox(root)
        messagebox.showinfo = self.msgbox.showinfo
        messagebox.showwarning = self.msgbox.showwarning
        messagebox.showerror = self.msgbox.showerror
        messagebox.askyesno = self.msgbox.askyesno

    def run(self):
        try:
            max_items = CTkInputDialog(
                text="Enter the number of entries to load:",
                title="Load Entries"

            ).get_input()

            if max_items is None:
                return  # user cancelled

            max_items = int(max_items)
            if max_items < 1:
                raise ValueError
        except Exception:
            self.msgbox.showerror("Invalid Input", "Please enter a valid number.")
            return

        # Clear existing tree
        self.tree_manager.clear_tree()

        # Load items from CSV
        all_items = self.tracker.load_all_parsed_items_from_csv()
        if not all_items:
            self.msgbox.showinfo("Load Entries", "No items available to load.")
            return

        # Reverse so newest first
        all_items = all_items[::-1]
        items_to_add = all_items[:max_items]

        # Insert in batches
        self._add_batch(items_to_add)

    def _add_batch(self, items, start_index=0, batch_size=200):
        end_index = min(start_index + batch_size, len(items))
        for i in range(start_index, end_index):
            self.tree_manager.add_item_to_tree(items[i])

        if end_index < len(items):
            self.root.after(15, self._add_batch, items, end_index, batch_size)
        else:
            self.tree_manager.reapply_row_formatting()
            self.tree_manager.filter_tree_by_time()
            self.controls.update_total_items_count()
            self.msgbox.showinfo(
                "Load Entries",
                f"Loaded {len(items)} entries successfully."
            )
