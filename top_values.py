from currency_utils import convert_to_float

TIERED_TYPES = ("Replica", "Replacement")
EXCLUDED_ITEMS = {"mirror of kalandra"}


def rank_curios(currency, term_types, tiers=None, type_filter="All", search="", limit=None):
    """Return the priced curios for one league, most valuable first.

    currency maps item name -> {"chaos", "divine", ...} as loaded for the active league.
    Each row is a dict with name, type, chaos, divine and tier (tier only for Replica/Replacement).
    """
    tiers = tiers or {}
    search = (search or "").strip().lower()
    rows = []
    for name, values in currency.items():
        if name.lower() in EXCLUDED_ITEMS:
            continue
        chaos = convert_to_float(values.get("chaos"))
        if chaos <= 0:
            continue
        item_type = term_types.get(name, "")
        if type_filter != "All" and item_type != type_filter:
            continue
        if search and search not in name.lower():
            continue
        tier = ""
        if item_type in TIERED_TYPES:
            tier = (tiers.get(name) or {}).get("tier", "") or ""
        rows.append({
            "img": (tiers.get(name) or {}).get("img") or values.get("img") or "",
            "name": name,
            "type": item_type,
            "chaos": chaos,
            "divine": convert_to_float(values.get("divine")),
            "tier": tier,
        })
    rows.sort(key=lambda r: (-r["chaos"], r["name"]))
    if limit:
        rows = rows[:limit]
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def _tier_key(tier):
    try:
        return 0, float(tier)
    except (TypeError, ValueError):
        return 1, 0.0


def sort_rows(rows, column, descending=False):
    """Sort ranked rows by a display column; rows without a tier always sort last."""
    if column == "tier":
        with_tier = [r for r in rows if _tier_key(r["tier"])[0] == 0]
        without = [r for r in rows if _tier_key(r["tier"])[0] == 1]
        with_tier.sort(key=lambda r: _tier_key(r["tier"])[1], reverse=descending)
        return with_tier + without
    if column in ("name", "type"):
        return sorted(rows, key=lambda r: r[column].lower(), reverse=descending)
    return sorted(rows, key=lambda r: r[column], reverse=descending)


def available_types(currency, term_types):
    """Return the sorted item types that have at least one priced curio."""
    return sorted({term_types.get(name) for name in currency if term_types.get(name)})
