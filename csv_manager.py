import csv
from datetime import datetime
from pathlib import Path

import toasts
from config import *
from load_utils import load_csv
from logger import log_message


class CSVManager:
    def __init__(self, csv_path=None):
        self.csv_path = Path(csv_path or csv_file_path)
        self.last_record_number = 0

    def load_csv_dict(self):
        if not self.csv_path.exists():
            return []
        return load_csv(self.csv_path, as_dict=True, skip_header=False)

    def save_csv_dict(self, root, rows, fieldnames):
        try:
            with self.csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except PermissionError as e:
            toasts.show_message(root, "!!! Unable to write to CSV (file may be open) !!!", duration=5000)
            log_message(f"[ERROR] PermissionError: {e}")
        except OSError as e:
            log_message(f"[ERROR] CSV write failed: {e}")

    def get_next_record_number(self):
        from settings import get_setting, set_setting

        cached_last = int(get_setting("Application", "current_row", default=0) or 0)
        highest_in_csv = 0

        if self.csv_path.exists():
            try:
                with self.csv_path.open("r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    if len(rows) > 1:
                        last_row = rows[-1]
                        highest_in_csv = int(last_row[0]) if last_row[0].isdigit() else 0
            except Exception as e:
                log_message(f"[ERROR] Could not read CSV for record number: {e}")

        # Only trust the cached value if it matches the CSV’s highest value
        if self.last_record_number == 0:
            if cached_last == highest_in_csv:
                self.last_record_number = cached_last
            else:
                self.last_record_number = highest_in_csv

        # Increment and save
        self.last_record_number += 1
        set_setting("Application", "current_row", self.last_record_number)

        return self.last_record_number

    def recalculate_record_number(self):
        from settings import set_setting

        self.last_record_number = 0

        if self.last_record_number == 0 and self.csv_path.exists():
            try:
                with self.csv_path.open("r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                    if len(rows) > 1:
                        last_row = rows[-1]
                        self.last_record_number = int(last_row[0]) if last_row[0].isdigit() else 0
            except Exception as e:
                log_message(f"[ERROR] Could not read CSV for record number: {e}")
                self.last_record_number = 0

        set_setting("Application", "current_row", self.last_record_number)

        return self.last_record_number

    def modify_record(self, root, record_number, item_name, updates=None, delete=False):
        updates = updates or {}
        rows = self.load_csv_dict()
        if not rows:
            log_message(f"[WARN] CSV is empty or missing: {self.csv_path}")
            return

        header = list(rows[0].keys())
        updated = False

        for row in rows:
            if str(row.get(csv_record_header, "")) == str(record_number):
                if delete:
                    rows.remove(row)
                    updated = True
                    break
                for field_name, new_value in updates.items():
                    if field_name in header:
                        row[field_name] = str(new_value)
                        log_message(f"[INFO] Record #{record_number}: '{item_name}' | {field_name} → {new_value}")
                        updated = True
                    else:
                        log_message(f"[ERROR] CSV missing column '{field_name}'")

        if updated:
            self.save_csv_dict(root, rows, fieldnames=header)
            action = "Deleted" if delete else "Updated"
            log_message(f"[INFO] {action} Record #{record_number}: '{item_name}' in CSV")
        else:
            action = "delete" if delete else "update"
            log_message(f"[INFO] No matching record found to {action} for Record #{record_number}: '{item_name}'")

    def upgrade_with_record_numbers(self):
        rows = self.load_csv_dict()
        if not rows:
            log_message(f"[INFO] File not found or empty: {self.csv_path}")
            return

        if csv_record_header not in rows[0]:
            for i, row in enumerate(rows, start=1):
                row[csv_record_header] = str(i)
        else:
            for i, row in enumerate(rows, start=1):
                row[csv_record_header] = str(i)

        self.save_csv_dict(None, rows, fieldnames=list(rows[0].keys()))
        log_message(f"[INFO] Upgraded CSV with Record # column → {self.csv_path}")

    def upgrade_with_picked_column(self):
        rows = self.load_csv_dict()
        if not rows:
            return

        if csv_picked_header not in rows[0]:
            for row in rows:
                row[csv_picked_header] = "False"
        else:
            for row in rows:
                if not row.get(csv_picked_header):
                    row[csv_picked_header] = "False"

        self.save_csv_dict(None, rows, fieldnames=list(rows[0].keys()))
        log_message(f"[INFO] Added/Filled '{csv_picked_header}' column")

    def duplicate_latest(self, root):
        rows = self.load_csv_dict()
        if not rows:
            log_message("[ERROR] CSV file has no entries to duplicate.")
            return None

        last_row = rows[-1].copy()
        record_number = self.get_next_record_number()
        last_row[csv_record_header] = str(record_number)

        if csv_time_header in last_row:
            last_row[csv_time_header] = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        rows.append(last_row)
        self.save_csv_dict(root, rows, fieldnames=list(last_row.keys()))

        log_message(f"[INFO] Duplicated latest entry → Record {record_number}")

        return last_row
