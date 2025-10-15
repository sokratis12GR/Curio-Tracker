import json
import os
import time

from load_utils import LOCK_FILE

MIN_SECONDS_BETWEEN_RUNS: int = 2 * 60 * 60  # 2 hours


def is_recent_run(script_name: str, min_duration: int = MIN_SECONDS_BETWEEN_RUNS) -> bool:
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE, "r") as f:
            data = json.load(f)
        ts = float(data.get(script_name, 0))
        return (time.time() - ts) < min_duration
    except Exception as e:
        print(e)
        return False


def update_lock(script_name: str):
    try:
        data = {}
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, "r") as f:
                data = json.load(f)
        data[script_name] = time.time()
        with open(LOCK_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[WARN] Failed to update lock file: {e}")
