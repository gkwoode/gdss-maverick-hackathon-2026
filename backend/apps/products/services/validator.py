"""
validator.py
------------
Normalisation and validation rules for the 13-column IMDB schema.
Each function accepts the raw extracted value (str | None) and returns a
cleaned value plus a boolean indicating whether it passed validation.

Weight format target: uppercase, no space for single-char units (250G),
space before multi-char units (1.5 KG, 500 ML).
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Barcode
# ---------------------------------------------------------------------------

_BARCODE_PATTERN = re.compile(r"^\d{8,14}$")


def validate_barcode(value: Optional[str]) -> tuple[Optional[str], bool]:
    if not value:
        return None, False
    cleaned = re.sub(r"[\s\-]", "", value.strip())
    return cleaned, bool(_BARCODE_PATTERN.match(cleaned))


# ---------------------------------------------------------------------------
# Weight / volume
# Normalise to UPPERCASE, space before multi-char units.
# Examples: 250G  430G  1.5 KG  500 ML
# ---------------------------------------------------------------------------

_WEIGHT_PATTERN = re.compile(
    r"^(\d+(?:[.,]\d+)?)\s*(ml|l|g|kg|oz|lb|cl|fl\s*oz)$",
    re.IGNORECASE,
)

# Maps lowercase unit → (uppercase display, space_before)
_UNIT_MAP: dict[str, tuple[str, bool]] = {
    "ml": ("ML", True),
    "l":  ("L",  False),
    "g":  ("G",  False),
    "kg": ("KG", True),
    "oz": ("OZ", True),
    "lb": ("LB", True),
    "cl": ("CL", True),
    "floz":  ("FL OZ", True),
    "fl oz": ("FL OZ", True),
}


def validate_weight(value: Optional[str]) -> tuple[Optional[str], bool]:
    if not value:
        return None, False
    cleaned = value.strip().replace(",", ".")
    match = _WEIGHT_PATTERN.match(cleaned)
    if not match:
        # Try to uppercase whatever we got
        return cleaned.upper(), False
    amount = match.group(1)
    unit_key = match.group(2).lower().replace(" ", "")
    unit_display, space = _UNIT_MAP.get(unit_key, (match.group(2).upper(), True))
    sep = " " if space else ""
    return f"{amount}{sep}{unit_display}", True


# ---------------------------------------------------------------------------
# Country
# ---------------------------------------------------------------------------

_COUNTRY_ALIASES: dict[str, str] = {
    "usa": "United States",
    "us": "United States",
    "u.s.a.": "United States",
    "u.s.": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "great britain": "United Kingdom",
    "england": "United Kingdom",
    "uae": "United Arab Emirates",
    "u.a.e.": "United Arab Emirates",
    "rsa": "South Africa",
    "south africa": "South Africa",
    "gh": "Ghana",
    "ghana": "Ghana",
    "ng": "Nigeria",
    "nigeria": "Nigeria",
    "ke": "Kenya",
    "kenya": "Kenya",
    "cn": "China",
    "china": "China",
    "prc": "China",
    "de": "Germany",
    "germany": "Germany",
    "fr": "France",
    "france": "France",
    "it": "Italy",
    "italy": "Italy",
    "es": "Spain",
    "spain": "Spain",
    "in": "India",
    "india": "India",
    "br": "Brazil",
    "brazil": "Brazil",
    "au": "Australia",
    "australia": "Australia",
    "ca": "Canada",
    "canada": "Canada",
    "jp": "Japan",
    "japan": "Japan",
    "nl": "Netherlands",
    "netherlands": "Netherlands",
    "be": "Belgium",
    "belgium": "Belgium",
    "ch": "Switzerland",
    "switzerland": "Switzerland",
    "za": "South Africa",
}


def validate_country(value: Optional[str]) -> tuple[Optional[str], bool]:
    if not value:
        return None, False
    lookup = value.strip().lower()
    normalised = _COUNTRY_ALIASES.get(lookup)
    if normalised:
        return normalised, True
    return value.strip().title(), True


# ---------------------------------------------------------------------------
# Packaging type
# ---------------------------------------------------------------------------

_PACKAGING_ALIASES: dict[str, str] = {
    "pet bottle": "BOTTLE",
    "glass bottle": "BOTTLE",
    "plastic bottle": "BOTTLE",
    "bottle": "BOTTLE",
    "tin can": "CAN",
    "aluminium can": "CAN",
    "aluminum can": "CAN",
    "tin": "CAN",
    "can": "CAN",
    "carton box": "BOX",
    "cardboard box": "BOX",
    "box": "BOX",
    "foil bag": "BAG",
    "plastic bag": "BAG",
    "bag": "BAG",
    "stand-up pouch": "POUCH",
    "doy pack": "POUCH",
    "pouch": "POUCH",
    "tetra pack": "TETRA PAK",
    "tetrapak": "TETRA PAK",
    "tetra-pak": "TETRA PAK",
    "tetra pak": "TETRA PAK",
    "sachet": "SACHET",
    "tube": "TUBE",
    "tub": "TUB",
    "jar": "JAR",
    "glass jar": "GLASS JAR",
}


def normalise_packaging(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    lookup = value.strip().lower()
    return _PACKAGING_ALIASES.get(lookup, value.strip().upper())


def normalise_text(value: Optional[str], uppercase: bool = False) -> Optional[str]:
    if not value:
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned.upper() if uppercase else cleaned


# ---------------------------------------------------------------------------
# Full record validation for the 13-column schema
# ---------------------------------------------------------------------------

def validate_and_normalise(raw: dict) -> dict:
    """
    Apply field-level validation and normalisation.
    Returns the cleaned record dict (preserving ``confidence`` and ``method`` keys).
    """
    out = dict(raw)

    out["barcode"], _ = validate_barcode(raw.get("barcode"))
    out["weight"], _ = validate_weight(raw.get("weight"))
    out["country"], _ = validate_country(raw.get("country"))
    out["packaging_type"] = normalise_packaging(raw.get("packaging_type"))

    for field in ("manufacturer", "brand", "item_name"):
        out[field] = normalise_text(raw.get(field))

    for field in ("variant", "product_type", "fragrance_flavor"):
        val = normalise_text(raw.get(field), uppercase=True)
        out[field] = val if val else ""

    for field in ("promotion", "addons", "tagline"):
        val = normalise_text(raw.get(field))
        out[field] = val if val else ""

    return out
