import os
import shutil
import sys
import tempfile
import time
import tkinter as tk
import unittest
from tkinter import ttk
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as c
from csv_manager import CSVManager
from json_manager import JSONManager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_record_numbering import make_row


class RecordCountTests(unittest.TestCase):
    def setUp(self):
        self._patch = mock.patch("settings.set_setting", lambda *a, **k: None)
        self._patch.start()
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def _check(self, mgr):
        self.assertEqual(mgr.get_record_count(), 0)  # missing file
        mgr.ensure_data_file()
        self.assertEqual(mgr.get_record_count(), 0)  # header only
        mgr.append_rows([make_row(i, f"N{i}") for i in range(1, 251)])
        self.assertEqual(mgr.get_record_count(), 250)

    def test_csv(self):
        self._check(CSVManager(os.path.join(self.dir, "m")))

    def test_csv_without_trailing_newline(self):
        mgr = CSVManager(os.path.join(self.dir, "m"))
        mgr.ensure_data_file()
        mgr.append_rows([make_row(1, "A"), make_row(2, "B")])
        data = mgr.file_path.read_bytes().rstrip(b"\r\n")
        mgr.file_path.write_bytes(data)
        self.assertEqual(mgr.get_record_count(), 2)

    def test_json(self):
        self._check(JSONManager(os.path.join(self.dir, "m")))


def make_item(record, name, timestamp="2026-11-10_12-00-00"):
    return SimpleNamespace(
        record_number=record, time=timestamp, type="Currency",
        itemName=SimpleNamespace(lines=[name]), chaos_value="", picked=False,
    )


class TreeLoadingTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk not available")
        self.root.withdraw()
        self._patch = mock.patch("settings.set_setting", lambda *a, **k: None)
        self._patch.start()
        from tree_manager import TreeManager
        self.tree = ttk.Treeview(self.root, columns=[col["id"] for col in c.TREE_COLUMNS])
        self.tm = TreeManager(self.root, self.tree, "DARK")
        self.tm.msgbox = mock.Mock()

    def tearDown(self):
        self._patch.stop()
        self.root.destroy()

    def _pump_until(self, predicate, timeout=10):
        end = time.time() + timeout
        while not predicate() and time.time() < end:
            self.root.update()
        self.assertTrue(predicate(), "background load did not finish")

    def _rows(self):
        return [self.tree.item(i, "values") for i in self.tree.get_children()]

    def test_background_rows_match_single_insert(self):
        items = [make_item(str(n), f"Item {n}") for n in range(1, 6)]

        for item in items:
            self.tm.add_item_to_tree(item, insert_at_top=False)
        expected = self._rows()

        done = []
        self.tm.load_in_background(lambda: list(items), done.append)
        self._pump_until(lambda: done)

        self.assertEqual(done, [5])
        self.assertEqual(self._rows(), expected)
        tags = [self.tree.item(i, "tags")[0] for i in self.tree.get_children()]
        self.assertEqual(tags, ["odd", "even", "odd", "even", "odd"])

    def test_load_all_orders_by_record_and_dedupes(self):
        items = [make_item("2", "B", "2026-11-10_12-00-02"),
                 make_item("1", "A", "2026-11-10_12-00-01"),
                 make_item("1", "A second column", "2026-11-10_12-00-01"),
                 make_item("3", "C", "2026-11-10_12-00-03")]
        tracker = SimpleNamespace(load_all_parsed_items=lambda mgr: list(items))
        done = []
        self.tm.load_all_items_threaded(tracker, post_callback=lambda: done.append(1),
                                        ask_confirmation=False)
        self._pump_until(lambda: done)

        record_col = self.tm.columns.index("record")
        item_col = self.tm.columns.index("item")
        rows = self._rows()
        # The record column defaults to sort_reverse=True: newest first.
        self.assertEqual([str(r[record_col]) for r in rows], ["3", "2", "1"])
        self.assertNotIn("A second column", [r[item_col] for r in rows])
        self.assertFalse(self.tm.sort_reverse["record"])  # toggled like sort_tree

        # Same result as the old path: insert, then sort_tree("record").
        self.tm.clear_tree()
        self.tm.sort_reverse["record"] = True
        for item in self.tm._dedupe_by_record(sorted(items, key=lambda i: i.time, reverse=True)):
            self.tm.add_item_to_tree(item, insert_at_top=False)
        self.tm.sort_tree("record")
        self.assertEqual(self._rows(), rows)

    def test_totals_count_values_picked_and_skip_deleted(self):
        priced = make_item("1", "A")
        priced.chaos_value = "10"
        picked = make_item("2", "B")
        picked.chaos_value = "5"
        picked.picked = True
        free = make_item("3", "C")
        gone = make_item("4", "D")
        gone.chaos_value = "100"
        for item in (priced, picked, free, gone):
            self.tm.add_item_to_tree(item)
        # Removed from the widget but still tracked: must not count.
        self.tree.delete(self.tm.get_iid_for_record(4))

        total_chaos, _, picked_chaos, _ = self.tm.calculate_totals()
        self.assertEqual(total_chaos, 15.0)
        self.assertEqual(picked_chaos, 5.0)

    def _tags(self):
        return [self.tree.item(i, "tags")[0] for i in self.tree.get_children()]

    def test_cell_edit_updates_cached_totals(self):
        item = make_item("1", "A")
        item.chaos_value = "10"
        self.tm.add_item_to_tree(item)
        self.assertEqual(self.tm.calculate_totals()[2], 0.0)
        # Same write the picked toggle in editing.py does.
        self.tree.set(self.tm.get_iid_for_record(1), "picked", "☑")
        self.assertEqual(self.tm.calculate_totals()[2], 10.0)

    def test_search_uses_fresh_text_after_edit(self):
        for n, name in enumerate(["Alpha", "Beta", "Gamma"], start=1):
            self.tm.add_item_to_tree(make_item(str(n), name))
        self.tm.search_var.set("beta")
        self.assertEqual(len(self.tree.get_children()), 1)

        iid = self.tm.get_iid_for_record(3)
        self.tree.set(iid, "item", "Beta Two")
        self.tm.apply_filters()
        self.assertEqual(len(self.tree.get_children()), 2)
        self.assertEqual(self._tags(), ["odd", "even"])

        self.tm.search_var.set("")
        self.assertEqual(len(self.tree.get_children()), 3)

    def test_clear_removes_rows_hidden_by_filter(self):
        for n in range(1, 4):
            self.tm.add_item_to_tree(make_item(str(n), f"Name{n}"))
        self.tm.search_var.set("name2")
        self.tm.clear_tree()
        self.tm.search_var.set("")
        for n in range(1, 4):
            self.assertFalse(self.tree.exists(f"row_{n}"))

    def test_capture_insert_keeps_stripes_alternating(self):
        for n in range(1, 6):
            self.tm.add_item_to_tree(make_item(str(n), f"I{n}"))
            tags = self._tags()
            self.assertTrue(all(a != b for a, b in zip(tags, tags[1:])), tags)

    def test_sort_keeps_filtered_rows_hidden(self):
        for n, name in enumerate(["Alpha", "Beta", "Alps"], start=1):
            self.tm.add_item_to_tree(make_item(str(n), name))
        self.tm.search_var.set("alp")
        self.tm.sort_tree("record")
        item_col = self.tm.columns.index("item")
        names = sorted(self.tree.item(i, "values")[item_col] for i in self.tree.get_children())
        self.assertEqual(len(names), 2)
        self.assertTrue(all("Alp" in n for n in names), names)
        self.assertEqual(self._tags(), ["odd", "even"])

    def test_record_and_time_sort_match_cell_values(self):
        items = [make_item("3", "C", "2026-11-10_12-00-01"),
                 make_item("10", "J", "2026-11-10_12-00-03"),
                 make_item(None, "No number", "2026-11-10_12-00-02"),
                 make_item("1", "A", "")]
        for item in items:
            self.tm.add_item_to_tree(item, insert_at_top=False)
        item_col = self.tm.columns.index("item")

        def names():
            return [self.tree.item(i, "values")[item_col] for i in self.tree.get_children()]

        self.tm.sort_reverse["record"] = False
        self.tm.sort_tree("record")
        self.assertEqual(names(), ["A", "C", "J", "No number"])  # numeric, blanks last
        self.tm.sort_tree("record")
        self.assertEqual(names(), ["J", "C", "A", "No number"])

        self.tm.sort_reverse["time"] = False
        self.tm.sort_tree("time")
        self.assertEqual(names(), ["C", "No number", "J", "A"])  # unknown time last

    def test_clear_stops_running_load(self):
        items = [make_item(str(n), f"I{n}") for n in range(1, 3001)]
        done = []
        self.tm.load_in_background(lambda: items, done.append)
        self._pump_until(lambda: self.tree.get_children())
        self.tm.clear_tree()
        for _ in range(200):
            self.root.update()
        self.assertEqual(done, [])
        self.assertEqual(self.tree.get_children(), ())


if __name__ == "__main__":
    unittest.main()
