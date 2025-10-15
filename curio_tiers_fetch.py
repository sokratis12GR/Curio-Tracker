import pandas as pd
import requests

from config import LEAGUE
from load_utils import OUTPUT_TIERS_CSV, LOCK_FILE
from logger import log_message
from shared_lock import is_recent_run, update_lock

# === CONFIG ===
MIN_SECONDS_BETWEEN_RUNS = 12 * 60 * 60
HEADERS = {"User-Agent": "fetch-poeladder-curios/1.0"}
API_URL = "https://poeladder.com/api/v1/curio"


# === FETCH FUNCTION ===
def fetch_curios():
    print("Fetching curios from poeladder...")

    try:
        resp = requests.get(
            API_URL,
            params={"league": LEAGUE},
            headers=HEADERS,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to fetch: {e}")
        return []

    if not isinstance(data, list):
        print("[ERROR] Unexpected API response format")
        return []

    return data


# === WRAPPER FUNCTION TO CALL ===
def run_fetch_curios(force=False):
    if not force and is_recent_run(OUTPUT_TIERS_CSV, MIN_SECONDS_BETWEEN_RUNS):
        log_message("[INFO] Last run <12 hours ago, skipping tiers fetch.")
        return

    curios = fetch_curios()
    if not curios:
        log_message("[WARN] No curios fetched.")
        return

    for entry in curios:
        name = entry.get("name")
        if isinstance(name, str) and name.startswith("Replica "):
            entry["name"] = name[len("Replica "):]

    df = pd.DataFrame(curios)
    df.to_csv(OUTPUT_TIERS_CSV, index=False)
    log_message(f"[INFO] Saved curios CSV: {OUTPUT_TIERS_CSV} with {len(df)} rows")

    update_lock(OUTPUT_TIERS_CSV)
    log_message(f"[INFO] Lock file updated: {LOCK_FILE}")
