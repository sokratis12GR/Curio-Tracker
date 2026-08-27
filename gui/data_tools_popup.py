import csv
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from customtkinter import *

import config
from csv_manager import CSVManager
from csv_to_json import csv_to_nested_json
from gui.ctksimplebox import CTkMessageBox
from win_utils import center_window_on_parent


class DataToolsPopup:
    def __init__(self, parent, tree_manager):
        self.parent = parent
        self.tree_manager = tree_manager

        self.popup = CTkToplevel(parent)
        self.popup.title("Data Tools")
        self.popup.geometry("450x390")
        self.popup.resizable(False, False)
        self.popup.transient(parent.winfo_toplevel())
        self.msgbox = CTkMessageBox(self.popup)

        self.data_file = config.data_file_base + ".csv"
        self.last_export_path = None

        self._setup_ui()

        center_window_on_parent(
            self.popup,
            self.parent
        )

        self.popup.grab_set()
        self.popup.focus_force()

    def _setup_ui(self):
        self.popup.grid_columnconfigure(0, weight=1)

        title = CTkLabel(
            self.popup,
            text="Data Tools",
            font=CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 5))

        description = CTkLabel(
            self.popup,
            text="Import, merge and save external data files.",
            anchor="w"
        )
        description.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 15))

        merge_btn = CTkButton(
            self.popup,
            text="Merge External matches.csv",
            command=self.merge_external_file
        )
        merge_btn.grid(row=2, column=0, sticky="ew", padx=20, pady=5)

        save_btn = CTkButton(
            self.popup,
            text="Export to CSV",
            command=self.export_to_csv
        )
        save_btn.grid(row=3, column=0, sticky="ew", padx=20, pady=5)

        export_json_btn = CTkButton(
            self.popup,
            text="Export to JSON",
            command=self.export_to_json
        )
        export_json_btn.grid(row=4, column=0, sticky="ew", padx=20, pady=5)

        self.export_status = CTkLabel(
            self.popup,
            text="",
            anchor="w",
            justify="left",
            wraplength=410
        )
        self.export_status.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=20,
            pady=(5, 0)
        )

        self.show_location_btn = CTkButton(
            self.popup,
            text="Show Location",
            command=self.show_export_location
        )

        close_btn = CTkButton(
            self.popup,
            text="Close",
            command=self.popup.destroy
        )
        close_btn.grid(row=7, column=0, sticky="ew", padx=20, pady=(20, 10))

    def merge_external_file(self):
        external_file = filedialog.askopenfilename(
            parent=self.popup,
            title="Select External matches.csv",
            filetypes=[("CSV Files", "*.csv")]
        )

        if not external_file:
            return

        try:
            external_headers, external_rows = self._read_csv(external_file)

            if os.path.exists(self.data_file):
                current_headers, current_rows = self._read_csv(self.data_file)
            else:
                current_headers = external_headers
                current_rows = []

            structure_upgraded = False

            if set(external_headers) != set(current_headers):
                missing_from_current = [
                    header for header in external_headers
                    if header not in current_headers
                ]

                missing_from_external = [
                    header for header in current_headers
                    if header not in external_headers
                ]

                message = (
                    "The external CSV columns do not match the current data file.\n\n"
                )

                if missing_from_current:
                    message += (
                        "New columns found in the external file:\n"
                        f"{', '.join(missing_from_current)}\n\n"
                    )

                if missing_from_external:
                    message += (
                        "Columns missing from the external file:\n"
                        f"{', '.join(missing_from_external)}\n\n"
                    )

                message += (
                    "Would you like to automatically upgrade the current "
                    "matches.csv structure and attempt the merge?\n\n"
                    "A backup will be created before any changes are made."
                )

                upgrade = self.msgbox.askyesno(
                    "Upgrade CSV Structure",
                    message,
                )

                if not upgrade:
                    return

                current_headers, current_rows, external_rows = self._upgrade_headers(
                    current_headers,
                    current_rows,
                    external_headers,
                    external_rows
                )

                structure_upgraded = True

            external_rows = [
                {header: row.get(header, "") for header in current_headers}
                for row in external_rows
            ]

            current_rows = [
                {header: row.get(header, "") for header in current_headers}
                for row in current_rows
            ]

            # External data is placed on top of the old data
            merged_rows = external_rows + current_rows

            backup_file = self._create_backup()

            with open(self.data_file, "w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=current_headers)
                writer.writeheader()
                writer.writerows(merged_rows)

            self._upgrade_current_file()

            # self._reload_data()

            upgrade_text = ""

            if structure_upgraded:
                upgrade_text = (
                    "\n\nThe current matches.csv file was upgraded to the "
                    "combined structure."
                )

            self.msgbox.showinfo(
                "Merge Complete",
                f"Added {len(external_rows)} external rows.\n\n"
                f"Total rows: {len(merged_rows)}\n"
                f"Backup: {backup_file}"
                f"{upgrade_text}\n\n"
                f"Record numbers and required columns were recalculated.\n\n"
                f"Please restart the application for all changes to function properly.",
            )

        except Exception as error:
            self.msgbox.showerror(
                "Merge Failed",
                str(error),
            )

    def export_to_csv(self):
        source_file = Path(self.data_file)

        if not source_file.exists():
            self._set_export_result(
                error=f"Could not find:\n{source_file}"
            )
            return

        save_path = filedialog.asksaveasfilename(
            parent=self.popup,
            title="Export to CSV",
            defaultextension=".csv",
            initialfile="matches_external.csv",
            filetypes=[("CSV Files", "*.csv")]
        )

        if not save_path:
            return

        try:
            shutil.copy2(
                source_file,
                save_path
            )

            self._set_export_result(
                path=save_path,
                export_type="CSV"
            )

        except Exception as error:
            self._set_export_result(
                error=error
            )

    def _read_csv(self, file_path):
        with open(file_path, "r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            if not reader.fieldnames:
                raise ValueError("The selected CSV does not contain headers.")

            headers = [
                header.strip()
                for header in reader.fieldnames
                if header is not None
            ]

            rows = []

            for row in reader:
                if None in row:
                    row.pop(None)

                cleaned_row = {
                    header.strip(): value
                    for header, value in row.items()
                    if header is not None
                }

                rows.append(cleaned_row)

        return headers, rows

    def _upgrade_headers(
            self,
            current_headers,
            current_rows,
            external_headers,
            external_rows
    ):
        upgraded_headers = list(current_headers)

        # Add new external columns to the current structure
        for header in external_headers:
            if header not in upgraded_headers:
                upgraded_headers.append(header)

        # Fill missing values in the old data
        for row in current_rows:
            for header in upgraded_headers:
                if header not in row:
                    row[header] = self._get_default_value(header)

        # Fill missing values in the external data
        for row in external_rows:
            for header in upgraded_headers:
                if header not in row:
                    row[header] = self._get_default_value(header)

        return upgraded_headers, current_rows, external_rows

    def _get_default_value(self, header):
        if header == getattr(config, "csv_enchantment_header", None):
            return "None"

        if header == getattr(config, "csv_picked_header", None):
            return "False"

        if header == getattr(config, "csv_owned_header", None):
            return "False"

        return ""

    def _upgrade_current_file(self):
        csv_manager = CSVManager(config.data_file_base)
        csv_manager.upgrade_structure()
        csv_manager.recalculate_record_number()

    def _create_backup(self):
        if not os.path.exists(self.data_file):
            return "No previous file"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name, file_ext = os.path.splitext(self.data_file)
        backup_file = f"{file_name}_backup_{timestamp}{file_ext}"

        shutil.copy2(self.data_file, backup_file)

        return backup_file

    def _reload_data(self):
        from curio_tracker import reload_data_manager

        data_manager = reload_data_manager()
        self.tree_manager.switch_data_manager(data_manager)

    def _set_export_result(self, path=None, export_type=None, error=None):
        if error is not None:
            self.last_export_path = None

            self.export_status.configure(
                text=f"Export failed: {error}"
            )

            self.show_location_btn.grid_remove()

            self.msgbox.showerror(
                "Export Failed",
                str(error)
            )
            return

        path = Path(path)
        self.last_export_path = path

        self.export_status.configure(
            text=(
                f"{export_type} export complete.\n"
                f"{path}"
            )
        )

        self.show_location_btn.grid(
            row=6,
            column=0,
            sticky="ew",
            padx=20,
            pady=(8, 0)
        )

        self.msgbox.showinfo(
            "Export Complete",
            f"{export_type} export completed successfully.\n\n"
            f"Location:\n{path}"
        )

    def export_to_json(self):
        csv_file = Path(
            config.data_file_base + ".csv"
        )

        if not csv_file.exists():
            self._set_export_result(
                error=f"Could not find:\n{csv_file}"
            )
            return

        json_file = csv_file.with_suffix(".json")

        try:
            csv_to_nested_json(
                csv_file,
                json_file
            )

            self._set_export_result(
                path=json_file,
                export_type="JSON"
            )

        except Exception as error:
            self._set_export_result(
                error=error
            )

    def show_export_location(self):
        if not self.last_export_path:
            return

        path = Path(self.last_export_path)

        if not path.exists():
            self.msgbox.showerror(
                "File Not Found",
                f"The exported file could not be found:\n{path}"
            )
            return

        try:
            if sys.platform == "win32":
                subprocess.Popen([
                    "explorer",
                    "/select,",
                    str(path)
                ])

            elif sys.platform == "darwin":
                subprocess.Popen([
                    "open",
                    "-R",
                    str(path)
                ])

            else:
                subprocess.Popen([
                    "xdg-open",
                    str(path.parent)
                ])

        except Exception as error:
            self.msgbox.showerror(
                "Open Location Failed",
                str(error)
            )


def show_data_tools_popup(parent, tree_manager):
    DataToolsPopup(parent, tree_manager)
