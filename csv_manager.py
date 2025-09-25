import csv
from pathlib import Path

from config import csv_file_path
from curio_tracker import log_message
from load_utils import load_csv


class CSVManager:
    def __init__(self, csv_path=None):
        self.csv_path = Path(csv_path or csv_file_path)

    def load_csv_dict(self):
        if not self.csv_path.exists():
            return []
        return load_csv(self.csv_path, as_dict=True, skip_header=False)

    def save_csv_dict(self, rows, fieldnames):
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def modify_record(self, record_number, item_name, updates=None, delete=False):
        updates = updates or {}

        if not self.csv_path.exists():
            log_message(f"[WARN] CSV not found: {self.csv_path}")
            return

        with self.csv_path.open("r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        if not lines:
            log_message(f"[WARN] CSV is empty: {self.csv_path}")
            return

        header = lines[0].split(",")
        try:
            rec_idx = header.index("Record #")
        except ValueError:
            log_message("[ERROR] CSV missing 'Record #' column")
            return

        updated_lines = [lines[0]]  # keep header
        updated = False

        for line in lines[1:]:
            cols = line.split(",")
            if rec_idx < len(cols) and cols[rec_idx].strip() == str(record_number):
                if delete:
                    updated = True
                    continue  # skip this row to delete
                elif updates:
                    for field_name, new_value in updates.items():
                        try:
                            field_idx = header.index(field_name)
                            if field_idx >= len(cols):
                                cols += [""] * (field_idx - len(cols) + 1)
                            cols[field_idx] = str(new_value)
                            log_message(f"[INFO] Record #{record_number}: '{item_name}' | {field_name} → {new_value}")
                        except ValueError:
                            log_message(f"[ERROR] CSV missing column '{field_name}'")
                    updated = True
            updated_lines.append(",".join(cols))

        if updated:
            with self.csv_path.open("w", encoding="utf-8") as f:
                f.write("\n".join(updated_lines) + "\n")
            action = "Deleted" if delete else "Updated"
            log_message(f"[INFO] {action} Record #{record_number}: '{item_name}' in CSV")
        else:
            action = "delete" if delete else "update"
            log_message(f"[INFO] No matching record found to {action} for Record #{record_number}: '{item_name}'")
