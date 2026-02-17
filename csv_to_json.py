import csv
import json
from pathlib import Path
from collections import defaultdict
import tkinter as tk
from tkinter import messagebox

def csv_to_nested_json(csv_file_path, json_file_path=None):
    try:
        csv_path = Path(csv_file_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

        if json_file_path is None:
            json_file_path = csv_path.with_suffix('.json')

        rows = []
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        nested = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        reward_columns = [
            'Trinket', 'Replacement', 'Replica', 'Experimented Base Type',
            'Weapon Enchantment', 'Armor Enchantment', 'Scarab', 'Currency'
        ]

        for row in rows:
            league = row['League']
            player = row['Logged By']
            blueprint_type = row['Blueprint Type']
            area_level = row['Area Level']
            timestamp = row.get('Time', '')
            picked = row.get('Picked', 'False').strip().lower() == 'true'
            record_number = row.get('Record #', '')

            blueprint_key = (blueprint_type, area_level)

            for col in reward_columns:
                value = row.get(col)
                if value:
                    reward_entry = {
                        "Record #": record_number,
                        "Reward": value,
                        "Type": col,
                        "Timestamp": timestamp,
                        "Picked": picked
                    }

                    if col in ['Currency', 'Scarab']:
                        reward_entry["Stack Size"] = row.get('Stack Size', '')

                    nested[league][player][blueprint_key].append(reward_entry)
                    break

        def group_wings(rewards):
            wings = []
            for i in range(0, len(rewards), 5):
                wings.append({"Wing": rewards[i:i+5]})
            return wings

        final_json = {}
        for league, players in nested.items():
            final_json[league] = []
            for player, blueprints in players.items():
                player_entry = {"Player": player, "Blueprints": []}
                for (blueprint, area_level), rewards in blueprints.items():
                    blueprint_entry = {
                        "Blueprint": blueprint,
                        "Area Level": area_level,
                        "Blueprint rewards": group_wings(rewards)
                    }
                    player_entry["Blueprints"].append(blueprint_entry)
                final_json[league].append(player_entry)

        # Custom JSON writer: pretty outer structure, single-line reward entries
        def write_json_with_single_line_rewards(obj, file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                def _serialize(obj, indent=0):
                    spacing = '  ' * indent
                    if isinstance(obj, list):
                        f.write('[\n')
                        for i, item in enumerate(obj):
                            f.write(spacing + '  ')
                            _serialize(item, indent + 1)
                            if i != len(obj) - 1:
                                f.write(',')
                            f.write('\n')
                        f.write(spacing + ']')
                    elif isinstance(obj, dict):
                        if "Reward" in obj:
                            f.write(json.dumps(obj, ensure_ascii=False))
                        else:
                            f.write('{\n')
                            items = list(obj.items())
                            for i, (k, v) in enumerate(items):
                                f.write(f'{spacing}  "{k}": ')
                                _serialize(v, indent + 1)
                                if i != len(items) - 1:
                                    f.write(',')
                                f.write('\n')
                            f.write(spacing + '}')
                    else:
                        f.write(json.dumps(obj, ensure_ascii=False))
                _serialize(obj, 0)
                f.write('\n')

        write_json_with_single_line_rewards(final_json, json_file_path)

        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Success", f"Exported matches data to JSON:\n{json_file_path}")
        root.destroy()

        return final_json

    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Error", f"Failed to export matches data to JSON:\n{e}")
        root.destroy()
        return None
