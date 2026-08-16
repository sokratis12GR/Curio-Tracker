import json
import urllib.parse
import webbrowser

import config
from load_utils import get_datasets


def normalize_trade_name(name):
    if not name:
        return ""

    name = name.replace("-Attuned", "-attuned")
    name = name.replace("-Step", "-step")
    name = name.replace(" Of ", " of ")
    name = name.replace(" The ", " the ")

    return name


def normalize_enchantment_lookup_name(name):
    if not name:
        return ""

    name = str(name)

    name = name.replace("\r\n", "; ")
    name = name.replace("\n", "; ")

    parts = [
        part.strip()
        for part in name.split(";")
        if part.strip()
    ]

    return "; ".join(parts).lower()


def find_enchantment_trade(name):
    if not name:
        return None

    enchantments = get_datasets().get(
        "enchantments_trade",
        {}
    )

    normalized_name = normalize_enchantment_lookup_name(name)

    for enchant_name, data in enchantments.items():
        if normalize_enchantment_lookup_name(enchant_name) == normalized_name:
            return data

    return None


def generate_trade_url_from_values(item_type, name):
    if item_type not in (
        "Replica",
        "Experimental",
        "Replacement",
        "Enchant",
        "Armor Enchants",
        "Weapon Enchants",
    ):
        return None

    if not name:
        return None

    name = normalize_trade_name(name)

    league = config.LEAGUE

    query = {
        "query": {
            "status": {
                "option": "securable"
            },
            "stats": [
                {
                    "type": "and",
                    "filters": []
                }
            ],
            "filters": {
                "type_filters": {
                    "filters": {}
                },
                "misc_filters": {
                    "filters": {
                        "foulborn_item": {
                            "option": "false"
                        }
                    }
                }
            }
        },
        "sort": {
            "price": "asc"
        }
    }

    if item_type == "Replica":
        if not name.lower().startswith("replica "):
            name = "Replica " + name

        query["query"]["name"] = name

    elif item_type == "Replacement":
        query["query"]["name"] = name

    elif item_type == "Experimental":
        query["query"]["type"] = name

    elif item_type in (
        "Enchant",
        "Armor Enchants",
        "Weapon Enchants",
    ):
        enchant = find_enchantment_trade(name)

        if not enchant:
            print(
                f"[WARN] No trade enchantment mapping found for: {name}"
            )
            return None

        enchant_category = enchant.get("category")

        if item_type == "Armor Enchants":
            if enchant_category != "Body Armour":
                return None

        elif item_type == "Weapon Enchants":
            if enchant_category != "Any Weapon":
                return None

        stats = enchant.get("stats", [])

        if not stats:
            return None

        for stat in stats:
            stat_id = stat.get("id")

            if not stat_id:
                continue

            trade_filter = {
                "id": stat_id
            }

            value = stat.get("value")

            if value is not None:
                trade_filter["value"] = {
                    "min": value,
                    "max": value
                }

            query["query"]["stats"][0]["filters"].append(
                trade_filter
            )

    encoded_query = urllib.parse.quote(
        json.dumps(
            query,
            separators=(",", ":")
        ),
        safe=""
    )

    return (
        f"https://www.pathofexile.com/trade/search/"
        f"{urllib.parse.quote(str(league), safe='')}"
        f"?q={encoded_query}"
    )


def open_url(url):
    if not url:
        return False

    return webbrowser.open_new_tab(url)


def open_wiki(url):
    return open_url(url)


def open_trade(item_type, name):
    url = generate_trade_url_from_values(
        item_type,
        name
    )

    if not url:
        return False

    return open_url(url)