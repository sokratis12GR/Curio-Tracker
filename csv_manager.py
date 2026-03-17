import csv
from datetime import datetime
from pathlib import Path

from config import *
from data_manager import BaseDataManager
from load_utils import load_csv
from logger import log_message


class CSVManager(BaseDataManager):
    def __init__(self, file_path=None):
        base = Path(file_path or data_file_base)
        self.file_path = base.with_suffix(".csv")
        self.last_record_number = 0

    def load_dict(self):
        if not self.file_path.exists():
            return []
        return load_csv(self.file_path, as_dict=True, skip_header=False)

    def save_dict(self, root, rows, fieldnames):
        try:
            with self.file_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        except PermissionError as e:
            import toasts
            toasts.show_message(root, "!!! Unable to write to CSV (file may be open) !!!", duration=5000)
            log_message(f"[ERROR] PermissionError: {e}")
        except OSError as e:
            log_message(f"[ERROR] CSV write failed: {e}")

    def get_next_record_number(self, force=False):
        from settings import set_setting

        if force or self.last_record_number == 0:
            self.recalculate_record_number()

        if self.file_path.exists():
            rows = self.load_dict()
            existing_numbers = {int(row[csv_record_header]) for row in rows if row.get(csv_record_header, "").isdigit()}
            next_number = 1
            while next_number in existing_numbers:
                next_number += 1
            self.last_record_number = next_number
        else:
            self.last_record_number += 1

        set_setting("Application", "csv_current_row", self.last_record_number)
        return self.last_record_number

    def recalculate_record_number(self):
        from settings import set_setting

        max_record = 0
        if self.file_path.exists():
            try:
                with self.file_path.open("r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        val = row.get(csv_record_header, "0")
                        if str(val).isdigit():
                            max_record = max(max_record, int(val))
            except Exception as e:
                log_message(f"[ERROR] Could not read CSV for record number: {e}")

        self.last_record_number = max_record
        set_setting("Application", "csv_current_row", self.last_record_number)
        return self.last_record_number

    def modify_record(self, root, record_number, item_name, updates=None, delete=False):
        updates = updates or {}
        rows = self.load_dict()
        if not rows:
            log_message(f"[WARN] CSV is empty or missing: {self.file_path}")
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
            self.save_dict(root, rows, fieldnames=header)
            action = "Deleted" if delete else "Updated"
            log_message(f"[INFO] {action} Record #{record_number}: '{item_name}' in CSV")
        else:
            action = "delete" if delete else "update"
            log_message(f"[INFO] No matching record found to {action} for Record #{record_number}: '{item_name}'")

    def append_rows(self, rows: list[dict], root=None):
        if not rows:
            return

        write_header = not self.file_path.exists()
        fieldnames = list(rows[0].keys())

        if self.file_path.exists():
            try:
                with self.file_path.open("r", encoding="utf-8") as f:
                    reader = list(csv.DictReader(f))
                    if reader:
                        val = reader[-1].get(csv_record_header, "0")
                        if str(val).isdigit():
                            self.last_record_number = int(val)
            except Exception as e:
                log_message(f"[ERROR] Failed reading last record for append: {e}")

        for row in rows:
            if not row.get(csv_record_header):
                self.last_record_number += 1
                row[csv_record_header] = str(self.last_record_number)

        try:
            with self.file_path.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                writer.writerows(rows)
        except PermissionError as e:
            if root:
                import toasts
                toasts.show_message(root, "!!! Unable to write to CSV (file may be open) !!!", duration=5000)
            log_message(f"[ERROR] PermissionError: {e}")
        except OSError as e:
            log_message(f"[ERROR] CSV write failed: {e}")

        from settings import set_setting
        set_setting("Application", "csv_current_row", self.last_record_number)

    def upgrade_structure(self):
        rows = self.load_dict()
        if not rows:
            log_message(f"[INFO] File not found or empty: {self.file_path}")
            return

        changed = False

        for i, row in enumerate(rows, start=1):
            row[csv_record_header] = str(i)
            changed = True

        for i, row in enumerate(rows, start=1):

            if not str(row.get(csv_record_header, "")).isdigit():
                row[csv_record_header] = str(i)
                changed = True

            if not row.get(csv_picked_header):
                row[csv_picked_header] = "False"
                changed = True

        if changed:
            self.save_dict(None, rows, fieldnames=list(rows[0].keys()))
            log_message(f"[INFO] CSV structure upgraded → {self.file_path}")

    def duplicate_latest(self, root):
        rows = self.load_dict()
        if not rows:
            log_message("[ERROR] CSV file has no entries to duplicate.")
            return None

        last_row = rows[-1].copy()

        # Ensure last_record_number is current
        self.recalculate_record_number()

        # Assign next unique number
        record_number = self.get_next_record_number()
        last_row[csv_record_header] = str(record_number)

        if csv_time_header in last_row:
            last_row[csv_time_header] = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Append and save
        rows.append(last_row)
        self.save_dict(root, rows, fieldnames=list(last_row.keys()))

        log_message(f"[INFO] Duplicated latest CSV entry → Record {record_number}")
        return last_row

    def ensure_data_file(self):
        if not self.file_path.exists():
            headers = [
                "Record #", "League", "Logged By", "Blueprint Type", "Area Level",
                "Trinket", "Replacement", "Replica", "Experimented Base Type",
                "Weapon Enchantment", "Armor Enchantment", "Scarab", "Currency",
                "Stack Size", "Variant", "Flag?", "Time", "Picked", "Owned"
            ]
            with open(self.file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()