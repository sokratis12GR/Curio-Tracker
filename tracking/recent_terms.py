from datetime import datetime

import config as c
import ocr_utils as utils
from logger import log_message

MAX_RECENT_TERMS = 5  # keep last 5 entries in memory
recent_terms = []  # list of tuples: (term, datetime)

duplicate_duration_time = c.time_last_dupe_check_seconds


def populate_recent_terms(data_mgr, within_seconds: int = None, max_items: int = None):
    global recent_terms

    max_items = max_items or MAX_RECENT_TERMS
    within_seconds = within_seconds or int(duplicate_duration_time or 60)

    try:
        rows = data_mgr.load_dict()
    except Exception:
        rows = []

    if not rows:
        recent_terms = []
        return

    # Take last max_items rows
    last_rows = rows[-max_items:]
    parsed = []
    now = datetime.now()

    for row in last_rows:
        ts_str = row.get(c.csv_time_header)

        term = None
        for col in (
                c.csv_trinket_header,
                c.csv_replacement_header,
                c.csv_replica_header,
                c.csv_experimented_header,
                c.csv_weapon_enchant_header,
                c.csv_armor_enchant_header,
                c.csv_scarab_header,
                c.csv_currency_header,
        ):
            val = row.get(col)
            if val and val.strip():
                term = utils.smart_title_case(val.strip())
                break

        if not term:
            continue

        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S") if ts_str else None
        except Exception:
            ts = None

        if ts:
            if (now - ts).total_seconds() <= within_seconds:
                parsed.append((term, ts))
        else:
            parsed.append((term, now))

    parsed = parsed[-max_items:]
    recent_terms = parsed.copy()


def is_duplicate_recent_entry(value):
    current_time = datetime.now()
    dupe_duration = int(duplicate_duration_time or 60)

    incoming = utils.smart_title_case(value)

    for term, ts in recent_terms:
        if term == incoming and (current_time - ts).total_seconds() < dupe_duration:
            log_message(f"[DupCheck] In-memory dupe found for '{incoming}' (ts={ts})")
            return True

    return False


def mark_term_as_captured(value, timestamp: datetime = None):
    global recent_terms
    ts = timestamp or datetime.now()
    term = utils.smart_title_case(value)

    for idx, (t, old_ts) in enumerate(recent_terms):
        if t == term:
            recent_terms.pop(idx)
            break

    recent_terms.append((term, ts))

    if len(recent_terms) > MAX_RECENT_TERMS:
        recent_terms = recent_terms[-MAX_RECENT_TERMS:]

    # format timestamps for logging
    formatted = [(t, ts.strftime("%Y-%m-%d %H:%M:%S")) for t, ts in recent_terms]

    log_message(f"[RecentTerms] Buffer now: {formatted}")


def remove_recent_term(term: str) -> bool:
    global recent_terms

    term = utils.smart_title_case(term)
    term = term.replace("Replica ", "")
    before = len(recent_terms)

    recent_terms = [
        (t, ts) for (t, ts) in recent_terms
        if t != term
    ]

    removed = len(recent_terms) != before
    if removed:
        log_message(f"[RecentTerms] Removed term: {term}")
    return removed


def clear_recent_terms():
    global recent_terms
    recent_terms.clear()
    log_message("[RecentTerms] Cleared all recent terms")


def set_duplicate_duration(duration: int):
    from settings import set_setting
    global duplicate_duration_time
    duplicate_duration_time = duration
    set_setting('Application', 'time_last_dupe_check_seconds', duration)
    log_message(f"Time between-duplicates check set to: {duration}s")
