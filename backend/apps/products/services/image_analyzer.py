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
    "You are an expert product-label analyst for a retail company. "
    "Your job is to read product images and extract structured data for "
    "an Item Master Database (IMDB). Be precise; only report what is "
    "clearly visible on the label. Never hallucinate brand names, weights, "
    "barcodes, or countries. If a field is not visible, return null."
)

_EXTRACTION_PROMPT = """Analyze the product image and return a single JSON object with EXACTLY these keys:

{
  "item_name": "<full descriptive product name as it would appear in a retail catalog, e.g. 'Blue Band Margarine Original 500G Tub'>",
  "barcode": "<numeric barcode as printed — digits only, no spaces or dashes — or null>",
  "manufacturer": "<full legal name of the manufacturing company, or null>",
  "brand": "<brand name as printed on the label, or null>",
  "weight": "<net weight or volume with unit in UPPERCASE — examples: '250G', '430G', '1.5 KG', '500 ML', '1L' — or null>",
  "packaging_type": "<packaging form in UPPERCASE: TUB | GLASS JAR | SACHET | BOTTLE | CAN | BOX | BAG | POUCH | TETRA PAK | TUBE | JAR | or null>",
  "country": "<country of manufacture or packing as printed on label, or null>",
  "variant": "<product variant if applicable, e.g. 'ORIGINAL', 'LOW FAT', 'LIGHT' — empty string '' if not applicable>",
  "product_type": "<short product type / category, e.g. 'MARGARINE', 'MAYONNAISE', 'BUTTER', 'YOGHURT', 'JUICE' — or null>",
  "fragrance_flavor": "<flavor or fragrance if applicable, e.g. 'STRAWBERRY', 'VANILLA', 'RICH' — empty string '' if not applicable>",
  "promotion": "<on-pack promotion text verbatim, e.g. '50% OFF', 'BUY 2 GET 1 FREE' — empty string '' if none visible>",
  "addons": "<additional features or pack contents, e.g. 'SPOON INCLUDED', 'FREE RECIPE BOOK' — empty string '' if none>",
  "tagline": "<short promotional or descriptive tagline printed on the pack, or empty string '' if none>",
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

Rules:
- Confidence values must be floats between 0 and 1.
- Use null (JSON null, not empty string) for fields you truly cannot determine.
- Use empty string "" for VARIANT, FRAGRANCE_FLAVOR, PROMOTION, ADDONS, TAGLINE when not applicable.
- Weight must be UPPERCASE with no space for single-letter units (250G, 500ML) and a space before multi-letter units (1.5 KG, 500 ML).
- Do not guess; if a value is ambiguous, set confidence ≤ 0.4.
- The image tag at the bottom of the image often contains the product name — use it.
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
EMPTY_STRING_FIELDS = {"variant", "fragrance_flavor", "promotion", "addons", "tagline"}


def _preprocess_image(image_bytes: bytes) -> bytes:
    """Resize and mildly sharpen the image before sending to the model."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    max_side = 1600
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
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
        max_tokens=1024,
        temperature=0.1,
    )

    raw = json.loads(response.choices[0].message.content)
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
