import csv
import json
from pathlib import Path
from tkinter import messagebox

from customtkinter import CTk

from json_utils import rows_to_nested_json


def csv_to_nested_json(csv_file_path, json_file_path=None):
    csv_path = Path(csv_file_path)

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    nested = rows_to_nested_json(rows)

    if json_file_path is None:
        json_file_path = csv_path.with_suffix(".json")

    with open(json_file_path, "w", encoding="utf-8") as f:
        json.dump(nested, f, ensure_ascii=False, indent=2)

    root = CTk()
    root.withdraw()
    messagebox.showinfo(
        "Operation Complete",
        f"CSV has been successfully converted to JSON:\n{json_file_path}"
    )
    root.destroy()

    return nested