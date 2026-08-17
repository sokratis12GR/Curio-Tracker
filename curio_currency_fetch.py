import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import median

import pandas as pd
import requests

import config
from config import LEAGUES_TO_FETCH, APP_DISPLAY_NAME, DISCORD_USERNAME, CONTACT
from load_utils import get_datasets, OUTPUT_CURRENCY_CSV
from logger import log_message
from shared_lock import is_recent_run, update_lock
from version_utils import VERSION

# === THREADING FLAGS ===
FETCH_DONE = threading.Event()
IS_FETCHING = False

# === CONFIG ===
MIN_SECONDS_BETWEEN_RUNS = 2 * 60 * 60  # 2 hours
LOCK_FILE_IDENTIFIER ="poe_ninja_currency"

HEADERS = {
    "User-Agent": (
        f"{APP_DISPLAY_NAME}/{VERSION} "
        f"(Economy value fetcher for heist items; contact: {CONTACT} | discord: {DISCORD_USERNAME})"
    ),
    "Accept": "application/json",
}
VALID_TYPES = ["Currency", "Scarab", "Replica", "Replacement", "Experimental"]

ITEMS_TYPE_MAP = get_datasets()["terms"]

ITEMS_TYPE_MAP["Chaos Orb"] = "Currency"

CATEGORIES_API = {
    "Currency": "exchange",
    "Scarabs": "exchange",
    "Unique Flasks": "stash",
    "Unique Jewels": "stash",
    "Unique Accessories": "stash",
    "Unique Armours": "stash",
    "Unique Weapons": "stash",
    "Unique Map": "stash",
    "Base Types": "stash"
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


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch_category(cat_name, api_endpoint, league):
    item_type = ITEM_TYPE_MAP.get(cat_name, cat_name)

    if cat_name == "Currency":
        item_type = "Currency"

    if api_endpoint == "exchange":
        url = (
            "https://poe.ninja/poe1/api/economy/"
            "exchange/current/overview"
        )
    else:
        url = (
            "https://poe.ninja/poe1/api/economy/"
            "stash/current/item/overview"
        )

    params = {
        "league": league,
        "type": item_type
    }

    try:
        resp = SESSION.get(
            url,
            params=params,
            timeout=20
        )
        resp.raise_for_status()

        data = resp.json()

        if api_endpoint == "exchange":
            lines = normalize_exchange_data(data)
        else:
            lines = data.get("lines", [])

        return cat_name, lines

    except Exception as e:
        print(f"Error fetching {cat_name}: {e}")
        return cat_name, []


def normalize_exchange_data(data):
    items_by_id = {
        item.get("id"): item
        for item in data.get("items", [])
        if item.get("id")
    }

    core = data.get("core", {})
    rates = core.get("rates", {})
    divine_rate = rates.get("divine")

    normalized_lines = []

    for line in data.get("lines", []):
        item_id = line.get("id")
        item = items_by_id.get(item_id, {})

        chaos_value = line.get("primaryValue")

        divine_value = None
        if isinstance(chaos_value, (int, float)) and isinstance(divine_rate, (int, float)):
            divine_value = chaos_value * divine_rate

        normalized_lines.append({
            **line,
            "name": item.get("name"),
            "detailsId": item.get("detailsId"),
            "image": item.get("image"),
            "category": item.get("category"),
            "chaosValue": chaos_value,
            "chaosEquivalent": chaos_value,
            "divineValue": divine_value
        })

    return normalized_lines


def build_lookup_dict(category_data):
    lookup = defaultdict(list)
    for lines in category_data.values():
        for l in lines:
            key = l.get("name") or l.get("currencyTypeName")
            if key:
                lookup[key].append(l)
    return lookup


def fetch_all_items(league: str):
    category_data = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(fetch_category, cat, api, league)
            for cat, api in CATEGORIES_API.items()
        ]
        for fut in as_completed(futures):
            cat_name, data = fut.result()
            category_data[cat_name] = data

    lookup_dict = build_lookup_dict(category_data)
    base_lines = category_data.get("Base Types", [])

    all_rows = []

    for csv_name, csv_type in ITEMS_TYPE_MAP.items():
        if csv_type not in VALID_TYPES:
            continue

        lookup_name = normalize_name_for_lookup(csv_name)
        line = None
        five_link_value = six_link_value = "N/A"

        # candidates = lookup_dict.get(lookup_name, [])
        # if candidates:

        if csv_type in ("Replica", "Replacement"):
            search_name = f"Replica {lookup_name}" if csv_type == "Replica" else lookup_name
            candidates = lookup_dict.get(search_name, [])
            if candidates:
                five_link_candidates = [c for c in candidates if c.get("links") == 5]
                six_link_candidates = [c for c in candidates if c.get("links") == 6]

                if five_link_candidates:
                    five_link_value = round(five_link_candidates[0].get("chaosValue", "N/A"), 2) \
                        if isinstance(five_link_candidates[0].get("chaosValue"), (int, float)) else "N/A"

                if six_link_candidates:
                    six_link_value = round(six_link_candidates[0].get("chaosValue", "N/A"), 2) \
                        if isinstance(six_link_candidates[0].get("chaosValue"), (int, float)) else "N/A"

                candidates = [l for l in candidates if l.get("links") not in (5, 6)]
                chaos_values = [l.get("chaosValue") or l.get("chaosEquivalent")
                                for l in candidates if
                                isinstance(l.get("chaosValue") or l.get("chaosEquivalent"), (int, float))]
                if chaos_values:
                    med = median(chaos_values)
                    line = min(candidates, key=lambda l: abs((l.get("chaosValue") or l.get("chaosEquivalent")) - med))
                else:
                    line = candidates[0] if candidates else None
        elif csv_type == "Currency":
            if lookup_name == "Chaos Orb":
                line = {"chaosValue": 1}
            else:
                line = lookup_dict.get(lookup_name, [None])[0]
        elif csv_type == "Experimental":
            if lookup_name == "Astrolabe Amulet":
                candidates = [l for l in base_lines if l.get("name") == lookup_name]
                chaos_values = [l.get("chaosValue", 0) for l in candidates if
                                isinstance(l.get("chaosValue"), (int, float))]
                if chaos_values:
                    med = sorted(chaos_values)[len(chaos_values) // 2]
                    line = next((l for l in candidates if l.get("chaosValue") == med), candidates[0])
                else:
                    line = candidates[0] if candidates else None
            else:
                def is_influenced(l):
                    return l.get("variant") not in [None, ""]

                candidates = [l for l in base_lines if
                              l.get("name") == lookup_name and l.get("levelRequired") == 84 and not is_influenced(l)]

                five_link_candidates = [c for c in candidates if c.get("links") == 5]
                six_link_candidates = [c for c in candidates if c.get("links") == 6]

                if five_link_candidates:
                    five_link_value = round(five_link_candidates[0].get("chaosValue", "N/A"), 2) \
                        if isinstance(five_link_candidates[0].get("chaosValue"), (int, float)) else "N/A"

                if six_link_candidates:
                    six_link_value = round(six_link_candidates[0].get("chaosValue", "N/A"), 2) \
                        if isinstance(six_link_candidates[0].get("chaosValue"), (int, float)) else "N/A"

                if not candidates:
                    for lvl in [83, 85, 86]:
                        candidates = [l for l in base_lines if l.get("name") == lookup_name and l.get(
                            "levelRequired") == lvl and not is_influenced(l)]
                        if candidates:
                            break
                line = candidates[0] if candidates else None
        else:
            line = lookup_dict.get(lookup_name, [None])[0]

        chaos_value = exalted_value = divine_value = None
        buying = selling = "N/A"

        if line:
            if csv_name == "Chaos Orb":
                chaos_value = 1
                buying = selling = 1
                exalted_value = divine_value = "N/A"

            elif csv_type in ("Currency", "Scarab"):
                chaos_value = (
                        line.get("chaosValue")
                        or line.get("chaosEquivalent")
                )

                divine_value = line.get("divineValue")
                exalted_value = "N/A"

                buying = selling = (
                    round(chaos_value, 2)
                    if isinstance(chaos_value, (int, float))
                    else "N/A"
                )

            else:
                chaos_value = (
                        line.get("chaosValue")
                        or line.get("chaosEquivalent")
                )

                exalted_value = line.get("exaltedValue")
                divine_value = line.get("divineValue")

                buying = selling = (
                    round(chaos_value, 2)
                    if isinstance(chaos_value, (int, float))
                    else "N/A"
                )

            chaos_value = (
                round(chaos_value, 2)
                if isinstance(chaos_value, (int, float))
                else "N/A"
            )

            exalted_value = (
                round(exalted_value, 2)
                if isinstance(exalted_value, (int, float))
                else "N/A"
            )

            divine_value = (
                round(divine_value, 4)
                if isinstance(divine_value, (int, float))
                else "N/A"
            )

        if csv_type in ["Scarab", "Currency"] and buying == "N/A" and selling == "N/A":
            continue

        all_rows.append({
            "Category": csv_type,
            "Name": csv_name,
            "Chaos Value": chaos_value,
            "Exalted Value": exalted_value,
            "Divine Value": divine_value,
            "five_link_value": five_link_value,
            "six_link_value": six_link_value,
            "League": league
        })

    return all_rows


# === WRAPPER FUNCTION TO CALL ===
def run_fetch(force=False):
    global IS_FETCHING

    # --- Skip if recent ---
    if not force and is_recent_run(
            LOCK_FILE_IDENTIFIER,
            min_duration=MIN_SECONDS_BETWEEN_RUNS
    ):
        log_message("[INFO] Using cached currency data (recent lock found).")
        FETCH_DONE.set()
        IS_FETCHING = False
        return

    IS_FETCHING = True
    FETCH_DONE.clear()
    log_message(f"[INFO] Fetching fresh currency data from poe.ninja for {len(LEAGUES_TO_FETCH)} leagues...")

    try:
        all_rows = []

        with ThreadPoolExecutor(max_workers=min(len(LEAGUES_TO_FETCH), 4)) as executor:
            future_to_league = {executor.submit(fetch_all_items, league): league for league in LEAGUES_TO_FETCH}
            for future in as_completed(future_to_league):
                league = future_to_league[future]
                try:
                    rows = future.result()
                    if rows:
                        all_rows.extend(rows)
                        log_message(f"[INFO] {league}: fetched {len(rows)} rows.")
                    else:
                        log_message(f"[WARN] {league}: no data fetched.")
                except Exception as e:
                    log_message(f"[ERROR] {league}: fetch failed: {e}")

        if not all_rows:
            log_message("[WARN] No data fetched for any league.")

            update_lock(
                LOCK_FILE_IDENTIFIER,
                status="error",
                error="No data fetched for any league.",
                resources={
                    "currency": {
                        "url": "https://poe.ninja",
                        "file": config.currency_fetch_file_name,
                    }
                }
            )

            return

        df = pd.DataFrame(all_rows)
        df.to_csv(OUTPUT_CURRENCY_CSV, index=False, float_format="%.2f")
        log_message(f"[INFO] Saved combined CSV: {OUTPUT_CURRENCY_CSV}")

        update_lock(
            LOCK_FILE_IDENTIFIER,
            status="success",
            resources={
                "currency": {
                    "url": "https://poe.ninja",
                    "file": config.currency_fetch_file_name,
                }
            }
        )
        log_message(f"[INFO] Lock updated: {LOCK_FILE_IDENTIFIER}")

        summary = df.groupby(["League", "Category"]).size().to_dict()
        log_message("[INFO] Summary of fetched items per league/category:")
        for (league, cat), count in summary.items():
            log_message(f"  {league:<15} | {cat:<15} | {count} items")

    finally:
        IS_FETCHING = False
        FETCH_DONE.set()

# run_fetch(True)
