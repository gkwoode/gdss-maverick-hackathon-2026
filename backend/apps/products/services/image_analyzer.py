"""
image_analyzer.py
-----------------
Primary attribute-extraction service for the 13-column IMDB schema.

Strategy (in priority order):
  1. OpenAI GPT-4o Vision — structured JSON extraction of all 13 IMDB fields.
  2. pyzbar — dedicated barcode decoder (supplements VLM barcode result).
  3. pytesseract OCR fallback — when no OpenAI key is configured.
"""

import base64
import json
import logging
import os
import re
from io import BytesIO
from typing import Any

from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a product-data extraction specialist. "
    "Extract ONLY what is explicitly printed and clearly legible "
    "in the image. "
    "Your #1 rule: return null for any field you are not certain about. "
    "A null is always better than a wrong value. "
    "Never invent, assume, or carry knowledge from other products "
    "into your answer."
)

_EXTRACTION_PROMPT = """Extract the 13 product attributes from this image.

Return EXACTLY this JSON — field values AND a nested confidence object:

{
  "item_name": <string | null>,
  "barcode": <string | null>,
  "manufacturer": <string | null>,
  "brand": <string | null>,
  "weight": <string | null>,
  "packaging_type": <string | null>,
  "country": <string | null>,
  "variant": <string | "">,
  "product_type": <string | null>,
  "fragrance_flavor": <string | "">,
  "promotion": <string | "">,
  "addons": <string | "">,
  "tagline": <string | "">,
  "confidence": {
    "item_name": 0.0,
    "barcode": 0.0,
    "manufacturer": 0.0,
    "brand": 0.0,
    "weight": 0.0,
    "packaging_type": 0.0,
    "country": 0.0,
    "variant": 0.0,
    "product_type": 0.0,
    "fragrance_flavor": 0.0,
    "promotion": 0.0,
    "addons": 0.0,
    "tagline": 0.0
  }
}

── FIELD RULES ──────────────────────────────────────────────────────────────

item_name   : Full product name. FIRST check any sticker/label at the bottom
              of the image — that is the canonical source. Read it verbatim.
              If no bottom label, read from the main pack. null if uncertain.

barcode     : Barcode digits ONLY (8–14 digits, no spaces or dashes).
              null if barcode is not clearly readable — do NOT guess digits.

manufacturer: Exact company name from "Manufactured by" / "Made by" text.
              null if not printed on this image.

brand       : Primary brand name as printed on the front face. null if not
              clearly legible.

weight      : Net weight or volume in UPPERCASE. Format rules:
                Single-char units (G, L): no space → 250G, 2L
                Multi-char units (KG, ML, OZ): space → 1.5 KG, 500 ML
              null if not visible.

packaging_type: Choose EXACTLY ONE from this list (or null if ambiguous):
              TUB, GLASS JAR, SACHET, BOTTLE, CAN, BOX, BAG, POUCH,
              TETRA PAK, TUBE, JAR

country     : Country from an explicit "Made in X" or "Packed in X" statement.
              null if no such statement is visible.

variant     : Variant label printed on pack (ORIGINAL, LOW FAT, LIGHT, etc.).
              "" if no variant label exists.

product_type: Category in UPPERCASE (MARGARINE, BUTTER, JUICE, OIL, MILK …).
              Only use what is clearly identifiable from the image. null if
              you cannot determine it from visible text alone.

fragrance_flavor: ONLY actual flavours or scents (STRAWBERRY, VANILLA …).
              Do NOT put variant names here. "" if no specific flavour/scent.

promotion   : Verbatim on-pack promotion text. "" if none.
addons      : Included extras (e.g. SPOON INCLUDED). "" if none.
tagline     : Short slogan/tagline printed on pack. "" if none.

── CONFIDENCE RULES ─────────────────────────────────────────────────────────

Rate each field 0.0–1.0:
  0.9–1.0  Clearly legible, no doubt
  0.6–0.9  Readable but slightly obscured
  0.3–0.6  Partially visible or requires inference
  0.0–0.3  Mostly guessing

If your confidence for a nullable field (item_name, barcode, manufacturer,
brand, weight, packaging_type, country, product_type) is below 0.5,
set that field to null — do not return a low-confidence guess.
"""

# ---------------------------------------------------------------------------
# Canonical 13 IMDB fields
# ---------------------------------------------------------------------------
IMDB_FIELDS = [
    "item_name",
    "barcode",
    "manufacturer",
    "brand",
    "weight",
    "packaging_type",
    "country",
    "variant",
    "product_type",
    "fragrance_flavor",
    "promotion",
    "addons",
    "tagline",
]

# Fields that should default to "" (empty string) rather than null when absent
EMPTY_STRING_FIELDS = {
    "variant", "fragrance_flavor", "promotion", "addons", "tagline"
}


def _preprocess_image(image_bytes: bytes) -> bytes:
    """Resize and mildly sharpen the image before sending to the model."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    max_side = 1024  # sufficient for label text; smaller = faster upload
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)  # ~30% smaller than q=92
    return buf.getvalue()


def _empty_result() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for f in IMDB_FIELDS:
        result[f] = "" if f in EMPTY_STRING_FIELDS else None
    result["confidence"] = {f: 0.0 for f in IMDB_FIELDS}
    result["method"] = "none"
    return result


# ---------------------------------------------------------------------------
# Barcode extraction via pyzbar
# ---------------------------------------------------------------------------

def extract_barcode_pyzbar(image_bytes: bytes) -> str | None:
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        decoded = pyzbar_decode(img)
        if decoded:
            return decoded[0].data.decode("utf-8")
    except Exception as exc:
        logger.debug("pyzbar failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# OCR fallback (pytesseract)
# ---------------------------------------------------------------------------

def _ocr_fallback(image_bytes: bytes) -> dict[str, Any]:
    try:
        import pytesseract
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        text = pytesseract.image_to_string(img)
    except Exception as exc:
        msg = str(exc).lower()
        if "tesseract is not installed" in msg or "not in your path" in msg:
            logger.warning(
                "Tesseract OCR is not available (%s). "
                "Install it to enable the OCR fallback: "
                "Windows -> https://github.com/UB-Mannheim/tesseract/wiki ; "
                "Linux -> sudo apt install tesseract-ocr ; "
                "macOS -> brew install tesseract",
                exc,
            )
        else:
            logger.warning("pytesseract OCR failed: %s", exc)
        return _empty_result()

    result = _empty_result()
    result["method"] = "ocr"

    # Weight — e.g. "500 ml", "250g", "1.5 KG"
    weight_match = re.search(
        r"\b(\d+(?:[.,]\d+)?)\s*(ml|ML|l|L|g|G|kg|KG|oz|OZ|lb|LB)\b", text
    )
    if weight_match:
        amt = weight_match.group(1).replace(",", ".")
        unit = weight_match.group(2).upper()
        # Space before multi-char units
        result["weight"] = f"{amt} {unit}" if len(unit) > 1 else f"{amt}{unit}"
        result["confidence"]["weight"] = 0.5

    # Barcode via pyzbar
    barcode = extract_barcode_pyzbar(image_bytes)
    if barcode:
        result["barcode"] = barcode
        result["confidence"]["barcode"] = 0.95

    # Country of manufacture
    country_match = re.search(
        r"(?:Made|Manufactured|Produced|Packed)\s+in\s+([A-Za-z ]{2,30})",
        text, re.IGNORECASE
    )
    if country_match:
        result["country"] = country_match.group(1).strip().title()
        result["confidence"]["country"] = 0.6

    return result


# ---------------------------------------------------------------------------
# GPT-4o Vision extraction
# ---------------------------------------------------------------------------

def _gpt4o_extract(image_bytes: bytes) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _EXTRACTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=700,
        temperature=0.0,
    )

    raw = json.loads(response.choices[0].message.content)

    # Use the model's own per-field confidence scores.
    # Fall back to 0.7 (not 0.92) if the model omitted the key.
    model_conf = raw.pop("confidence", None)
    if isinstance(model_conf, dict):
        conf = {f: float(model_conf.get(f, 0.0)) for f in IMDB_FIELDS}
    else:
        conf = {
            f: 0.7 if raw.get(f) not in (None, "") else 0.0
            for f in IMDB_FIELDS
        }

    # Safety net: null out any nullable field the model rated below 0.5.
    # This enforces the prompt rule in code even if the model slips.
    nullable = set(IMDB_FIELDS) - EMPTY_STRING_FIELDS
    for field in nullable:
        if conf.get(field, 0.0) < 0.5 and raw.get(field) is not None:
            raw[field] = None
            conf[field] = 0.0

    raw["confidence"] = conf
    raw["method"] = "gpt4o"
    return raw


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_image(image_bytes: bytes) -> dict[str, Any]:
    """
    Run the full extraction pipeline on raw image bytes.

    Returns a dict with keys matching IMDB_FIELDS plus:
      - ``confidence``: per-field confidence dict
      - ``method``: which extraction method succeeded
    """
    processed = _preprocess_image(image_bytes)

    try:
        result = _gpt4o_extract(processed)
        logger.info("GPT-4o extraction succeeded")
    except Exception as exc:
        logger.warning("GPT-4o extraction failed (%s); falling back to OCR", exc)
        result = _ocr_fallback(processed)

    # pyzbar always overrides barcode — more reliable than vision for barcodes
    if not result.get("barcode"):
        barcode = extract_barcode_pyzbar(processed)
        if barcode:
            result["barcode"] = barcode
            result.setdefault("confidence", {})["barcode"] = 0.98

    # Ensure confidence dict has all keys and all IMDB fields are present
    conf = result.get("confidence", {})
    for field in IMDB_FIELDS:
        if field not in conf:
            conf[field] = 0.0 if result.get(field) in (None, "") else 0.5
        if field not in result:
            result[field] = "" if field in EMPTY_STRING_FIELDS else None
    result["confidence"] = conf

    return result
