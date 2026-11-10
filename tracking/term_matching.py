import time
from collections import defaultdict
from typing import List, Dict

import config as c
import ocr_utils as utils
from load_utils import get_datasets
from logger import log_message
from tracking.ocr_capture import ocr_from_image
from tracking.recent_terms import is_duplicate_recent_entry

non_dup_count = 0

datasets = get_datasets()
term_types = datasets["terms"]
all_terms = set(term_types.keys())
experimental_items = datasets["experimental"]
body_armors = datasets["body_armors"]

PRECOMP_TERMS = []
for term in all_terms:
    cleaned = utils.remove_possessive_s(term)
    normalized_term = utils.normalize_for_search(cleaned)
    term_type = term_types.get(term, "")
    term_type_cmp = utils.smart_title_case(term_type) if isinstance(term_type, str) else ""
    enchant_parts = None

    if ";" in cleaned and term_type_cmp in (c.ARMOR_ENCHANT_TYPE, c.WEAPON_ENCHANT_TYPE):
        enchant_parts = tuple(
            utils.normalize_for_search(utils.smart_title_case(part.strip()))
            for part in cleaned.split(";", 1)
        )

    PRECOMP_TERMS.append((
        term,
        normalized_term,
        enchant_parts,
        term_type_cmp
    ))


def build_enchant_type_lookup(term_types):
    lookup = defaultdict(set)
    for raw_term, type_name in term_types.items():
        norm = utils.normalize_for_search(utils.smart_title_case(raw_term))  # full term
        lookup[norm].add(type_name)
    return lookup


enchant_type_lookup = build_enchant_type_lookup(term_types)


#################################################
# Check if a term or combo term is in the text. #
#################################################
def is_term_match(normalized_term, normalized_lines, enchant_parts=None) -> bool:
    # --- Handle Enchant Combos ---
    if enchant_parts is not None:
        part1, part2 = enchant_parts

        for i, line in enumerate(normalized_lines):
            if part1 in line or part2 in line:
                # Look ahead 2 lines for the other part
                for j in range(1, 3):
                    if i + j < len(normalized_lines):
                        if (part1 in line and part2 in normalized_lines[i + j]) or (
                                part2 in line and part1 in normalized_lines[i + j]):
                            if c.DEBUGGING:
                                log_message(
                                    f"[EnchantCombo] Found combo '{part1}' & '{part2}' at lines {i} and {i + j}")
                            return True
        return False

    # --- Standard Term Matching ---
    return any(normalized_term in line for line in normalized_lines)


#################################################
# Gets all matched terms from the list          #
#################################################
def get_matched_terms(text, allow_dupes=False) -> List[Dict]:
    global non_dup_count

    all_candidates = []

    text_clean = utils.remove_possessive_s(text)
    normalized_lines = tuple(
        utils.normalize_for_search(line)
        for line in text_clean.splitlines()
    )

    for original_term, normalized_term, enchant_parts, _ in PRECOMP_TERMS:
        if is_term_match(normalized_term, normalized_lines, enchant_parts):
            duplicate = is_duplicate_recent_entry(original_term)
            all_candidates.append((original_term, duplicate))

    #########################################################################################
    # SPECIFICALLY FOR ENCHANTS TO NOT COUNT TWICE FOR MATCHES i.e                          #
    # "8% Increased Explicit Ailment Modifier Magnitudes" and                               #
    # "8% Increased Explicit Ailment Modifier Magnitudes; Has 1 White Socket"               #
    # if it contains "Has 1 White Socket" it will write it/save it as the 2nd one instead   #
    #########################################################################################
    suppress_parts = set()
    full_enchant_terms = set()
    for term_title, _ in all_candidates:
        if ";" in term_title and (term_types.get(term_title) in (c.ARMOR_ENCHANT_TYPE, c.WEAPON_ENCHANT_TYPE)):
            part1, part2 = [utils.smart_title_case(p.strip()) for p in term_title.split(";", 1)]
            suppress_parts.add(part1)
            suppress_parts.add(part2)
            full_enchant_terms.add(term_title)

    if suppress_parts and not full_enchant_terms and c.DEBUGGING:
        log_message("[Suppress] Found sub-parts to suppress but no full enchant terms present")

    ############################################################
    # Group candidates by term type and filter by match length #
    ############################################################
    sorted_terms = sorted(all_candidates, key=lambda x: len(x[0]), reverse=True)
    final_matches = []
    seen = set()

    for term_title, duplicate in sorted_terms:
        # Skip shorter terms already covered by a longer kept match
        if any(term_title in existing for existing in seen):
            continue  # do not add it at all

        seen.add(term_title)
        final_matches.append((term_title, duplicate))

    #######################################
    # Final filtering of suppressed terms #
    #######################################
    matched = []

    for term_title, duplicate in final_matches:
        if term_title in suppress_parts and term_title not in full_enchant_terms:
            continue

        armor_flag = False
        weapon_flag = False

        item_type = term_types.get(term_title)
        base_part = term_title.split(";", 1)[0].strip()
        norm_key = utils.normalize_for_search(utils.smart_title_case(base_part))
        possible_types = enchant_type_lookup.get(norm_key, [])

        # Only assign flags if item_type is an enchant type
        if item_type in (c.ARMOR_ENCHANT_TYPE, c.WEAPON_ENCHANT_TYPE):
            if possible_types:
                if all(t == c.ARMOR_ENCHANT_TYPE for t in possible_types):
                    armor_flag = True
                elif all(t == c.WEAPON_ENCHANT_TYPE for t in possible_types):
                    weapon_flag = True
                else:
                    # Term exists in both armor and weapon types
                    # Use proximity logic to disambiguate
                    if utils.is_armor_enchant_by_body_armor_order(term_title, text, body_armors, enchant_type_lookup):
                        armor_flag = True
                    else:
                        weapon_flag = True
        else:
            # For non-enchant types, force flags false
            armor_flag = False
            weapon_flag = False

        # Append result, respecting duplicate flags and allowance
        if allow_dupes or not duplicate:
            non_dup_count += 1
            matched.append({
                "term": term_title,
                "duplicate": False,
                "armor_enchant_flag": armor_flag,
                "weapon_enchant_flag": weapon_flag,
            })
        else:
            matched.append({
                "term": term_title,
                "duplicate": True,
                "armor_enchant_flag": armor_flag,
                "weapon_enchant_flag": weapon_flag,
            })

    return matched


#############################################################################
# Attempts to recover missed terms using fuzzy OCR matching against the      #
# actual terms dataset. Duplicate handling and match metadata remain here    #
# because they depend on the current application state.                     #
#                                                                           #
#    Args:                                                                  #
#        text (str): OCR text returned from the enlarged review capture.     #
#        allow_dupes (bool): Whether duplicate matches should be allowed.    #
#        threshold (float): Minimum similarity required for fuzzy matching.  #
#                                                                           #
#    Returns:                                                               #
#        list: Matched term dictionaries using the same format as the normal #
#              get_matched_terms() function.                                #
#############################################################################
def get_review_fuzzy_matches(text, allow_dupes=False, threshold=None) -> List[Dict]:
    global non_dup_count

    if threshold is None:
        threshold = c.FUZZY_THRESHOLD

    matched = []
    rejected = []

    fuzzy_matches = utils.find_review_fuzzy_terms(
        text,
        PRECOMP_TERMS,
        threshold=threshold,
        rejected=rejected
    )

    #############################################################
    # Always logged (not gated on DEBUGGING) so misfires can be #
    # diagnosed from a user's normal log file.                  #
    #############################################################
    for near_miss in sorted(rejected, key=lambda m: m["similarity"], reverse=True):
        log_message(
            f"[OCR FUZZY] "
            f"Rejected '{near_miss['term']}' "
            f"against '{near_miss['candidate']}' | "
            f"similarity={near_miss['similarity']:.3f} | "
            f"reason={near_miss['reason']}"
        )

    for fuzzy_match in fuzzy_matches:
        original_term = fuzzy_match["term"]
        best_line = fuzzy_match["candidate"]
        best_ratio = fuzzy_match["similarity"]

        duplicate = is_duplicate_recent_entry(
            original_term
        )

        if allow_dupes or not duplicate:
            non_dup_count += 1

            matched.append({
                "term": original_term,
                "duplicate": False,
                "armor_enchant_flag": False,
                "weapon_enchant_flag": False,
            })
        else:
            matched.append({
                "term": original_term,
                "duplicate": True,
                "armor_enchant_flag": False,
                "weapon_enchant_flag": False,
            })

        log_message(
            f"[OCR FUZZY] "
            f"Matched '{original_term}' "
            f"against '{best_line}' | "
            f"similarity={best_ratio:.3f} | "
            f"threshold={threshold:.2f}"
        )

    return matched


#############################################################################
# Reviews a failed OCR capture once again using an enlarged image.          #
# This is only called when the original OCR capture returned no matches.    #
# The enlarged pass first uses normal matching, then falls back to fuzzy    #
# matching against the actual terms dataset if necessary.                   #
#                                                                           #
#    Args:                                                                  #
#        image_np (np.ndarray): The original captured image as NumPy array. #
#        scale (int): Scale factor used for the second OCR pass.             #
#        allow_dupes (bool): Whether duplicate matches should be allowed.    #
#                                                                           #
#    Returns:                                                               #
#        tuple: OCR text and any matched terms found during the review.      #
#############################################################################
def review_failed_capture(image_np, scale=2, allow_dupes=False, prepared_mask=None):
    review_start = time.perf_counter()

    if c.DEBUGGING:
        log_message(
            f"[OCR REVIEW] "
            f"No matches found during initial capture. "
            f"Reviewing enlarged capture at {scale}x scale..."
        )

    full_text, filtered = ocr_from_image(
        image_np,
        scale=scale,
        prepared_mask=prepared_mask
    )

    ocr_end = time.perf_counter()

    corrected_text = utils.normalize_review_ocr_text(
        full_text
    )

    correction_end = time.perf_counter()

    #############################################################
    # First attempt the exact matcher again after normalization #
    #############################################################
    matched_terms = get_matched_terms(
        corrected_text,
        allow_dupes
    )

    exact_match_end = time.perf_counter()

    #############################################################
    # Only fall back to fuzzy matching if exact matching fails  #
    #############################################################
    if not matched_terms:
        matched_terms = get_review_fuzzy_matches(
            corrected_text,
            allow_dupes=allow_dupes
        )

    fuzzy_match_end = time.perf_counter()

    if c.DEBUGGING:
        if matched_terms:
            log_message(
                f"[OCR REVIEW] "
                f"Found {len(matched_terms)} match(es) during review."
            )
        else:
            log_message(
                "[OCR REVIEW] "
                "No matches found after enlarged review."
            )

        log_message(
            f"[OCR REVIEW PERF] "
            f"ocr={(ocr_end - review_start) * 1000:.1f}ms | "
            f"correction={(correction_end - ocr_end) * 1000:.1f}ms | "
            f"exact_matching={(exact_match_end - correction_end) * 1000:.1f}ms | "
            f"fuzzy_matching={(fuzzy_match_end - exact_match_end) * 1000:.1f}ms | "
            f"total={(fuzzy_match_end - review_start) * 1000:.1f}ms"
        )

    return corrected_text, matched_terms
