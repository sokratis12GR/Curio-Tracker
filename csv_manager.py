import csv
from datetime import datetime
from pathlib import Path

from config import *
from data_manager import BaseDataManager, max_record_number, shift_records_after_delete
from load_utils import load_csv
from logger import log_message


class CSVManager(BaseDataManager):
    def __init__(self, file_path=None):
        base = Path(file_path or data_file_base)
        self.file_path = base.with_suffix(".csv")
        self.last_record_number = 0
        # (mtime, size) of the file as last read/written by this manager.
        # If it differs, another writer touched the file and the cached
        # last_record_number must be re-read.
        self._known_file_state = None

    def _file_state(self):
        try:
            st = self.file_path.stat()
            return st.st_mtime_ns, st.st_size
        except OSError:
            return None

    def _remember_file_state(self):
        self._known_file_state = self._file_state()

    def _set_last_record_number(self, value):
        from settings import set_setting

        self.last_record_number = value
        set_setting("Application", "csv_current_row", value)

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
            self._remember_file_state()
        except PermissionError as e:
            import toasts
            toasts.show_message(root, "!!! Unable to write to CSV (file may be open) !!!", duration=5000)
            log_message(f"[ERROR] PermissionError: {e}")
        except OSError as e:
            log_message(f"[ERROR] CSV write failed: {e}")

    #############################################################
    # Record numbers are kept continuous (1..N): deletions      #
    # shift later records down, so the next number is always    #
    # highest + 1. This only peeks; callers that write a record #
    # update last_record_number afterwards.                     #
    #############################################################
    def get_next_record_number(self, force=False):
        if (
                force
                or self.last_record_number == 0
                or self._file_state() != self._known_file_state
        ):
            self.recalculate_record_number()

        return self.last_record_number + 1

    def get_record_count(self):
        # Counts lines without parsing, so it stays fast on large files.
        # Quoted values containing newlines would over-count; this is
        # only used for load estimates.
        if not self.file_path.exists():
            return 0
        lines = 0
        last = b"\n"
        with self.file_path.open("rb") as f:
            while chunk := f.read(1 << 20):
                lines += chunk.count(b"\n")
                last = chunk[-1:]
        if last != b"\n":
            lines += 1  # final line without a trailing newline
        return max(lines - 1, 0)  # minus the header

    def recalculate_record_number(self):
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

        self._set_last_record_number(max_record)
        self._remember_file_state()
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
                    shift_records_after_delete(rows, record_number)
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
            if delete:
                self._set_last_record_number(max_record_number(rows))
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

        numbered = [str(row.get(csv_record_header, "")) for row in rows]

        if not all(n.isdigit() for n in numbered):
            # Number any unnumbered rows after the current highest record.
            next_number = self.get_next_record_number()
            for row in rows:
                if not str(row.get(csv_record_header, "")).isdigit():
                    row[csv_record_header] = str(next_number)
                    next_number += 1

        try:
            with self.file_path.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                writer.writerows(rows)
            self._remember_file_state()
        except PermissionError as e:
            if root:
                import toasts
                toasts.show_message(root, "!!! Unable to write to CSV (file may be open) !!!", duration=5000)
            log_message(f"[ERROR] PermissionError: {e}")
            return
        except OSError as e:
            log_message(f"[ERROR] CSV write failed: {e}")
            return

        self._set_last_record_number(
            max(self.last_record_number, max_record_number(rows))
        )

    def upgrade_structure(self):
        rows = self.load_dict()

        if not rows:
            log_message(f"[INFO] File not found or empty: {self.file_path}")
            return

        changed = False

        required_headers = self.get_csv_headers()

        # Existing headers
        # existing_headers = list(rows[0].keys())
        existing_headers = [
            h for h in rows[0].keys()
            if h is not None
        ]

        for row in rows:
            if None in row:
                row.pop(None)
                changed = True

        # Add missing columns
        for header in required_headers:
            if header not in existing_headers:
                existing_headers.append(header)
                changed = True

                # Default values for new columns
                for row in rows:
                    if header == csv_enchantment_header:
                        row[header] = "None"
                    elif header == csv_picked_header:
                        row[header] = "False"
                    elif header == csv_owned_header:
                        row[header] = "False"
                    else:
                        row[header] = ""

        # Fix record numbers
        for i, row in enumerate(rows, start=1):
            if row.get(csv_record_header) != str(i):
                row[csv_record_header] = str(i)
                changed = True

        # Ensure required defaults
        for row in rows:
            if not row.get(csv_picked_header):
                row[csv_picked_header] = "False"
                changed = True

            if not row.get(csv_owned_header):
                row[csv_owned_header] = "False"
                changed = True

            if not row.get(csv_enchantment_header):
                row[csv_enchantment_header] = "None"
                changed = True

        if changed:
            self.save_dict(
                None,
                rows,
                fieldnames=existing_headers
            )

            log_message(
                f"[INFO] CSV structure upgraded → {self.file_path}"
            )
        else:
            self._remember_file_state()

        # Rows are now numbered 1..N.
        self._set_last_record_number(len(rows))

    def duplicate_latest(self, root):
        rows = self.load_dict()
        if not rows:
            log_message("[ERROR] CSV file has no entries to duplicate.")
            return None

        last_row = rows[-1].copy()

        # Assign next number from the rows just loaded
        record_number = max_record_number(rows) + 1
        last_row[csv_record_header] = str(record_number)

        if csv_time_header in last_row:
            last_row[csv_time_header] = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Append and save
        rows.append(last_row)
        self.save_dict(root, rows, fieldnames=list(last_row.keys()))
        self._set_last_record_number(record_number)

        log_message(f"[INFO] Duplicated latest CSV entry → Record {record_number}")
        return last_row

    def ensure_data_file(self):
        if not self.file_path.exists():
            with self.file_path.open(
                    "w",
                    newline="",
                    encoding="utf-8"
            ) as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=self.get_csv_headers()
                )
                writer.writeheader()
            self._set_last_record_number(0)
            self._remember_file_state()

    def get_csv_headers(self):
        return [
            csv_record_header,
            csv_league_header,
            csv_loggedby_header,
            csv_blueprint_header,
            csv_area_level_header,
            csv_trinket_header,
            csv_replacement_header,
            csv_replica_header,
            csv_experimented_header,
            csv_weapon_enchant_header,
            csv_armor_enchant_header,
            csv_scarab_header,
            csv_currency_header,
            csv_stack_size_header,
            csv_variant_header,
            csv_flag_header,
            csv_time_header,
            csv_picked_header,
            csv_owned_header,
            csv_enchantment_header,
        ]