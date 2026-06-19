"""
image_analyzer.py
-----------------
Primary attribute-extraction service for the 13-column IMDB schema.

Strategy (in priority order):
  1. OpenAI GPT-4o Vision — structured JSON extraction of all 13 IMDB fields.
     Set OPENAI_MODEL=ft:gpt-4o-mini-... to use a fine-tuned model instead.
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
# Model selection
# Set OPENAI_MODEL env var to use a fine-tuned model after training.
# Fine-tuned model names start with "ft:"; inference then uses the training-
# format prompt (no confidence scoring) to match what the model was trained on.
# ---------------------------------------------------------------------------
_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
_IS_FINETUNED = _MODEL.startswith("ft:")

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

# ---------------------------------------------------------------------------
# Fine-tuned model prompts
# These MUST match ml/train_openai.py exactly — the fine-tuned model was
# trained with this format; inference must use the same format.
# ---------------------------------------------------------------------------

_FT_SYSTEM_PROMPT = (
    "You are a strict product-label reader for a retail IMDB system. "
    "Your ONLY job is to READ and TRANSCRIBE text that is physically "
    "printed on the product label in the image. "
    "NEVER guess, infer, complete, or use any knowledge you have about "
    "this brand or product — even if you recognise it. "
    "If a field value is not clearly visible on this specific image, "
    "return null (or empty string for optional fields). "
    "Accuracy is more important than completeness: "
    "a null is always better than an invented or assumed value.\n\n"
    "Return ONLY a valid JSON object with these exact keys:\n"
    "item_name, barcode, manufacturer, brand, weight, packaging_type, "
    "country, variant, product_type, fragrance_flavor, promotion, "
    "addons, tagline\n\n"
    "Field notes:\n"
    "  item_name      – ALL CAPS assembled string:\n"
    "                   BRAND + PRODUCT_DESC + WEIGHT + PACKAGING"
    " + MANUFACTURER\n"
    "                   (only include parts visible on this label)\n"
    "                   null only if brand AND description both unreadable\n"
    "  barcode        – digits only (8-14 digits);"
    " null if ANY digit unclear\n"
    "  manufacturer   – company name after any of: 'Manufactured by',"
    " 'Made by', 'Distributed by', 'Marketed by', 'Imported by',"
    " 'Packed by'; null if none present\n"
    "  brand          – copy brand name exactly as printed; null if absent\n"
    "  weight         – copy net weight/volume exactly (e.g. 250G, 500 ML)\n"
    "  packaging_type – TUB/BOTTLE/CAN/JAR/SACHET/BOX/BAG/POUCH/TETRA PAK\n"
    "  country        – from 'Made in X'/'Packed in X' only; null if absent\n"
    "  variant        – variant text (ORIGINAL, LOW FAT...); '' if absent\n"
    "  product_type   – category text on label; null if not printed\n"
    "  fragrance_flavor – flavour/scent text; '' if absent\n"
    "  promotion      – promo text verbatim; '' if absent\n"
    "  addons         – bundled extras text; '' if absent\n"
    "  tagline        – slogan text; '' if absent\n\n"
    "Do not include any explanation outside the JSON."
)

_FT_EXTRACTION_PROMPT = (
    "Extract all 13 IMDB attributes from the product image(s) "
    "and return them as a JSON object."
)

# ---------------------------------------------------------------------------
# Base model prompts (GPT-4o with per-field confidence scoring)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a strict product-label reader for a retail IMDB system. "
    "Your ONLY job is to READ and TRANSCRIBE text that is physically "
    "printed on the product label in the image. "
    "NEVER guess, infer, complete, or use any knowledge you have about "
    "this brand or product — even if you recognise it. "
    "If a field value is not clearly visible on this specific image, "
    "return null. Accuracy is more important than completeness: "
    "a null is always better than an invented or assumed value."
)

_EXTRACTION_PROMPT = """Read the product label in this image and extract
the 13 IMDB attributes listed below.

STRICT RULES — read these before extracting:
  • Only transcribe text you can CLEARLY SEE on this specific label.
  • Do NOT use your general knowledge about the brand or product.
  • Do NOT guess, complete, or construct any value.
  • If a field is not printed on this image, return null (or "" for
    the fields marked with "").
  • A null is always correct when text is absent or unreadable.
  • MANUFACTURER WARNING: You likely know which company makes this
    brand from your training data. IGNORE that knowledge. Only return
    a manufacturer if a company-attribution phrase (see manufacturer
    field rules below) is physically printed on THIS label.

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
    "item_name": 0.0, "barcode": 0.0, "manufacturer": 0.0,
    "brand": 0.0, "weight": 0.0, "packaging_type": 0.0,
    "country": 0.0, "variant": 0.0, "product_type": 0.0,
    "fragrance_flavor": 0.0, "promotion": 0.0,
    "addons": 0.0, "tagline": 0.0
  }
}

── FIELD RULES ──────────────────────────────────────────────────────────────

item_name: Construct a full item identifier in UPPERCASE by assembling these
  parts in order, separated by spaces:
    1. Brand name (as printed on label)
    2. Key product description / variant text from the label
       (e.g. "CHOLESTEROL FREE SPREAD FOR BREAD", "MAYONNAISE WITH LEMON")
    3. Net weight/volume (e.g. 250G, 500ML, 1.5KG)
    4. Packaging material + form (e.g. PLASTIC TUB, GLASS JAR, SACHET,
       PLASTIC BOTTLE)
    5. Manufacturer / distributor name visible on label (from
       "Manufactured by", "Distributed by", "Made by" text)
  Use ALL CAPS. Do NOT add punctuation between parts.
  Example: "BLUE BAND SPREAD 250G PLASTIC TUB UPFIELD GHANA LTD"
  null only if the brand AND product description are both unreadable.

barcode: Read EVERY digit printed below the barcode lines with 100% certainty.
  Digits only, no spaces or dashes (8–14 digits).
  CRITICAL: If even ONE digit is unclear, blurred, or you have any doubt,
  return null — a barcode scanner will be used instead. A wrong digit is
  far worse than null. Only return a value when you can read every single
  character with complete confidence.

manufacturer: The label MUST contain a company-attribution phrase followed
  by a company name. Accepted trigger phrases (copy the company name
  that follows, in ALL CAPS):
    "Manufactured by", "Made by", "Produced by",
    "Distributed by", "Marketed by", "Imported by",
    "Packed by", "Processed by"
  Copy the full company name character-for-character exactly as printed.
  • Do NOT return a manufacturer name from your general knowledge —
    even if you are 100% certain which company owns this brand.
  • Do NOT complete a partially-visible company name from memory.
  • Return only the company name, not the trigger phrase itself.
  null if none of the trigger phrases appear on this image, or the
  company name after the phrase is unreadable.

brand: Copy the brand name exactly as printed on the label.
  null if not visible.

weight: Copy the net weight or volume exactly as printed (e.g. 250G,
  500 ML, 1.5 KG). Uppercase units only.
  null if not printed on this image.

packaging_type: Identify from what you can physically see in the image.
  Choose EXACTLY ONE: TUB, GLASS JAR, SACHET, BOTTLE, CAN, BOX, BAG,
  POUCH, TETRA PAK, TUBE, JAR.
  null if the package type is genuinely unclear.

country: Copy the country name from any of these phrases printed on
  the label (return ONLY the country name, in ALL CAPS):
    "Made in X", "Manufactured in X", "Produced in X",
    "Packed in X", "Packaged in X", "Bottled in X",
    "Product of X", "Country of origin: X"
  null if none of these phrases appear on this image.

variant: Copy variant text printed on pack (e.g. ORIGINAL, LOW FAT,
  LIGHT, SALTED). "" if no variant text is printed.

product_type: Copy the product category text printed on the label
  (e.g. MARGARINE, JUICE, POWDER, ENERGY DRINK).
  Do NOT use your knowledge of the brand — only read label text.
  null if no category text is printed on this image.

fragrance_flavor: Copy flavour or scent text printed on the label
  (e.g. STRAWBERRY, VANILLA, LEMON). "" if not printed.

promotion: Copy any promotional text printed on the label verbatim
  (e.g. "BUY 2 GET 1 FREE", "20% EXTRA FREE"). "" if none.

addons: Copy any bundled-extras text printed on the label
  (e.g. "FREE SPOON INSIDE"). "" if none.

tagline: Copy the short slogan or tagline printed on the label.
  "" if none.

── CONFIDENCE RULES ─────────────────────────────────────────────────────────

Rate each field 0.0–1.0 based on how clearly you can READ the text:
  0.9–1.0  Text is fully legible, 100% certain of every character
  0.6–0.9  Text is readable but slightly blurred or partially cut off
  0.3–0.6  Text is partially visible, some characters unclear
  0.0–0.3  Text is mostly unreadable

If you cannot read a field clearly enough to be at least 30% confident,
return null — do not guess. Null is always the correct answer when the
text is absent or unreadable.
"""


# ---------------------------------------------------------------------------
# Image pre-processing
# ---------------------------------------------------------------------------

def _preprocess_image(image_bytes: bytes) -> bytes:
    """Resize and enhance the image before sending to the model."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    # 1400px preserves fine-print legibility (country, manufacturer)
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
        r"(?:Manufactured|Produced|Distributed)"
        r"\s+by[:\s]+([A-Za-z][^\n]{3,60})",
        text,
        re.IGNORECASE,
    )
    if mfr_match:
        result["manufacturer"] = mfr_match.group(1).strip()
        result["confidence"]["manufacturer"] = 0.55

    return result


# ---------------------------------------------------------------------------
# GPT-4o Vision extraction (base and fine-tuned)
# ---------------------------------------------------------------------------

def _gpt4o_extract(image_bytes: bytes) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Fine-tuned models must use the same prompt they were trained with.
    # Base gpt-4o uses the richer prompt that asks for per-field confidence.
    system = _FT_SYSTEM_PROMPT if _IS_FINETUNED else _SYSTEM_PROMPT
    user_text = _FT_EXTRACTION_PROMPT if _IS_FINETUNED else _EXTRACTION_PROMPT

    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
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

    # Base model returns per-field confidence; fine-tuned model does not.
    # Assign 0.85 to every field the fine-tuned model extracted.
    model_conf = raw.pop("confidence", None)
    if isinstance(model_conf, dict):
        conf = {f: float(model_conf.get(f, 0.0)) for f in IMDB_FIELDS}
    else:
        conf = {
            f: 0.85 if raw.get(f) not in (None, "") else 0.0
            for f in IMDB_FIELDS
        }

    # Do NOT null out low-confidence values here — the multi-image aggregator
    # picks the highest-confidence value per field across all images.

    raw["confidence"] = conf
    raw["method"] = "gpt4o-ft" if _IS_FINETUNED else "gpt4o"
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

    # Run pyzbar on both original and preprocessed bytes — resizing can
    # sometimes degrade barcode patterns so try both.
    barcode_pyzbar = (
        extract_barcode_pyzbar(image_bytes)
        or extract_barcode_pyzbar(processed)
    )

    try:
        result = _gpt4o_extract(processed)
        logger.info("GPT-4o extraction succeeded (model=%s)", _MODEL)
    except Exception as exc:
        logger.warning(
            "GPT-4o extraction failed (%s); falling back to OCR", exc
        )
        result = _ocr_fallback(processed)

    # pyzbar reads the actual barcode pattern — always beats visual digit
    # reading. Override GPT-4o's barcode unconditionally when pyzbar succeeds.
    if barcode_pyzbar:
        result["barcode"] = barcode_pyzbar
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
