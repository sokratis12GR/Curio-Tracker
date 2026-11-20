import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from top_values import available_types, rank_curios, sort_rows

CURRENCY = {
    "Replica Headhunter": {"chaos": "5000", "divine": "25"},
    "Divine Orb": {"chaos": "200", "divine": "1"},
    "Ambush Scarab": {"chaos": "3", "divine": ""},
    "Worthless Thing": {"chaos": "", "divine": ""},
}
TYPES = {
    "Replica Headhunter": "Replica",
    "Divine Orb": "Currency",
    "Ambush Scarab": "Scarab",
    "Worthless Thing": "Scarab",
}
TIERS = {"Replica Headhunter": {"tier": "1"}, "Divine Orb": {"tier": "3"}}


def test_sorted_by_chaos_and_unpriced_dropped():
    names = [r["name"] for r in rank_curios(CURRENCY, TYPES, TIERS)]
    assert names == ["Replica Headhunter", "Divine Orb", "Ambush Scarab"]


def test_tier_only_for_replica_and_replacement():
    rows = {r["name"]: r for r in rank_curios(CURRENCY, TYPES, TIERS)}
    assert rows["Replica Headhunter"]["tier"] == "1"
    assert rows["Divine Orb"]["tier"] == ""


def test_filters_and_limit():
    assert [r["name"] for r in rank_curios(CURRENCY, TYPES, type_filter="Scarab")] == ["Ambush Scarab"]
    assert [r["name"] for r in rank_curios(CURRENCY, TYPES, search="orb")] == ["Divine Orb"]
    assert len(rank_curios(CURRENCY, TYPES, limit=1)) == 1


def test_mirror_excluded():
    currency = {**CURRENCY, "Mirror Of Kalandra": {"chaos": "90000", "divine": "450"}}
    types = {**TYPES, "Mirror Of Kalandra": "Currency"}
    assert "Mirror Of Kalandra" not in [r["name"] for r in rank_curios(currency, types)]


def test_available_types():
    assert available_types(CURRENCY, TYPES) == ["Currency", "Replica", "Scarab"]


def test_rank_kept_after_resort():
    rows = sort_rows(rank_curios(CURRENCY, TYPES, TIERS), "name")
    assert [(r["name"], r["rank"]) for r in rows] == [
        ("Ambush Scarab", 3), ("Divine Orb", 2), ("Replica Headhunter", 1)]


def test_tier_sort_puts_blank_last():
    rows = [{"tier": ""}, {"tier": "2"}, {"tier": "1"}]
    assert [r["tier"] for r in sort_rows(rows, "tier")] == ["1", "2", ""]
    assert [r["tier"] for r in sort_rows(rows, "tier", descending=True)] == ["2", "1", ""]
