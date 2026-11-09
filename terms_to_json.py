import csv
import json

INPUT_FILE = "all_valid_heist_terms.csv"
OUTPUT_FILE = "terms.json"

def csv_to_json(input_file, output_file):
    data = []

    # Open CSV and read rows as dictionaries
    with open(input_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            name = row.get("Name", "").strip()
            type_name = row.get("Type", "").strip()

            if name:  # Only include non-empty names
                data.append({"Name": name, "Type": type_name})

    # Write list of objects to JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Converted {len(data)} entries → {output_file}")

if __name__ == "__main__":
    csv_to_json(INPUT_FILE, OUTPUT_FILE)
