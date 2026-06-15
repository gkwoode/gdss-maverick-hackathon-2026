"""
aggregator.py
-------------
Merges per-image extraction results from multiple images of the same product
into a single consolidated IMDB record.

Strategy:
  - For every field: take the value with the highest confidence score.
  - For PROMOTION, ADDONS, TAGLINE: concatenate all unique non-empty values
    (different sides of the pack may show different text).
  - Overall confidence per field = max confidence across all images.
"""

from typing import Any

from .image_analyzer import EMPTY_STRING_FIELDS, IMDB_FIELDS

# Fields where we collect ALL unique non-empty values across images
_CONCAT_FIELDS = {"promotion", "addons", "tagline"}


def aggregate_extractions(results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Merge a list of per-image extraction dicts into one consolidated record.

    Args:
        results: List of dicts returned by ``analyze_image`` (after validation).
                 Each dict must contain all IMDB_FIELDS and a ``confidence`` sub-dict.

    Returns:
        A merged dict with the same structure (plus ``method`` and ``confidence``).
    """
    if not results:
        return {}

    if len(results) == 1:
        return results[0]

    merged: dict[str, Any] = {}
    merged_conf: dict[str, float] = {f: 0.0 for f in IMDB_FIELDS}

    for field in IMDB_FIELDS:
        if field in _CONCAT_FIELDS:
            # Collect all unique non-empty values
            seen: list[str] = []
            best_conf = 0.0
            for r in results:
                val = (r.get(field) or "").strip()
                conf = r.get("confidence", {}).get(field, 0.0)
                if val and val not in seen:
                    seen.append(val)
                if conf > best_conf:
                    best_conf = conf
            merged[field] = ", ".join(seen) if seen else ""
            merged_conf[field] = best_conf
        else:
            # Take the value with the highest confidence
            best_val: Any = "" if field in EMPTY_STRING_FIELDS else None
            best_conf = 0.0
            for r in results:
                val = r.get(field)
                conf = r.get("confidence", {}).get(field, 0.0)
                # Prefer non-null/non-empty values
                has_value = val is not None and val != ""
                if has_value and conf > best_conf:
                    best_val = val
                    best_conf = conf
            merged[field] = best_val
            merged_conf[field] = best_conf

    # Determine the method used (prefer gpt4o)
    methods = [r.get("method", "unknown") for r in results]
    merged["method"] = "gpt4o" if "gpt4o" in methods else methods[0]
    merged["confidence"] = merged_conf

    return merged
