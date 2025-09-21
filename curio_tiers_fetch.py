import requests
import os
import time
import pandas as pd
from settings import LOCK_FILE, OUTPUT_TIERS_CSV

# === CONFIG ===
MIN_SECONDS_BETWEEN_RUNS = 2 * 60 * 60  # 2 hours
HEADERS = {"User-Agent": "fetch-poeladder-curios/1.0"}
API_URL = "https://poeladder.com/api/v1/curio"
LEAGUE = "Mercenaries"

# === LOCK FUNCTIONS ===
def is_recent_run():
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE, "r") as f:
            ts = float(f.read().strip())
        return (time.time() - ts) < MIN_SECONDS_BETWEEN_RUNS
    except Exception:
        return False

def update_lock():
    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(time.time()))
    except Exception as e:
        print(f"[WARN] Failed to update lock file: {e}")

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
    if not force and is_recent_run():
        print("[INFO] Last run <2 hours ago, skipping fetch.")
        return

    curios = fetch_curios()
    if not curios:
        print("[WARN] No curios fetched.")
        return

    for entry in curios:
        name = entry.get("name")
        if isinstance(name, str) and name.startswith("Replica "):
            entry["name"] = name[len("Replica "):]

    df = pd.DataFrame(curios)
    df.to_csv(OUTPUT_TIERS_CSV, index=False)
    print(f"[INFO] Saved curios CSV: {OUTPUT_TIERS_CSV} with {len(df)} rows")

    update_lock()
    print(f"[INFO] Lock file updated: {LOCK_FILE}")

# run_fetch_curios(True)
