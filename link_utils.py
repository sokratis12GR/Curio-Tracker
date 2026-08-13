import json
import urllib.parse
import webbrowser

import config


def normalize_trade_name(name):
    if not name:
        return ""

    name = name.replace("-Attuned", "-attuned")
    name = name.replace(" Of ", " of ")
    name = name.replace(" The ", " the ")

    return name


def generate_trade_url_from_values(item_type, name):
    if item_type not in ("Replica", "Experimental", "Replacement"):
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
    else:
        query["query"]["type"] = name

    encoded_query = urllib.parse.quote(
        json.dumps(query, separators=(",", ":")),
        safe=""
    )

    return (
        f"https://www.pathofexile.com/trade/search/"
        f"{urllib.parse.quote(str(league), safe='')}?q={encoded_query}"
    )


def open_url(url):
    if not url:
        return False

    return webbrowser.open_new_tab(url)


def open_wiki(url):
    return open_url(url)


def open_trade(item_type, name):
    url = generate_trade_url_from_values(item_type, name)

    if not url:
        return False

    return open_url(url)