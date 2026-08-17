import csv
import io
import json
import os
import sys
import urllib

import config as c
from ocr_utils import smart_title_case, format_currency_value
from shared_lock import is_site_cache_valid, update_site_cache_lock

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


def load_json(file_path, default=None, ensure_dir=False):
    if ensure_dir:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

    if not os.path.exists(file_path):
        return default if default is not None else {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


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


def save_json(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_json_url(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def refresh_site_cache():
    resources = {
        "terms": {
            "url": c.all_terms_url,
            "file": TERMS_CACHE_FILE,
        },
        "experimental": {
            "url": c.experimental_items_url,
            "file": EXPERIMENTAL_ITEMS_CACHE_FILE,
        },
        "enchantments_trade": {
            "url": c.enchantments_trade_url,
            "file": ENCHANTMENTS_TRADE_CACHE_FILE,
        },
    }

    fetched = {}

    for name, resource in resources.items():
        try:
            print(f"Fetching remote JSON from {resource['url']} ...")
            fetched[name] = fetch_json_url(resource["url"])
        except Exception as e:
            print(f"Failed to refresh {name}: {e}")

            update_site_cache_lock(
                status="error",
                error=f"{name}: {e}"
            )

            return False

    for name, resource in resources.items():
        save_json(resource["file"], fetched[name])

    update_site_cache_lock(
        status="success"
    )

    return True


def ensure_site_cache():
    cache_files_exist = (
            os.path.exists(TERMS_CACHE_FILE)
            and os.path.exists(EXPERIMENTAL_ITEMS_CACHE_FILE)
            and os.path.exists(ENCHANTMENTS_TRADE_CACHE_FILE)
    )

    if is_site_cache_valid() and cache_files_exist:
        return True

    if refresh_site_cache():
        return True

    if cache_files_exist:
        print("[WARN] Site refresh failed. Using stale local cache.")
        return True

    return False


_REMOTE_EXPERIMENTAL_CACHE = None


def load_remote_experimental(url=None):
    global _REMOTE_EXPERIMENTAL_CACHE

    if _REMOTE_EXPERIMENTAL_CACHE is not None:
        return _REMOTE_EXPERIMENTAL_CACHE

    ensure_site_cache()

    data = load_json(EXPERIMENTAL_ITEMS_CACHE_FILE, default=[])

    parsed = {}

    for entry in data:
        item_name = entry.get("Item", "").strip()
        implicits = entry.get("ImplicitMod", [])

        if not item_name:
            continue

        if isinstance(implicits, str):
            implicits = [line.strip() for line in implicits.splitlines() if line.strip()]
        elif isinstance(implicits, list):
            implicits = [str(line).strip() for line in implicits if str(line).strip()]
        else:
            implicits = []

        parsed[smart_title_case(item_name)] = implicits

    _REMOTE_EXPERIMENTAL_CACHE = parsed
    print(f"Successfully loaded cached experimental items ({len(parsed)} items).")
    return parsed


def load_currency_dataset(file_path: str) -> dict:
    rows = load_csv(file_path, row_parser=lambda row: (
        smart_title_case(row["Name"].strip()),
        format_currency_value(row.get("Chaos Value", "")),
        format_currency_value(row.get("Divine Value", "")),
        format_currency_value(row.get("five_link_value", "")),
        format_currency_value(row.get("six_link_value", "")),
        row.get("League")
    ) if "Name" in row else None, as_dict=True)

    dataset = {}
    for term, chaos, divine, five_l, six_l, league in rows:
        if not league:
            continue
        if league not in dataset:
            dataset[league] = {}
        dataset[league][term] = {"chaos": chaos, "divine": divine, "five_link": five_l, "six_link": six_l}
    return dataset


_REMOTE_ENCHANTMENTS_TRADE_CACHE = None

def load_remote_enchantments_trade(url=c.enchantments_trade_url):
    global _REMOTE_ENCHANTMENTS_TRADE_CACHE

    if _REMOTE_ENCHANTMENTS_TRADE_CACHE is not None:
        return _REMOTE_ENCHANTMENTS_TRADE_CACHE

    ensure_site_cache()

    data = load_json(ENCHANTMENTS_TRADE_CACHE_FILE, default={})

    if not isinstance(data, dict):
        print("Invalid cached enchantments_trade.json")
        return {}

    _REMOTE_ENCHANTMENTS_TRADE_CACHE = data

    print(f"Successfully loaded {len(data)} cached enchantment trade mappings.")

    return data


def load_tiers_dataset(file_path: str, debugging=False) -> dict:
    def parser(row):
        if len(row) >= 2:
            term = smart_title_case(row[0].strip())
            tier = format_currency_value(row[1])
            wiki = row[2]
            img = row[3]
            if debugging:
                print(f"{term}: {tier} | {wiki} | {img}")
            return term, {"tier": tier, "wiki": wiki, "img": img}
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


def load_csv_from_url(url, row_parser=None, skip_header=True):
    results = []

    try:
        print(f"Fetching remote CSV from {url} ...")
        with urllib.request.urlopen(url) as response:
            text = response.read().decode("utf-8")

        reader = csv.reader(io.StringIO(text))

        if skip_header:
            next(reader, None)

        for row in reader:
            if not row:
                continue

            parsed = row_parser(row) if row_parser else row
            if parsed:
                results.append(parsed)

        print("Successfully loaded remote CSV.")
        return results

    except Exception as e:
        print(f"Failed to fetch remote CSV: {e}")
        return []


_REMOTE_TERMS_CACHE = None


def load_remote_terms(url=c.all_terms_url):
    global _REMOTE_TERMS_CACHE

    if _REMOTE_TERMS_CACHE:
        return _REMOTE_TERMS_CACHE

    ensure_site_cache()

    data = load_json(TERMS_CACHE_FILE, default=[])

    parsed = {}
    for entry in data:
        name = entry.get("Name", "").strip()
        type_name = entry.get("Type", "").strip()
        if name:
            parsed[smart_title_case(name)] = type_name

    _REMOTE_TERMS_CACHE = parsed
    print(f"Successfully loaded cached JSON ({len(parsed)} terms).")
    return parsed


LOG_FILE = get_data_path(c.logs_file_name)
SETTINGS_PATH = get_data_path(c.settings_file_name)
LOCK_FILE = get_data_path(c.lock_file_name)
OUTPUT_CURRENCY_CSV = get_data_path(c.currency_fetch_file_name)
OUTPUT_TIERS_CSV = get_data_path(c.tiers_fetch_file_name)
OUTPUT_COLLECTION_CSV = get_data_path(c.collection_fetch_file_name)
OUTPUT_LEAGUES_CSV = get_data_path(c.poeladder_leagues_fetch_file_name)
INTERNAL_BODY_ARMORS_TXT = get_resource_path(c.file_body_armors)
TERMS_CACHE_FILE = get_data_path(c.terms_cache_file_name)
EXPERIMENTAL_ITEMS_CACHE_FILE = get_data_path(c.experimental_items_cache_file_name)
ENCHANTMENTS_TRADE_CACHE_FILE = get_data_path(c.enchantments_trade_cache_file_name)


def get_datasets(load_external=True, force_reload=False):
    global _DATASETS
    if _DATASETS is None or force_reload:
        _DATASETS = {
            "terms": load_remote_terms(),
            "experimental": load_remote_experimental(),
            "body_armors": load_body_armors(INTERNAL_BODY_ARMORS_TXT),
            "enchantments_trade": load_remote_enchantments_trade(),
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
