import csv
import os
import sys

import config as c
from ocr_utils import smart_title_case, format_currency_value

_DATASETS = None


def get_data_path(filename: str) -> str:
    appdata = os.getenv('APPDATA') or os.path.expanduser('~')
    base = os.path.join(appdata, c.APP_NAME)
    full_path = os.path.join(base, filename)

    # Ensure that the directory structure exists for the file
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    return full_path


def get_resource_path(filename):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, filename)


def load_csv(file_path, row_parser=None, skip_header=True, ensure_dir=False, as_dict=False):
    results = []

    if ensure_dir:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    if not os.path.exists(file_path):
        return results

    with open(file_path, newline='', encoding='utf-8-sig') as f:
        if as_dict:
            reader = csv.DictReader(f)
        else:
            reader = csv.reader(f)
            if skip_header:
                next(reader, None)

        for row in reader:
            if not row:
                continue
            parsed = row_parser(row) if row_parser else row
            if parsed:
                results.append(parsed)

    return results


def load_csv_with_types(file_path) -> dict:
    def parser(row):
        if len(row) >= 2:
            raw_term, type_name = row[0].strip(), row[1].strip()
            return smart_title_case(raw_term), type_name
        return None

    rows = load_csv(file_path, row_parser=parser)
    return {term: type_name for term, type_name in rows if term}


def load_body_armors(file_path) -> list:
    return [line.strip() for line in open(file_path, encoding="utf-8").readlines()]


def load_experimental_csv(file_path) -> dict:
    def parser(row):
        item_name = smart_title_case(row[0].strip())
        implicits = [line.strip() for line in row[1].splitlines() if line.strip()]
        return item_name, implicits

    rows = load_csv(file_path, row_parser=parser)
    return {item_name: implicits for item_name, implicits in rows if item_name}


def load_currency_dataset(file_path: str) -> dict:
    rows = load_csv(file_path, row_parser=lambda row: (
        smart_title_case(row["Name"].strip()),
        format_currency_value(row.get("Chaos Value", "")),
        format_currency_value(row.get("Divine Value", "")),
        row.get("League")
    ) if "Name" in row else None, as_dict=True)

    dataset = {}
    for term, chaos, divine, league in rows:
        if not league:
            continue
        if league not in dataset:
            dataset[league] = {}
        dataset[league][term] = {"chaos": chaos, "divine": divine}
    return dataset


def load_tiers_dataset(file_path: str, debugging=False) -> dict:
    def parser(row):
        if len(row) >= 2:
            term = smart_title_case(row[0].strip())
            tier = format_currency_value(row[1])
            if debugging:
                print(f"{term}: {tier}")
            return term, {"tier": tier}
        return None

    rows = load_csv(file_path, row_parser=parser)
    return {term: data for term, data in rows if term}


import pandas as pd
from collections import defaultdict


def load_collection_dataset(file_path: str, debugging: bool = False) -> dict:
    try:
        df = pd.read_csv(file_path)

        required_cols = {"name", "owned", "location", "ladder_identifier", "league"}
        if not required_cols.issubset(df.columns):
            return {}

        curios_by_league = defaultdict(dict)

        for _, row in df.iterrows():
            name = str(row["name"]).strip()
            if not name:
                continue

            league = str(row.get("ladder_identifier", "Unknown")).strip() or "Unknown"

            curios_by_league[league][name] = {
                "owned": str(row.get("owned", "FALSE")).strip().upper() == "TRUE",
                "location": str(row.get("location", "")).strip(),
                "ladder_identifier": str(row.get("ladder_identifier", "")).strip(),
                "league": str(row.get("league", "")).strip(),
            }

            if debugging:
                print(f"{league} | {name}: {curios_by_league[league][name]}")

        return dict(curios_by_league)

    except Exception as e:
        return {}


LOG_FILE = get_data_path(c.logs_file_name)
SETTINGS_PATH = get_data_path(c.settings_file_name)
LOCK_FILE = get_data_path(c.lock_file_name)
OUTPUT_CURRENCY_CSV = get_data_path(c.currency_fetch_file_name)
OUTPUT_TIERS_CSV = get_data_path(c.tiers_fetch_file_name)
OUTPUT_COLLECTION_CSV = get_data_path(c.collection_fetch_file_name)
OUTPUT_LEAGUES_CSV = get_data_path(c.poeladder_leagues_fetch_file_name)
INTERNAL_ALL_TYPES_CSV = get_resource_path(c.file_all_valid_heist_terms)
INTERNAL_EXPERIMENTAL_CSV = get_resource_path(c.file_experimental_items)
INTERNAL_BODY_ARMORS_TXT = get_resource_path(c.file_body_armors)


def get_datasets(load_external=True, force_reload=False):
    global _DATASETS
    if _DATASETS is None or force_reload:
        _DATASETS = {
            "terms": load_csv_with_types(INTERNAL_ALL_TYPES_CSV),
            "experimental": load_experimental_csv(INTERNAL_EXPERIMENTAL_CSV),
            "body_armors": load_body_armors(INTERNAL_BODY_ARMORS_TXT),
            "currency": {},
            "tiers": {},
            "collection": {}
        }
        if load_external:
            if os.path.exists(OUTPUT_CURRENCY_CSV):
                _DATASETS["currency"] = load_currency_dataset(OUTPUT_CURRENCY_CSV)
            if os.path.exists(OUTPUT_TIERS_CSV):
                _DATASETS["tiers"] = load_tiers_dataset(OUTPUT_TIERS_CSV)
            if os.path.exists(OUTPUT_COLLECTION_CSV):
                _DATASETS["collection"] = load_collection_dataset(OUTPUT_COLLECTION_CSV)
            if os.path.exists(OUTPUT_LEAGUES_CSV):
                df = pd.read_csv(OUTPUT_LEAGUES_CSV)
                _DATASETS["leagues"] = df.set_index("league_name").to_dict(orient="index")
    return _DATASETS
