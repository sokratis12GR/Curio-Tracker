import os
import shutil
import sys
import tempfile
import tkinter as tk
import unittest
from tkinter import ttk
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as c
from csv_manager import CSVManager
from json_manager import JSONManager

H = c.csv_record_header


def make_row(number, name):
    # Full column set in file order, like the rows write_entry builds.
    row = {header: "" for header in CSVManager().get_csv_headers()}
    row.update({
        H: number,
        c.csv_league_header: "3.26",
        c.csv_loggedby_header: "Tester#1234",
        c.csv_blueprint_header: "Repository",
        c.csv_area_level_header: "83",
        c.csv_replica_header: name,
        c.csv_time_header: "2026-11-10_12-00-00",
        c.csv_picked_header: False,
    })
    return row


class _ManagerCases:
    """Shared numbering cases; subclasses provide make_manager()."""

    def setUp(self):
        self._settings_patch = mock.patch("settings.set_setting", lambda *a, **k: None)
        self._settings_patch.start()
        self.dir = tempfile.mkdtemp()
        self.mgr = self.make_manager(os.path.join(self.dir, "matches"))

    def tearDown(self):
        self._settings_patch.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def capture(self, *names):
        """Mirrors write_entry: consecutive numbers from get_next_record_number."""
        next_number = self.mgr.get_next_record_number()
        rows = []
        for name in names:
            rows.append(make_row(next_number, name))
            next_number += 1
        self.mgr.ensure_data_file()
        self.mgr.append_rows(rows)
        self.mgr.last_record_number = next_number - 1

    def numbers_by_name(self):
        rows = self.mgr.load_dict()
        return {row[c.csv_replica_header]: int(row[H]) for row in rows}

    def delete(self, number):
        self.mgr.modify_record(None, number, "x", delete=True)

    def assert_continuous(self):
        numbers = sorted(int(r[H]) for r in self.mgr.load_dict())
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))

    def test_sequential_and_multi_item_captures(self):
        self.capture("A")
        self.capture("B", "C")
        self.assertEqual(self.numbers_by_name(), {"A": 1, "B": 2, "C": 3})
        self.assertEqual(self.mgr.get_next_record_number(), 4)

    def test_delete_middle_shifts_later_records(self):
        self.capture("A", "B", "C", "D")
        self.delete(2)
        self.assertEqual(self.numbers_by_name(), {"A": 1, "C": 2, "D": 3})
        self.assertEqual(self.mgr.get_next_record_number(), 4)

    def test_multi_item_capture_after_delete_has_no_collisions(self):
        self.capture("A", "B", "C", "D")
        self.delete(2)
        self.capture("E", "F")
        self.assertEqual(
            self.numbers_by_name(),
            {"A": 1, "C": 2, "D": 3, "E": 4, "F": 5},
        )
        self.assert_continuous()

    def test_delete_last(self):
        self.capture("A", "B", "C")
        self.delete(3)
        self.capture("D")
        self.assertEqual(self.numbers_by_name(), {"A": 1, "B": 2, "D": 3})

    def test_consecutive_deletes(self):
        # Like a multi-select delete: each delete uses the current number.
        self.capture("A", "B", "C", "D", "E")
        self.delete(2)  # B
        self.delete(2)  # C, which had shifted down to 2
        self.assertEqual(self.numbers_by_name(), {"A": 1, "D": 2, "E": 3})
        self.assert_continuous()

    def test_duplicate_latest_uses_next_number(self):
        self.capture("A", "B")
        self.delete(1)
        row = self.mgr.duplicate_latest(None)
        self.assertEqual(int(row[H]), 2)
        self.assertEqual(self.mgr.get_next_record_number(), 3)

    def test_upgrade_closes_existing_gaps(self):
        self.capture("A", "B", "C")
        rows = self.mgr.load_dict()
        rows[1][H] = "7"  # simulate a gap left by an older version
        rows[2][H] = "9"
        self.mgr.save_dict(None, rows, fieldnames=list(rows[0].keys()))
        self.mgr.upgrade_structure()
        self.assert_continuous()
        self.assertEqual(self.mgr.get_next_record_number(), 4)


class CSVRecordNumberingTests(_ManagerCases, unittest.TestCase):
    def make_manager(self, base):
        return CSVManager(base)

    def test_external_change_is_detected(self):
        self.capture("A", "B")
        self.assertEqual(self.mgr.get_next_record_number(), 3)
        # Another writer (e.g. the merge tool) appends to the file.
        other = CSVManager(os.path.join(self.dir, "matches"))
        other.append_rows([make_row(3, "X")])
        self.assertEqual(self.mgr.get_next_record_number(), 4)


class JSONRecordNumberingTests(_ManagerCases, unittest.TestCase):
    def make_manager(self, base):
        return JSONManager(base)


class TreeShiftTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("Tk not available")
        self.root.withdraw()
        self.tree = ttk.Treeview(self.root, columns=("item", "record"))

    def tearDown(self):
        self.root.destroy()

    def test_shift_updates_items_cells_and_lookup(self):
        from tree_manager import TreeManager

        items = {}
        record_to_iid = {}
        for number, record in enumerate(["1", "2", "3", "4"], start=1):
            iid = f"row_{number}"
            items[iid] = SimpleNamespace(record_number=record)
            record_to_iid[number] = iid
            self.tree.insert("", "end", iid=iid, values=(f"item{number}", number))

        tm = SimpleNamespace(
            record_to_iid=record_to_iid,
            csv_row_map=items,
            columns=["item", "record"],
            tree=self.tree,
        )

        self.tree.delete("row_2")
        TreeManager._shift_records_after_delete(tm, "2")

        self.assertEqual(tm.record_to_iid, {1: "row_1", 2: "row_3", 3: "row_4"})
        self.assertEqual(items["row_3"].record_number, "2")
        self.assertEqual(items["row_4"].record_number, "3")
        self.assertEqual(items["row_1"].record_number, "1")
        self.assertEqual(str(self.tree.set("row_4", "record")), "3")


if __name__ == "__main__":
    unittest.main()
