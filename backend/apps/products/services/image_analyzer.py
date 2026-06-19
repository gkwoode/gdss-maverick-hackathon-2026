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
    "You are a product-data extraction specialist for a retail IMDB system. "
    "Your goal is to capture as much accurate information as possible from "
    "product images. Extract every field you can see — partial information "
    "with a low confidence score is always better than returning null. "
    "Return null ONLY when a field is completely absent from the image. "
    "Never invent values, but do read and infer from all visible text."
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

item_name: The complete product name. Read in this order:
  1. Any sticker or label at the BOTTOM of the image — read it verbatim.
  2. If no bottom sticker, CONSTRUCT the name from visible pack text:
       Brand + product description + weight + packaging type
       Example: brand="Cowbell", desc="Powdered Milk", weight="400G",
       pack="TIN" → "Cowbell Powdered Milk 400G Tin"
  3. If only brand is visible: "BrandName product" is acceptable.
  DO NOT return null unless the image contains no product name information
  at all. Even a partial name is better than null.

barcode: Barcode digits ONLY (8–14 digits, no spaces or dashes).
  null only if barcode is entirely unreadable.

manufacturer: Exact company name from "Manufactured by" / "Made by" text.
  null if not printed on this image.

brand: Primary brand name as printed. Look for the largest/most prominent
  text on the front face. null only if completely invisible.

weight: Net weight or volume in UPPERCASE. Format:
    Single-char units (G, L): no space → 250G, 2L
    Multi-char units (KG, ML, OZ): space → 1.5 KG, 500 ML
  null if not visible.

packaging_type: Choose EXACTLY ONE (or null if truly ambiguous):
  TUB, GLASS JAR, SACHET, BOTTLE, CAN, BOX, BAG, POUCH,
  TETRA PAK, TUBE, JAR

country: Country from an explicit "Made in X" or "Packed in X" statement.
  null if no such statement is visible.

variant: Variant printed on pack (ORIGINAL, LOW FAT, LIGHT, FULL CREAM …).
  "" if none.

product_type: Product category UPPERCASE. Infer from the product description,
  brand, or category text on the label.
  Examples: MARGARINE, BUTTER, JUICE, OIL, MILK, JAM, SAUCE, YOGHURT.
  null only if completely unclear.

fragrance_flavor: ONLY actual flavours or scents (STRAWBERRY, VANILLA …).
  Do NOT put variant names here. "" if none.

promotion: Verbatim on-pack promotion text. "" if none.
addons: Included extras (e.g. SPOON INCLUDED). "" if none.
tagline: Short slogan/tagline printed on pack. "" if none.

── CONFIDENCE RULES ─────────────────────────────────────────────────────────

Rate each field 0.0–1.0 based on how clearly you can see the value:
  0.9–1.0  Clearly legible, 100% certain
  0.6–0.9  Readable but slightly obscured or partially cut off
  0.3–0.6  Partially visible, requires some inference from context
  0.0–0.3  Barely visible or highly uncertain

A confidence of 0.3 with a value is BETTER than null when some
information is visible. Return null ONLY when there is no information
to extract for that field from this image.
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

# Fields that default to "" (empty string) rather than null when absent
EMPTY_STRING_FIELDS = {
    "variant", "fragrance_flavor", "promotion", "addons", "tagline"
}

# Keywords for OCR-based product_type detection
_PRODUCT_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("MARGARINE", ["margarine"]),
    ("BUTTER", ["butter"]),
    ("MAYONNAISE", ["mayonnaise", "mayo"]),
    ("YOGHURT", ["yoghurt", "yogurt"]),
    ("MILK", ["milk", "powdered milk", "evaporated milk"]),
    ("JUICE", ["juice", "nectar"]),
    ("OIL", ["cooking oil", "vegetable oil", "palm oil", "sunflower oil"]),
    ("JAM", ["jam", "jelly", "preserve"]),
    ("SAUCE", ["sauce", "ketchup", "tomato paste"]),
    ("CHEESE", ["cheese"]),
    ("CREAM", ["cream", "sour cream", "whipping cream"]),
    ("SUGAR", ["sugar", "icing sugar"]),
    ("FLOUR", ["flour", "wheat flour"]),
    ("SALT", ["salt", "table salt"]),
    ("BISCUIT", ["biscuit", "cookie", "crackers"]),
    ("CHOCOLATE", ["chocolate"]),
    ("BEVERAGE", ["beverage", "drink", "energy drink"]),
]


def _preprocess_image(image_bytes: bytes) -> bytes:
    """Resize and enhance the image before sending to the model."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    # 1400px preserves fine-print legibility (country, manufacturer)
    # while keeping payload size reasonable
    max_side = 1400
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
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

def _detect_product_type_from_text(text: str) -> str | None:
    lower = text.lower()
    for product_type, keywords in _PRODUCT_TYPE_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return product_type
    return None


def _ocr_fallback(image_bytes: bytes) -> dict[str, Any]:
    try:
        import pytesseract
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        text = pytesseract.image_to_string(img)
    except Exception as exc:
        msg = str(exc).lower()
        if "tesseract is not installed" in msg or "not in your path" in msg:
            logger.warning(
                "Tesseract OCR not available (%s). "
                "Install: Linux → sudo apt install tesseract-ocr ; "
                "macOS → brew install tesseract",
                exc,
            )
        else:
            logger.warning("pytesseract OCR failed: %s", exc)
        return _empty_result()

    result = _empty_result()
    result["method"] = "ocr"
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Brand & item_name — use the first 1–2 non-trivial lines as a proxy
    if lines:
        result["brand"] = lines[0]
        result["confidence"]["brand"] = 0.4
        if len(lines) >= 2:
            result["item_name"] = f"{lines[0]} {lines[1]}"
            result["confidence"]["item_name"] = 0.35
        else:
            result["item_name"] = lines[0]
            result["confidence"]["item_name"] = 0.3

    # Weight — e.g. "500 ml", "250g", "1.5 KG"
    weight_match = re.search(
        r"\b(\d+(?:[.,]\d+)?)\s*(ml|ML|l|L|g|G|kg|KG|oz|OZ|lb|LB)\b",
        text,
    )
    if weight_match:
        amt = weight_match.group(1).replace(",", ".")
        unit = weight_match.group(2).upper()
        sep = " " if len(unit) > 1 else ""
        result["weight"] = f"{amt}{sep}{unit}"
        result["confidence"]["weight"] = 0.55

    # Barcode via pyzbar
    barcode = extract_barcode_pyzbar(image_bytes)
    if barcode:
        result["barcode"] = barcode
        result["confidence"]["barcode"] = 0.95

    # Country of manufacture
    country_match = re.search(
        r"(?:Made|Manufactured|Produced|Packed)\s+in\s+([A-Za-z ]{2,30})",
        text,
        re.IGNORECASE,
    )
    if country_match:
        result["country"] = country_match.group(1).strip().title()
        result["confidence"]["country"] = 0.6

    # Product type — keyword scan
    product_type = _detect_product_type_from_text(text)
    if product_type:
        result["product_type"] = product_type
        result["confidence"]["product_type"] = 0.5

    # Manufacturer — look for "Manufactured by" / "Made by" patterns
    mfr_match = re.search(
        r"(?:Manufactured|Produced|Distributed)\s+by[:\s]+([A-Za-z][^\n]{3,60})",
        text,
        re.IGNORECASE,
    )
    if mfr_match:
        result["manufacturer"] = mfr_match.group(1).strip()
        result["confidence"]["manufacturer"] = 0.55

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
        max_tokens=1000,
        temperature=0.0,
    )

    raw = json.loads(response.choices[0].message.content)

    # Use the model's own per-field confidence scores.
    # Fall back to 0.7 if the model omitted the confidence object.
    model_conf = raw.pop("confidence", None)
    if isinstance(model_conf, dict):
        conf = {f: float(model_conf.get(f, 0.0)) for f in IMDB_FIELDS}
    else:
        conf = {
            f: 0.7 if raw.get(f) not in (None, "") else 0.0
            for f in IMDB_FIELDS
        }

    # Do NOT null out low-confidence values here — the aggregator across
    # multiple images will pick the highest-confidence value per field.
    # A low-confidence value from one image is still useful when other
    # images may not show that field at all.

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
        logger.warning(
            "GPT-4o extraction failed (%s); falling back to OCR", exc
        )
        result = _ocr_fallback(processed)

    # pyzbar always overrides barcode — more reliable than vision
    if not result.get("barcode"):
        barcode = extract_barcode_pyzbar(processed)
        if barcode:
            result["barcode"] = barcode
            result.setdefault("confidence", {})["barcode"] = 0.98

    # Ensure all fields and confidence keys are present
    conf = result.get("confidence", {})
    for field in IMDB_FIELDS:
        if field not in conf:
            conf[field] = 0.0 if result.get(field) in (None, "") else 0.5
        if field not in result:
            result[field] = "" if field in EMPTY_STRING_FIELDS else None
    result["confidence"] = conf

    return result
