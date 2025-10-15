import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import pandas as pd
import requests

from config import POELADDER_LADDERS
from load_utils import OUTPUT_COLLECTION_CSV
from logger import log_message

# === THREADING FLAGS ===
FETCH_DONE = threading.Event()
IS_FETCHING = False

# === CONFIG ===
HEADERS = {"User-Agent": "fetch-poeladder-player-curios/1.0"}
API_URL = "https://poeladder.com/api/v1/users/{player}/curio"


# === SESSION FOR THREAD-SAFE REQUESTS ===
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch_curios(player: str, ladder_identifier: str):
    safe_player = player.replace("#", "-")
    encoded_player = urllib.parse.quote(safe_player, safe="")
    url = API_URL.format(player=encoded_player)

    full_url = f"{url}?ladderIdentifier={urllib.parse.quote(ladder_identifier)}"
    print(f"Fetching curios for {player} using URL:\n{full_url}")

    try:
        resp = SESSION.get(url, params={"ladderIdentifier": ladder_identifier}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch curios for {player} ({ladder_identifier}): {e}")
        return []

    if not isinstance(data, list):
        print("[ERROR] Unexpected API response format")
        return []

    # annotate with ladder info
    for entry in data:
        entry["ladder_identifier"] = ladder_identifier

    return data


def fetch_all_ladders(player: str):
    all_curios = []

    with ThreadPoolExecutor(max_workers=min(len(POELADDER_LADDERS), 4)) as executor:
        future_to_ladder = {
            executor.submit(fetch_curios, player, ladder_identifier): ladder_key
            for ladder_key, ladder_identifier in POELADDER_LADDERS.items()
        }

        for future in as_completed(future_to_ladder):
            ladder_key = future_to_ladder[future]
            try:
                curios = future.result()
                if curios:
                    # Strip "Replica " prefix and map league label
                    league_label = ladder_key.replace("SSF ", "")
                    for entry in curios:
                        name = entry.get("name")
                        if isinstance(name, str) and name.startswith("Replica "):
                            entry["name"] = name[len("Replica "):]
                        entry["league"] = league_label
                    all_curios.extend(curios)
                    log_message(f"[INFO] {ladder_key}: fetched {len(curios)} curios.")
                else:
                    log_message(f"[WARN] {ladder_key}: no curios fetched.")
            except Exception as e:
                log_message(f"[ERROR] {ladder_key}: fetch failed: {e}")

    return all_curios


def run_fetch_curios_threaded(player: str):
    global IS_FETCHING
    IS_FETCHING = True
    FETCH_DONE.clear()
    log_message(f"[INFO] Starting threaded fetch for player {player}...")

    try:
        all_curios = fetch_all_ladders(player)
        if not all_curios:
            log_message("[WARN] No curios fetched for any ladder.")
            return

        df = pd.DataFrame(all_curios)
        df.to_csv(OUTPUT_COLLECTION_CSV, index=False)
        log_message(f"[INFO] Saved combined curios CSV: {OUTPUT_COLLECTION_CSV} with {len(df)} rows.")

        # Optionally, print summary per league
        summary = df.groupby("league").size().to_dict()
        log_message("[INFO] Summary of curios fetched per league:")
        for league, count in summary.items():
            log_message(f"  {league:<20} | {count} items")

    finally:
        IS_FETCHING = False
        FETCH_DONE.set()
