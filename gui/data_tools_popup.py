import csv
import shutil
from datetime import datetime
from tkinter import messagebox

from customtkinter import *

import config
from csv_manager import CSVManager


class DataToolsPopup:
    def __init__(self, parent, tree_manager):
        self.parent = parent
        self.tree_manager = tree_manager

        self.popup = CTkToplevel(parent)
        self.popup.title("Data Tools")
        self.popup.geometry("450x260")
        self.popup.resizable(False, False)
        self.popup.transient(parent.winfo_toplevel())
        self.popup.grab_set()

        self.data_file = config.data_file_base + ".csv"

        self._setup_ui()
        self._center_popup()

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
            text="Save External Data",
            command=self.save_external_file
        )
        save_btn.grid(row=3, column=0, sticky="ew", padx=20, pady=5)

        close_btn = CTkButton(
            self.popup,
            text="Close",
            command=self.popup.destroy
        )
        close_btn.grid(row=4, column=0, sticky="ew", padx=20, pady=(20, 10))

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

                upgrade = messagebox.askyesno(
                    "Upgrade CSV Structure",
                    message,
                    parent=self.popup
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

            messagebox.showinfo(
                "Merge Complete",
                f"Added {len(external_rows)} external rows.\n\n"
                f"Total rows: {len(merged_rows)}\n"
                f"Backup: {backup_file}"
                f"{upgrade_text}\n\n"
                f"Record numbers and required columns were recalculated.\n\n"
                f"Please restart the application for all changes to function properly.",
                parent=self.popup
            )

        except Exception as error:
            messagebox.showerror(
                "Merge Failed",
                str(error),
                parent=self.popup
            )

    def save_external_file(self):
        if not os.path.exists(self.data_file):
            messagebox.showerror(
                "File Not Found",
                f"Could not find:\n{self.data_file}",
                parent=self.popup
            )
            return

        save_path = filedialog.asksaveasfilename(
            parent=self.popup,
            title="Save External Data",
            defaultextension=".csv",
            initialfile="matches_external.csv",
            filetypes=[("CSV Files", "*.csv")]
        )

        if not save_path:
            return

        try:
            shutil.copy2(self.data_file, save_path)

            messagebox.showinfo(
                "File Saved",
                f"External data saved to:\n{save_path}",
                parent=self.popup
            )

        except Exception as error:
            messagebox.showerror(
                "Save Failed",
                str(error),
                parent=self.popup
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

    def _center_popup(self):
        self.popup.update_idletasks()

        parent = self.parent.winfo_toplevel()

        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.popup.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.popup.winfo_height() // 2)

        self.popup.geometry(f"+{x}+{y}")


def show_data_tools_popup(parent, tree_manager):
    DataToolsPopup(parent, tree_manager)
