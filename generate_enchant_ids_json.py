import json
import re
import urllib.request
from pathlib import Path

STAT_ALIASES = {
    "50% reduced Explicit Defence Modifier magnitudes": {
        "text": "#% increased Explicit Defence Modifier magnitudes",
        "value": -50,
    },
    "50% reduced Explicit Life Modifier magnitudes": {
        "text": "#% increased Explicit Life Modifier magnitudes",
        "value": -50,
    },
    "50% reduced Explicit Resistance Modifier magnitudes": {
        "text": "#% increased Explicit Resistance Modifier magnitudes",
        "value": -50,
    },

    "25% reduced Explicit Critical Modifier magnitudes": {
        "text": "#% increased Explicit Critical Modifier magnitudes",
        "value": -25,
    },
    "25% reduced Explicit Speed Modifier magnitudes": {
        "text": "#% increased Explicit Speed Modifier magnitudes",
        "value": -25,
    },
    "25% reduced Explicit Damage Modifier magnitudes": {
        "text": "#% increased Explicit Damage Modifier magnitudes",
        "value": -25,
    },

    "25% reduced Attribute Requirements": {
        "text": "#% increased Attribute Requirements",
        "value": -25,
    },
    "40% reduced Attribute Requirements": {
        "text": "#% increased Attribute Requirements",
        "value": -40,
    },

    "-3 to maximum Sockets": {
        "text": "# to maximum Sockets",
        "value": -3,
    },

    "Has 1 White Socket": {
        "text": "Has # White Sockets",
        "value": 1,
    },
}

NON_SEARCHABLE_STATS = {
    "-3 to maximum Sockets",
}

TERMS_URL = "https://sokratis.space/curio_tracker/terms.json"
TRADE_STATS_URL = "https://www.pathofexile.com/api/trade/data/stats"

OUTPUT_FILE = Path("enchantments_trade.json")

ENCHANT_CATEGORIES = {
    "Weapon Enchants": "Any Weapon",
    "Armor Enchants": "Body Armour",
}


def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CurioTracker-DatasetBuilder/1.0"
        }
    )

    with urllib.request.urlopen(
            request,
            timeout=30
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def normalize_stat(text):
    if not text:
        return ""

    text = str(text).strip()

    # Replace numeric values with trade placeholders
    text = re.sub(
        r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?",
        "#",
        text
    )

    # A little tolerance for singular/plural differences
    text = text.replace("white socket", "white sockets")
    text = text.replace("crafted modifier", "crafted modifiers")

    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def extract_numeric_value(text):
    """
    Extract the first numeric value from an enchant line.

    Examples:
        6% increased ... -> 6
        -3 to maximum Sockets -> -3
        Has 1 White Socket -> 1
        All Sockets Linked -> None
    """
    match = re.search(
        r"(?<![A-Za-z])([-+]?\d+(?:\.\d+)?)",
        text
    )

    if not match:
        return None

    value = float(match.group(1))

    if value.is_integer():
        return int(value)

    return value


def split_enchant(name):
    """
    terms.json joins multiple enchant lines using semicolons.
    Convert them back into individual searchable stats.
    """
    return [
        part.strip()
        for part in name.split(";")
        if part.strip()
    ]


def load_enchant_terms():
    data = fetch_json(TERMS_URL)

    result = []

    for entry in data:
        name = entry.get("Name", "").strip()
        type_name = entry.get("Type", "").strip()

        category = ENCHANT_CATEGORIES.get(type_name)

        if not name or not category:
            continue

        result.append({
            "name": name,
            "category": category,
        })

    return result


def load_trade_enchants():
    data = fetch_json(TRADE_STATS_URL)

    result = []

    for group in data.get("result", []):
        if group.get("label") != "Enchant":
            continue

        for entry in group.get("entries", []):
            stat_id = entry.get("id")
            text = entry.get("text")

            if not stat_id or not text:
                continue

            if not stat_id.startswith("enchant."):
                continue

            result.append({
                "id": stat_id,
                "text": text,
                "normalized": normalize_stat(text),
            })

    return result


def build_trade_lookup(trade_enchants):
    lookup = {}

    for trade in trade_enchants:
        lookup.setdefault(
            trade["normalized"],
            []
        ).append(trade)

    return lookup


def find_trade_stat(line, trade_lookup):
    alias = STAT_ALIASES.get(line)

    if alias:
        normalized = normalize_stat(alias["text"])
        forced_value = alias.get("value")
    else:
        normalized = normalize_stat(line)
        forced_value = None

    matches = trade_lookup.get(
        normalized,
        []
    )

    if not matches:
        return None, None

    if len(matches) > 1:
        print(
            f"[WARN] Multiple trade stats matched:"
            f"\n    {line}"
        )

        for match in matches:
            print(
                f"    {match['id']} -> {match['text']}"
            )

    return matches[0], forced_value


def build_mapping():
    terms = load_enchant_terms()
    trade_enchants = load_trade_enchants()

    trade_lookup = build_trade_lookup(
        trade_enchants
    )

    output = {}
    unmatched = []

    for term in terms:
        enchant_name = term["name"]
        lines = split_enchant(enchant_name)

        matched_stats = []
        failed_lines = []
        unsearchable_lines = []

        for line in lines:
            if line in NON_SEARCHABLE_STATS:
                unsearchable_lines.append(line)
                continue

            trade, forced_value = find_trade_stat(
                line,
                trade_lookup
            )

            if not trade:
                failed_lines.append(line)
                continue

            stat = {
                "id": trade["id"]
            }

            if forced_value is not None:
                value = forced_value
            else:
                value = extract_numeric_value(line)

            if value is not None:
                stat["value"] = value

            matched_stats.append(stat)

        if failed_lines:
            unmatched.append({
                "name": enchant_name,
                "category": term["category"],
                "failed_lines": failed_lines,
            })
            continue

        entry = {
            "category": term["category"],
            "stats": matched_stats,
        }

        if unsearchable_lines:
            entry["unsearchable"] = unsearchable_lines

        output[enchant_name] = entry

    return output, unmatched


def main():
    mapping, unmatched = build_mapping()

    mapping = dict(
        sorted(
            mapping.items(),
            key=lambda x: x[0].lower()
        )
    )

    with OUTPUT_FILE.open(
            "w",
            encoding="utf-8"
    ) as f:
        json.dump(
            mapping,
            f,
            indent=4,
            ensure_ascii=False
        )

    print()
    print(f"Matched:   {len(mapping)}")
    print(f"Unmatched: {len(unmatched)}")
    print(f"Saved:     {OUTPUT_FILE.resolve()}")

    if unmatched:
        print("\nUnmatched:")

        for entry in unmatched:
            print(
                f"\n  - {entry['name']}"
            )

            for line in entry["failed_lines"]:
                print(
                    f"      FAILED: {line}"
                )
                print(
                    f"      NORMALIZED: "
                    f"{normalize_stat(line)}"
                )


if __name__ == "__main__":
    main()
