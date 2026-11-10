"""
Heist reference data for the Blueprint Encyclopedia.

Load order: remote JSON (config.blueprint_info_url) -> local cache
(fetch/blueprint_info.json) -> built-in DEFAULT_BLUEPRINT_INFO below, so the
window always works offline or before the remote file has been uploaded.

Run `python blueprint_info_export.py` to write DEFAULT_BLUEPRINT_INFO to
blueprint_info.json for uploading.

Sourced from https://www.poewiki.net/wiki/Heist and
https://www.poewiki.net/wiki/Blueprint
"""

import json
import os
import threading
import time
import urllib.request

import config as c
from load_utils import get_data_path

CDN = "https://web.poecdn.com/image/Art/2DItems"
BLUEPRINT_ICON_BASE = "https://sokratis.space/curio_tracker/assets/heist"

CACHE_MAX_AGE_SECONDS = 24 * 60 * 60


def _bp_icon(slug):
    return f"{BLUEPRINT_ICON_BASE}/{slug}.png"


DEFAULT_BLUEPRINT_INFO = {
    "version": 1,
    "category_icons": {
        "locations": f"{CDN}/Currency/Heist/ContractItem.png",
        "jobs": f"{CDN}/Currency/Heist/HeistCoinCurrency.png",
        "chest_types": f"{CDN}/Currency/CurrencyRerollRare.png",
        "mechanics": f"{CDN}/Currency/Heist/ContractItem.png",
    },
    "locations": [
        {"name": "Bunker", "icon": _bp_icon("bunker"), "description": "",
         "jobs": ["Agility", "Counter-thaumaturgy", "Engineering", "Demolition",
                  "Lockpicking", "Perception", "Trap disarmament"],
         "monsters": "Templars", "damage": ["Physical", "Lightning"]},
        {"name": "Records Office", "icon": _bp_icon("records_office"), "description": "",
         "jobs": ["Brute force", "Counter-thaumaturgy", "Deception", "Demolition",
                  "Lockpicking", "Trap disarmament"],
         "monsters": "", "damage": []},
        {"name": "Mansion", "icon": _bp_icon("mansion"), "description": "",
         "jobs": ["Agility", "Brute force", "Deception", "Lockpicking", "Perception"],
         "monsters": "", "damage": []},
        {"name": "Smuggler's Den", "icon": _bp_icon("smugglers_den"), "description": "",
         "jobs": ["Brute force", "Deception", "Demolition", "Perception", "Trap disarmament"],
         "monsters": "Smuggler", "damage": ["Physical", "Fire"]},
        {"name": "Underbelly", "icon": _bp_icon("underbelly"), "description": "",
         "jobs": ["Agility", "Brute force", "Deception", "Demolition", "Engineering"],
         "monsters": "", "damage": []},
        {"name": "Laboratory", "icon": _bp_icon("laboratory"), "description": "",
         "jobs": ["Counter-thaumaturgy", "Engineering", "Deception", "Demolition", "Perception"],
         "monsters": "Scientists", "damage": ["Physical", "Chaos"]},
        {"name": "Prohibited Library", "icon": _bp_icon("prohibited_library"), "description": "",
         "jobs": ["Counter-thaumaturgy", "Deception", "Engineering", "Lockpicking", "Perception"],
         "monsters": "", "damage": []},
        {"name": "Repository", "icon": _bp_icon("repository"), "description": "",
         "jobs": ["Agility", "Demolition", "Lockpicking", "Perception", "Trap disarmament"],
         "monsters": "Constructs", "damage": ["Physical", "Fire", "Cold"]},
        {"name": "Tunnels", "icon": _bp_icon("tunnels"), "description": "",
         "jobs": ["Agility", "Brute force", "Counter-thaumaturgy", "Demolition",
                  "Engineering", "Trap disarmament"],
         "monsters": "", "damage": []},
    ],
    "jobs": [
        {"name": "Lockpicking", "icon": _bp_icon("job_lockpicking"),
         "chest_types": ["Currency", "Map Fragments", "Jewellery"]},
        {"name": "Counter-thaumaturgy", "icon": _bp_icon("job_counter_thaumaturgy"),
         "chest_types": ["Currency", "Gems", "Jewellery"]},
        {"name": "Trap disarmament", "icon": _bp_icon("job_trap_disarmament"),
         "chest_types": ["Currency", "Armour", "Weapons", "Gold"]},
        {"name": "Deception", "icon": _bp_icon("job_deception"),
         "chest_types": ["Divination Cards", "Armour"]},
        {"name": "Agility", "icon": _bp_icon("job_agility"),
         "chest_types": ["Armour", "Essences"]},
        {"name": "Perception", "icon": _bp_icon("job_perception"),
         "chest_types": ["Divination Cards", "Jewellery", "Random"]},
        {"name": "Engineering", "icon": _bp_icon("job_engineering"),
         "chest_types": ["Maps", "Uniques", "Essences", "Random"]},
        {"name": "Brute force", "icon": _bp_icon("job_brute_force"),
         "chest_types": ["Uniques", "Weapons"]},
        {"name": "Demolition", "icon": _bp_icon("job_demolition"),
         "chest_types": ["Delirium", "Blight", "Random"]},
    ],
    "chest_types": [
        {"name": "Currency", "icon": _bp_icon("chest_currency"),
         "drops": "Basic currency"},
        {"name": "Divination Cards", "icon": _bp_icon("chest_divination_cards"),
         "drops": "2x Stacked Decks, Divination Scarabs"},
        {"name": "Maps", "icon": _bp_icon("chest_maps"),
         "drops": "Maps, basic currency usable with maps, Cartography Scarabs"},
        {"name": "Map Fragments", "icon": _bp_icon("chest_map_fragments"),
         "drops": "Scarabs, Sacrifice/Offering fragments, small chance for valuable map fragments"},
        {"name": "Gems", "icon": _bp_icon("chest_gems"),
         "drops": "Skill gems (may have levels/quality), Gemcutter's Prisms"},
        {"name": "Uniques", "icon": _bp_icon("chest_uniques"),
         "drops": "Unique items, Titanic Scarabs"},
        {"name": "Jewellery", "icon": _bp_icon("chest_jewellery"),
         "drops": "Rings, amulets, jewels, belts (some veiled/fractured/corrupted/influenced), "
                  "jewellery divination cards"},
        {"name": "Armour", "icon": _bp_icon("chest_armour"),
         "drops": "Armour (some veiled/fractured/20% quality/influenced/unique), "
                  "armour divination cards and currency"},
        {"name": "Weapons", "icon": _bp_icon("chest_weapons"),
         "drops": "Weapons (some veiled/fractured/20% quality/influenced/unique), "
                  "weapon divination cards and currency"},
        {"name": "Delirium", "icon": _bp_icon("chest_delirium"),
         "drops": "Simulacrum Splinters, cluster jewels, delirium orbs, maps with delirium layers"},
        {"name": "Gold", "icon": f"{CDN}/Currency/Ruthless/CoinPileTier3.png",
         "drops": "Gold"},
        {"name": "Blight", "icon": _bp_icon("chest_blight"),
         "drops": "Oils, Blighted Maps, Blight Scarabs, maps with a Blight encounter"},
        {"name": "Essences", "icon": _bp_icon("chest_essences"),
         "drops": "Essences, Essence Scarabs"},
        {"name": "Random", "icon": _bp_icon("chest_random"),
         "drops": "Items that can drop from any reward chest type"},
    ],
    "mechanics": [
        {"name": "Infiltration", "icon": None,
         "description": "Initial phase. A few guards and patrols are present. "
                        "Opening chests raises the Alert Level.",
         "tips": []},
        {"name": "Imminent Lockdown", "icon": None,
         "description": "Starts once Alert is maxed. A countdown (default 22s) begins before "
                        "Lockdown; opening chests during this phase reduces the timer by 3s.",
         "tips": []},
        {"name": "Lockdown", "icon": None,
         "description": "Triggered once the target is taken or the countdown expires. More enemies "
                        "spawn, unopened chests lock, and some doors/obstacles rearm.",
         "tips": []},
        {"name": "Revealing wings/rooms", "icon": None,
         "description": "Blueprints start with only one wing revealed. Whakano, Niles, or Gianna can "
                        "use Blueprint Reveals plus Rogue's Markers to reveal more wings and reward "
                        "rooms before planning.",
         "tips": []},
    ],
}

CATEGORIES = ("locations", "jobs", "chest_types", "mechanics")

_CACHE_FILE = get_data_path(c.blueprint_info_cache_file_name)
_lock = threading.Lock()


def _is_valid(data):
    return isinstance(data, dict) and all(
        isinstance(data.get(key), list) for key in CATEGORIES
    )


def _read_cache():
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if _is_valid(data) else None
    except Exception:
        return None


def _cache_is_fresh():
    try:
        return time.time() - os.path.getmtime(_CACHE_FILE) < CACHE_MAX_AGE_SECONDS
    except OSError:
        return False


def load_blueprint_info():
    """Fast, offline: cached remote copy if present, else built-in data."""
    return _read_cache() or DEFAULT_BLUEPRINT_INFO


def refresh_blueprint_info(force=False, timeout=8):
    """
    Fetch the remote JSON and update the cache. Returns the new data, or None
    if nothing changed / the fetch failed. Safe to call from a worker thread.
    A missing remote file never breaks anything; the cache/defaults stay used.
    """
    if not force and _cache_is_fresh():
        return None

    with _lock:
        try:
            with urllib.request.urlopen(c.blueprint_info_url, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            if getattr(c, "DEBUGGING", False):
                print(f"[BlueprintInfo] Remote fetch failed: {e}")
            return None

        if not _is_valid(data):
            print("[BlueprintInfo] Remote JSON has an unexpected format; ignoring.")
            return None

        try:
            with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return data


class BlueprintIndex:
    """Normalized view of the data with cross-links worked out."""

    def __init__(self, data):
        self.data = data
        self.category_icons = data.get("category_icons", {}) or {}
        self.entries = {
            cat: [e for e in data.get(cat, []) if isinstance(e, dict) and e.get("name")]
            for cat in CATEGORIES
        }
        self.by_name = {
            cat: {e["name"]: e for e in entries}
            for cat, entries in self.entries.items()
        }

        jobs = self.by_name["jobs"]

        # chest type -> jobs that open it
        self.jobs_for_chest = {}
        for job in self.entries["jobs"]:
            for chest in job.get("chest_types", []) or []:
                self.jobs_for_chest.setdefault(chest, []).append(job["name"])

        # job -> locations using it
        self.locations_for_job = {}
        for loc in self.entries["locations"]:
            for job in loc.get("jobs", []) or []:
                self.locations_for_job.setdefault(job, []).append(loc["name"])

        # location -> chest types reachable through its jobs
        self.chests_for_location = {}
        for loc in self.entries["locations"]:
            chests = []
            for job in loc.get("jobs", []) or []:
                for chest in (jobs.get(job, {}).get("chest_types") or []):
                    if chest not in chests:
                        chests.append(chest)
            self.chests_for_location[loc["name"]] = chests

    def best_locations_for_chest(self, chest):
        """Locations ranked by how many of their jobs can open this chest type."""
        openers = set(self.jobs_for_chest.get(chest, []))
        scored = []
        for loc in self.entries["locations"]:
            count = sum(1 for job in loc.get("jobs", []) or [] if job in openers)
            if count:
                scored.append((loc["name"], count))
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        return scored

    def icon_url(self, category, name):
        entry = self.by_name.get(category, {}).get(name)
        url = entry.get("icon") if entry else None
        return url or self.category_icons.get(category)
