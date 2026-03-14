import json
from datetime import datetime
from pathlib import Path

from config import data_file_base, csv_record_header, csv_time_header
from data_manager import BaseDataManager
from json_utils import rows_to_nested_json, nested_json_to_rows
from logger import log_message


class JSONManager(BaseDataManager):

    def __init__(self, file_path=None):
        base = Path(file_path or data_file_base)
        self.file_path = base.with_suffix(".json")
        self.last_record_number = 0

    def load_dict(self):
        if not self.file_path.exists():
            return []

        try:
            with self.file_path.open("r", encoding="utf-8") as f:
                nested = json.load(f)
            return nested_json_to_rows(nested)
        except Exception as e:
            log_message(f"[ERROR] JSON load failed: {e}")
            return []

    def save_dict(self, root, rows, fieldnames):
        try:
            nested = rows_to_nested_json(rows)
            with self.file_path.open("w", encoding="utf-8") as f:
                json.dump(nested, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log_message(f"[ERROR] JSON save failed: {e}")

    def get_next_record_number(self, force=False):
        from settings import set_setting, get_setting

        if self.last_record_number == 0:
            self.last_record_number = get_setting("Application", "json_current_row", 0)
            if (self.last_record_number == 0 or force) and self.file_path.exists():
                rows = self.load_dict()
                if rows:
                    last = rows[-1].get(csv_record_header)
                    if last and str(last).isdigit():
                        self.last_record_number = int(last)

        self.last_record_number += 1
        set_setting("Application", "json_current_row", self.last_record_number)
        return self.last_record_number

    def modify_record(self, root, record_number, item_name, updates=None, delete=False):
        rows = self.load_dict()
        if not rows:
            return

        updated = False

        for row in rows:
            if str(row.get("Record #")) == str(record_number):

                if delete:
                    rows.remove(row)
                    updated = True
                    break

                for field_name, new_value in (updates or {}).items():
                    if field_name in row:
                        row[field_name] = str(new_value)
                        updated = True

        if updated:
            if rows:
                self.save_dict(root, rows, fieldnames=list(rows[0].keys()))
            else:
                with self.file_path.open("w", encoding="utf-8") as f:
                    json.dump({"RewardTypes": {
                        "1": "Trinket",
                        "2": "Replacement",
                        "3": "Replica",
                        "4": "Experimented Base Type",
                        "5": "Weapon Enchantment",
                        "6": "Armor Enchantment",
                        "7": "Scarab",
                        "8": "Currency"
                    }, "Players": []}, f, indent=2)

    def append_rows(self, rows: list[dict], root=None):
        if not rows:
            return

        self.ensure_data_file()

        with self.file_path.open("r", encoding="utf-8") as f:
            nested_json = json.load(f)

        for row in rows:
            # Assign record number if missing
            if not row.get(csv_record_header):
                row[csv_record_header] = str(self.get_next_record_number())
            player_name = row["Logged By"].split("#")[0]
            league_name = row["League"]
            blueprint_name = row["Blueprint Type"]
            area_level = row["Area Level"]
            timestamp = row.get("Time", "")
            picked = row.get("Picked", False)

            # Determine reward and type
            reward_name = ""
            type_id = 0
            stack_size = row.get("Stack Size", "")
            for key, reward_type in nested_json["RewardTypes"].items():
                if row.get(reward_type):
                    reward_name = row[reward_type]
                    type_id = int(key)
                    break

            if not reward_name:
                continue

            reward_entry = {
                "Record": str(row["Record #"]),
                "Reward": reward_name,
                "TypeId": type_id,
                "Timestamp": timestamp,
                "Picked": picked
            }
            if stack_size:
                reward_entry["StackSize"] = stack_size

            # Find or create player
            player = next((p for p in nested_json["Players"] if p["Player"] == player_name), None)
            if not player:
                player = {"Player": player_name, "Leagues": []}
                nested_json["Players"].append(player)

            # Find or create league
            league = next((l for l in player["Leagues"] if l["League"] == league_name), None)
            if not league:
                league = {"League": league_name, "Blueprints": []}
                player["Leagues"].append(league)

            # Find or create blueprint
            blueprint = next((b for b in league["Blueprints"] if b["Blueprint"] == blueprint_name), None)
            if not blueprint:
                blueprint = {
                    "Blueprint": blueprint_name,
                    "AreaLevel": area_level,
                    "Rewards": []
                }
                league["Blueprints"].append(blueprint)

            # Append reward directly
            blueprint["Rewards"].append(reward_entry)

        with self.file_path.open("w", encoding="utf-8") as f:
            json.dump(nested_json, f, ensure_ascii=False, indent=2)

        self.last_record_number = max(int(r[csv_record_header]) for r in rows)
        from settings import set_setting
        set_setting("Application", "json_current_row", self.last_record_number)

    def recalculate_record_number(self):
        from settings import set_setting

        rows = self.load_dict()
        if rows:
            last_row = rows[-1]
            self.last_record_number = int(last_row.get(csv_record_header, 0))
        else:
            self.last_record_number = 0

        set_setting("Application", "json_current_row", self.last_record_number)
        return self.last_record_number

    def upgrade_structure(self):
        rows = self.load_dict()
        if not rows:
            return

        changed = False
        for i, row in enumerate(rows, start=1):
            row[csv_record_header] = str(i)
            changed = True

        for i, row in enumerate(rows, start=1):

            if not str(row.get(csv_record_header, "")).isdigit():
                row[csv_record_header] = str(i)
                changed = True

            if "Picked" not in row:
                row["Picked"] = "False"
                changed = True

        if changed:
            self.save_dict(None, rows, fieldnames=list(rows[0].keys()))
            log_message("[INFO] JSON structure upgraded")

    def duplicate_latest(self, root=None):
        rows = self.load_dict()
        if not rows:
            log_message("[ERROR] JSON file has no entries to duplicate.")
            return None

        # Recalculate last_record_number based on current rows in file
        self.recalculate_record_number()

        last_row = rows[-1].copy()
        record_number = self.get_next_record_number()
        last_row[csv_record_header] = str(record_number)

        if csv_time_header in last_row:
            last_row[csv_time_header] = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        rows.append(last_row)

        self.save_dict(None, rows, fieldnames=list(last_row.keys()))

        log_message(f"[INFO] Duplicated latest entry → Record {record_number}")

        from settings import set_setting
        set_setting("Application", "json_current_row", self.last_record_number)

        return last_row

    def ensure_data_file(self):
        if not self.file_path.exists():
            base_json = {
                "RewardTypes": {
                    "1": "Trinket",
                    "2": "Replacement",
                    "3": "Replica",
                    "4": "Experimented Base Type",
                    "5": "Weapon Enchantment",
                    "6": "Armor Enchantment",
                    "7": "Scarab",
                    "8": "Currency"
                },
                "Players": []
            }
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(base_json, f, indent=2)