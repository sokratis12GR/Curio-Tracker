import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as c
import ocr_utils as utils

TERMS = {
    "Infernal Blade": c.EXPERIMENTAL_TYPE,
    "Psychotic Axe": c.EXPERIMENTAL_TYPE,
    "Disapprobation Axe": c.EXPERIMENTAL_TYPE,
    "Apex Cleaver": c.EXPERIMENTAL_TYPE,
    "Honed Cleaver": c.EXPERIMENTAL_TYPE,
    "Headhunter": c.REPLICA_TYPE,
    "Abyssus": c.REPLICA_TYPE,
    "Breach Scarab of the Hive": c.SCARAB_TYPE,
    "Orb of Annulment": c.CURRENCY_TYPE,
    "8% increased Explicit Speed Modifier magnitudes": c.WEAPON_ENCHANT_TYPE,
}


def build_precomp(terms):
    precomp = []
    for term, term_type in terms.items():
        normalized = utils.normalize_for_search(utils.remove_possessive_s(term))
        precomp.append((term, normalized, None, term_type))
    return precomp


PRECOMP = build_precomp(TERMS)

# OCR-like text of a Storm Beak / Infernal Axe capture,
# with the enchant line obstructed.
STORM_BEAK_TEXT = """Curio Display
Storm Beak
Infernal Axe
One Handed Axe
Physical Damage: 69-115
Critical Strike Chance: 5.00%
Attacks Per Second: 1.30
Weapon Range: 1.1 Metres
Requires Level 69, 158 Str, 76 Dex
+2 To Level Of Socketed Melee Gems
32% Increased Physical Damage
Adds 1 To 2 Physical Damage
Contraband"""


def match(text):
    rejected = []
    found = utils.find_review_fuzzy_terms(text, PRECOMP, rejected=rejected)
    return [m["term"] for m in found], rejected


class FuzzyMatchingTests(unittest.TestCase):
    def test_infernal_axe_does_not_match_infernal_blade(self):
        found, rejected = match(STORM_BEAK_TEXT)
        self.assertEqual(found, [])
        reasons = {r["term"]: r["reason"] for r in rejected}
        self.assertEqual(reasons.get("Infernal Blade"), "word_mismatch")

    def test_garbled_experimental_still_matches(self):
        self.assertEqual(match("Storm Beak\nInfernai Blade")[0], ["Infernal Blade"])
        self.assertEqual(match("Psychotlc Axe")[0], ["Psychotic Axe"])

    def test_garbled_single_word_replica_still_matches(self):
        self.assertEqual(match("Headhuntr\nLeather Belt")[0], ["Headhunter"])

    def test_garbled_multi_word_terms_still_match(self):
        self.assertEqual(match("Breach Scarab 0f the Hlve")[0], ["Breach Scarab of the Hive"])
        self.assertEqual(match("Orb of Annulrnent")[0], ["Orb of Annulment"])

    def test_enchants_never_fuzzy_matched(self):
        found, _ = match("8% increased Explicit Speed Modifier magnitudas")
        self.assertEqual(found, [])

    def test_ambiguous_tie_is_dropped(self):
        precomp = build_precomp({"Alpha Blade": c.EXPERIMENTAL_TYPE, "Alpho Blade": c.EXPERIMENTAL_TYPE})
        rejected = []
        found = utils.find_review_fuzzy_terms("Alphx Blade", precomp, rejected=rejected)
        self.assertEqual(found, [])
        self.assertTrue(all(r["reason"] == "ambiguous" for r in rejected))


if __name__ == "__main__":
    unittest.main()
