"""Write the built-in Heist reference data to blueprint_info.json for uploading
to https://sokratis.space/curio_tracker/blueprint_info.json"""

import json

from blueprint_data import DEFAULT_BLUEPRINT_INFO

OUTPUT_FILE = "blueprint_info.json"

if __name__ == "__main__":
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_BLUEPRINT_INFO, f, indent=2, ensure_ascii=False)
        f.write("\n")
    counts = ", ".join(f"{k}: {len(v)}" for k, v in DEFAULT_BLUEPRINT_INFO.items() if isinstance(v, list))
    print(f"Exported {counts} -> {OUTPUT_FILE}")
