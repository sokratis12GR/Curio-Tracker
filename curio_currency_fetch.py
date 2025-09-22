import requests
import os
import sys
import time
import pandas as pd
from datetime import datetime
from settings import LOCK_FILE, OUTPUT_CURRENCY_CSV, LEAGUE
from statistics import median
import ocr_utils as utils
from ocr_utils import load_csv
from shared_lock import is_recent_run, update_lock

# === CONFIG ===
MIN_SECONDS_BETWEEN_RUNS = 2 * 60 * 60  # 2 hours

HEADERS = {"User-Agent": "fetch-poe-ninja-script/1.0"}
VALID_TYPES = ["Currency", "Scarab", "Replica", "Replacement", "Experimental"]

def get_resource_path(filename):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, filename)

def load_csv_with_types(file_path):
    def parser(row):
        if len(row) >= 2:
            raw_term, type_name = row[0].strip(), row[1].strip()
            return utils.smart_title_case(raw_term), type_name
        return None
    rows = load_csv(file_path, row_parser=parser)
    return {term: type_name for term, type_name in rows if term}

TERMS_CSV = get_resource_path("all_valid_heist_terms.csv")
ITEMS_TYPE_MAP = load_csv_with_types(TERMS_CSV)

ITEMS_TYPE_MAP["Chaos Orb"] = "Currency" 

CATEGORIES_API = {
    "Currency": "currencyoverview",
    "Scarabs": "itemoverview",
    "Unique Flasks": "itemoverview",
    "Unique Jewels": "itemoverview",
    "Unique Accessories": "itemoverview",
    "Unique Armours": "itemoverview",
    "Unique Weapons": "itemoverview",
    "Unique Map": "itemoverview",
    "Base Types": "itemoverview"
}

ITEM_TYPE_MAP = {
    "Currency": "Currency",
    "Scarabs": "Scarab",
    "Unique Flasks": "UniqueFlask",
    "Unique Jewels": "UniqueJewel",
    "Unique Accessories": "UniqueAccessory",
    "Unique Armours": "UniqueArmour",
    "Unique Weapons": "UniqueWeapon",
    "Unique Map": "UniqueMap",
    "Base Types": "BaseType"
}

def normalize_name_for_lookup(name: str) -> str:
    if not name:
        return name

    normalized = name
    normalized = normalized.replace(" Of The ", " of the ")
    normalized = normalized.replace(" Of ", " of ")
    normalized = normalized.replace("-Attuned", "-attuned")
    normalized = normalized.replace("Three-Step", "Three-step")

    return normalized

# === FETCH FUNCTION ===
def fetch_all_items():
    all_rows = []

    category_data = {}
    for cat_name, api_endpoint in CATEGORIES_API.items():
        print(f"Fetching {cat_name}...")
        params = {"league": LEAGUE}
        if api_endpoint == "currencyoverview":
            params["type"] = "Currency"
        else:
            params["type"] = ITEM_TYPE_MAP.get(cat_name, cat_name)

        try:
            resp = requests.get(
                f"https://poe.ninja/api/data/{api_endpoint}",
                params=params,
                headers=HEADERS,
                timeout=20
            )
            resp.raise_for_status()
            category_data[cat_name] = resp.json().get("lines", [])
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching {cat_name}: {e}")
            category_data[cat_name] = []

    all_lines = [line for lines in category_data.values() for line in lines]

    seen_replica_replacement = set()

    for csv_name, csv_type in ITEMS_TYPE_MAP.items():
        if csv_type not in VALID_TYPES:
            continue

        lookup_name = normalize_name_for_lookup(csv_name)

        line = None

        if csv_type in ("Replica", "Replacement"):
            # find all matching variants
            if csv_type == "Replica":
                search_name = f"Replica {lookup_name}"
            else:
                search_name = lookup_name

            candidates = [l for l in all_lines if l.get("name") == search_name]

            if candidates:
                # Exclude lines with 6 links
                candidates = [l for l in candidates if l.get("links") != 6]

                if candidates:
                    chaos_values = [l.get("chaosValue") or l.get("chaosEquivalent") for l in candidates]
                    chaos_values = [v for v in chaos_values if isinstance(v, (int, float))]

                    if chaos_values:
                        median_value = median(chaos_values)
                        # pick first line with chaosValue close to median, fallback to first candidate
                        line = next(
                            (l for l in candidates
                             if isinstance(l.get("chaosValue") or l.get("chaosEquivalent"), (int, float))
                             and abs((l.get("chaosValue") or l.get("chaosEquivalent")) - median_value) < 0.001),
                            candidates[0]
                        )
                    else:
                        line = candidates[0]  # fallback if no numeric chaosValue
                else:
                    line = None
        elif csv_type == "Currency":
            if lookup_name == "Chaos Orb":
                chaos_value = 1
                buying = selling = 1
                line = {"chaosValue": chaos_value}
            else:
                line = next((l for l in all_lines if l.get("currencyTypeName") == lookup_name), None)
        elif csv_type == "Experimental":
            base_lines = category_data.get("Base Types", [])
            if lookup_name == "Astrolabe Amulet":
                candidates = [l for l in base_lines if l.get("name") == lookup_name]
                chaos_values = [l.get("chaosValue", 0) for l in candidates if isinstance(l.get("chaosValue"), (int, float))]
                if chaos_values:
                    median_value = sorted(chaos_values)[len(chaos_values)//2]
                    line = next(l for l in candidates if l.get("chaosValue") == median_value)
                else:
                    line = candidates[0] if candidates else None
            else:
                def is_influenced(line):
                    variant = line.get("variant")
                    return variant not in [None, ""]
                candidates = [l for l in base_lines if l.get("name") == lookup_name 
                              and l.get("levelRequired") == 84 
                              and not is_influenced(l)]
                if not candidates:
                    for lvl in [83, 85, 86]:
                        candidates = [l for l in base_lines if l.get("name") == lookup_name 
                                      and l.get("levelRequired") == lvl 
                                      and not is_influenced(l)]
                        if candidates:
                            break
                line = candidates[0] if candidates else None
        else:
            line = next((l for l in all_lines if l.get("name") == lookup_name), None)

        chaos_value = exalted_value = divine_value = None
        buying = selling = "N/A"

        if line:
            if csv_name == "Chaos Orb":
                chaos_value = 1
                buying = selling = 1
                exalted_value = divine_value = "N/A"
            elif csv_type == "Currency":
                chaos_value = line.get("chaosEquivalent")
                buying = selling = round(chaos_value, 2) if isinstance(chaos_value, (int, float)) else "N/A"
                exalted_value = divine_value = "N/A"
            else:
                chaos_value = line.get("chaosValue") or line.get("chaosEquivalent")
                exalted_value = line.get("exaltedValue")
                divine_value = line.get("divineValue")
                buying = selling = round(chaos_value, 2) if isinstance(chaos_value, (int, float)) else "N/A"

            chaos_value = round(chaos_value, 2) if isinstance(chaos_value, (int, float)) else "N/A"
            exalted_value = round(exalted_value, 2) if isinstance(exalted_value, (int, float)) else "N/A"
            divine_value = round(divine_value, 2) if isinstance(divine_value, (int, float)) else "N/A"

        if csv_type in ["Scarab", "Currency"] and buying == "N/A" and selling == "N/A":
            continue

        all_rows.append({
            "Category": csv_type,
            "Name": csv_name,
            "Chaos Value": chaos_value,
            "Exalted Value": exalted_value,
            "Divine Value": divine_value
        })

    return all_rows

# === WRAPPER FUNCTION TO CALL ===
def run_fetch(force=False):
    if not force and is_recent_run(OUTPUT_CURRENCY_CSV):
        print("[INFO] Last run <2 hours ago, skipping fetch.")
        return

    all_rows = fetch_all_items()
    if not all_rows:
        print("[WARN] No data fetched.")
        return


    df = pd.DataFrame(all_rows)
    df.to_csv(OUTPUT_CURRENCY_CSV, index=False, float_format="%.2f")
    print(f"[INFO] Saved CSV: {OUTPUT_CURRENCY_CSV}")

    update_lock(OUTPUT_CURRENCY_CSV)
    print(f"[INFO] Lock file updated: {LOCK_FILE}")

    summary = df.groupby("Category").size().to_dict()
    print("[INFO] Fetched items summary per category:")
    for cat, count in summary.items():
        print(f"  {cat}: {count} items")

# run_fetch(True)