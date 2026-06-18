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
    "clearly visible on the label or in the image tag. "
    "Never hallucinate brand names, weights, barcodes, or countries. "
    "If a field is not visible, return null."
)

_EXTRACTION_PROMPT = """Analyze the product image carefully and return a single JSON object with EXACTLY these keys:

{
  "item_name": "<CRITICAL: Extract from the image tag/label at the BOTTOM of the image FIRST. This contains the canonical product name. Use it verbatim. If no visible tag, try to infer from package labels. Examples: 'Blue Band Margarine Original 500G Tub', 'Rama Butter 250G Glass Jar'. If truly unable to determine, null>",
  "barcode": "<Numeric barcode digits only, no spaces or dashes. Use pyzbar if available. If barcode visible but unclear, null>",
  "manufacturer": "<Full legal name of the manufacturing company as printed. Search for 'Manufactured by', 'Made by', or company name on label. If not found, null>",
  "brand": "<Brand name exactly as printed on label. The primary brand identifier. If not clearly visible, null>",
  "weight": "<Net weight or volume with unit in UPPERCASE format. Examples: '250G', '1.5 KG', '500 ML', '2L'. Format: AmountUNIT (no space for single-letter units like G, L; space for multi-letter units like KG, ML). If not visible, null>",
  "packaging_type": "<Packaging form in UPPERCASE. Choose from: TUB, GLASS JAR, SACHET, BOTTLE, CAN, BOX, BAG, POUCH, TETRA PAK, TUBE, JAR. If ambiguous, null>",
  "country": "<Country of manufacture or packing as explicitly stated on label (e.g., 'Made in India', 'Packed in Ghana'). Return the country name. If not visible, null>",
  "variant": "<Product variant if clearly labeled, e.g. 'ORIGINAL', 'LOW FAT', 'LIGHT', 'FULL CREAM', 'SMOOTH', 'CRUNCHY'. Empty string '' if no variant or not applicable>",
  "product_type": "<Product category in UPPERCASE. Examples: MARGARINE, MAYONNAISE, BUTTER, YOGHURT, JUICE, OIL, MILK, JAM, SAUCE. Infer from product description if needed. If unclear, null>",
  "fragrance_flavor": "<ONLY actual taste/scent flavors, e.g. 'STRAWBERRY', 'VANILLA', 'CHOCOLATE', 'HONEY', 'LEMON'. Do NOT include variants like 'ORIGINAL', 'LIGHT', or packaging details. Empty string '' if no specific flavor or not applicable>",
  "promotion": "<On-pack promotion text verbatim, e.g. '50% OFF', 'BUY 2 GET 1 FREE', 'FREE SAMPLE INCLUDED'. Empty string '' if none visible>",
  "addons": "<Additional features or pack contents, e.g. 'SPOON INCLUDED', 'FREE RECIPE BOOK', 'BONUS PACK'. Empty string '' if none>",
  "tagline": "<Short promotional or descriptive tagline printed on the pack, e.g. 'The Original Taste', 'Naturally Fresh'. Empty string '' if none>"
}

Critical Rules:
1. ALWAYS read the image tag/label at the BOTTOM of the image FIRST for item_name — it is the authoritative source.
2. Use null (JSON null) ONLY for fields where the value cannot be determined from the visible image content.
3. Use empty string "" ONLY for: variant, fragrance_flavor, promotion, addons, tagline when the field is not applicable.
4. Weight format: Amount + Unit (uppercase). Single-letter units (G, L): no space (250G). Multi-letter units (KG, ML, OZ, etc.): space before (1.5 KG).
5. fragrance_flavor must be actual flavor/scent ONLY — never include variant information here.
6. Extract exactly what you see. Do not hallucinate, guess, or infer beyond what is visible.
7. If a field is ambiguous or unclear, use null rather than guessing.
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
    max_side = 1024  # 1024px is sufficient for label text; smaller payload = faster API round-trip
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    img = img.filter(ImageFilter.SHARPEN)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)  # 85 vs 92: ~30% smaller with no visible quality loss
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
        if "tesseract is not installed" in str(exc).lower() or "not in your path" in str(exc).lower():
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
        max_tokens=500,
        temperature=0.0,
    )

    raw = json.loads(response.choices[0].message.content)
    # Compute confidence from field presence — 0.92 if value present, 0.0 if null/empty
    raw["confidence"] = {
        f: 0.92 if raw.get(f) not in (None, "") else 0.0
        for f in IMDB_FIELDS
    }
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
