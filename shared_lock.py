import json
import os
import threading
import time

import config as c

_LOCK_WRITE_MUTEX = threading.Lock()

def _get_data_path(filename: str) -> str:
    appdata = os.getenv("APPDATA") or os.path.expanduser("~")
    base = os.path.join(appdata, c.APP_NAME)
    full_path = os.path.join(base, filename)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    return full_path


# Existing external-fetch lock
LOCK_FILE = _get_data_path(c.lock_file_name)

# Separate sokratis.space cache lock
SITE_LOCK_FILE = _get_data_path(c.site_cache_lock_file_name)

MIN_SECONDS_BETWEEN_RUNS = 2 * 60 * 60  # 2 hours
SITE_CACHE_DURATION = 60 * 60  # 1 hour


def _read_lock(lock_file: str) -> dict:
    if not os.path.exists(lock_file):
        return {}

    try:
        with open(lock_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, dict) else {}

    except Exception as e:
        print(f"[WARN] Failed to read lock file {lock_file}: {e}")
        return {}


def _write_lock(lock_file: str, data: dict):
    try:
        os.makedirs(os.path.dirname(lock_file), exist_ok=True)

        with open(lock_file, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )
            f.write("\n")

    except Exception as e:
        print(f"[WARN] Failed to update lock file {lock_file}: {e}")


# ------------------------------------------------------------------
# Existing external-site locks
# ------------------------------------------------------------------

def is_recent_run(
        script_name: str,
        min_duration: int = MIN_SECONDS_BETWEEN_RUNS
) -> bool:
    data = _read_lock(LOCK_FILE)

    try:
        run_data = data.get(script_name, {})

        if not isinstance(run_data, dict):
            ts = float(run_data)

        else:
            ts = float(run_data.get("last_success", 0))

        return (time.time() - ts) < min_duration

    except (TypeError, ValueError, AttributeError):
        return False


def update_lock(
        script_name: str,
        status="success",
        error=None,
        resources=None
):
    with _LOCK_WRITE_MUTEX:
        data = _read_lock(LOCK_FILE)

        now = time.time()

        run_data = data.get(script_name, {})

        if not isinstance(run_data, dict):
            try:
                old_timestamp = float(run_data)
            except (TypeError, ValueError):
                old_timestamp = 0

            run_data = {}

            if old_timestamp > 0:
                run_data["last_success"] = old_timestamp

        run_data["last_attempt"] = now
        run_data["status"] = status

        if status == "success":
            run_data["last_success"] = now
            run_data.pop("error", None)
        elif error:
            run_data["error"] = str(error)

        if resources:
            run_data["resources"] = resources

        data[script_name] = run_data

        _write_lock(LOCK_FILE, data)

# ------------------------------------------------------------------
# sokratis.space shared cache lock
# ------------------------------------------------------------------

def is_site_cache_valid(
        min_duration: int = SITE_CACHE_DURATION
) -> bool:
    data = _read_lock(SITE_LOCK_FILE)

    try:
        site_data = data.get("sokratis_space", {})

        if not isinstance(site_data, dict):
            ts = float(site_data)

        else:
            ts = float(site_data.get("last_success", 0))

        return (time.time() - ts) < min_duration

    except (TypeError, ValueError, AttributeError):
        return False


def update_site_cache_lock(
        status="success",
        error=None
):
    with _LOCK_WRITE_MUTEX:
        data = _read_lock(SITE_LOCK_FILE)

        now = time.time()

        site_data = data.get("sokratis_space", {})

        if not isinstance(site_data, dict):
            try:
                old_timestamp = float(site_data)
            except (TypeError, ValueError):
                old_timestamp = 0

            site_data = {}

            if old_timestamp > 0:
                site_data["last_success"] = old_timestamp

        site_data["last_attempt"] = now
        site_data["status"] = status

        if status == "success":
            site_data["last_success"] = now
            site_data.pop("error", None)
        elif error:
            site_data["error"] = str(error)

        site_data["resources"] = {
            "terms": {
                "url": c.all_terms_url,
                "file": c.terms_cache_file_name,
            },
            "experimental_items": {
                "url": c.experimental_items_url,
                "file": c.experimental_items_cache_file_name,
            },
            "enchantments_trade": {
                "url": c.enchantments_trade_url,
                "file": c.enchantments_trade_cache_file_name,
            },
        }

        data["sokratis_space"] = site_data

        _write_lock(SITE_LOCK_FILE, data)
