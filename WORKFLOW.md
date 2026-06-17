# IMDB Product Data Extraction Workflow

## Overview

This system extracts product information from multiple images of each product and generates structured IMDB records matching the 13-column ground truth schema.

**13 Required Columns:**
1. ITEM_NAME
2. BARCODE
3. MANUFACTURER
4. BRAND
5. WEIGHT
6. PACKAGING TYPE
7. COUNTRY
8. VARIANT
9. TYPE
10. FRAGRANCE_FLAVOR
11. PROMOTION
12. ADDONS
13. TAGLINE

## Architecture

```
Product Images (3-4 per product)
         ↓
    Image Analyzer (GPT-4o Vision)
         ↓
    Per-Image Extraction Results
         ↓
    Aggregator (Multi-Image Merge)
         ↓
    Validator (Normalization)
         ↓
    Duplicate Checker
         ↓
    IMDBRecord (Database)
         ↓
    Exporter (CSV/XLSX)
```

## Components

### 1. Image Analyzer (`image_analyzer.py`)
- **Primary Method:** OpenAI GPT-4o Vision
- **Fallback:** Tesseract OCR
- **Barcode Extraction:** pyzbar (always preferred for barcodes)

**Key Features:**
- Reads image tag at bottom of image for canonical `item_name`
- Extracts all 13 fields with confidence scores
- Preprocessing: resize to 1600px, sharpen, enhance contrast
- Response format: Structured JSON with per-field confidence

**Field Extraction Strategy:**
- **item_name:** Image tag at bottom (highest priority)
- **barcode:** pyzbar → GPT-4o Vision
- **weight:** Format normalized (250G, 1.5 KG, 500 ML)
- **packaging_type:** Standardized enum (TUB, BOTTLE, CAN, etc.)
- **country:** "Made in X" text extraction
- **variant:** Only when explicitly labeled
- **fragrance_flavor:** Only taste/scent, NOT variant info
- **promotion:** Verbatim on-pack promo text

### 2. Aggregator (`aggregator.py`)
Merges results from multiple images of the same product.

**Merge Strategy:**
- **Standard fields:** Use value with highest confidence
- **Concatenation fields** (promotion, addons, tagline): Collect unique values across images
- **Longest value** (item_name): Use longest non-empty value
- **Overall confidence:** Max confidence per field

### 3. Validator (`validator.py`)
Normalizes and validates extracted data.

**Validation Rules:**
- **Barcode:** 8-14 numeric digits
- **Weight:** Format as `AmountUNIT` (uppercase, space before multi-letter units)
  - Examples: `250G`, `1.5 KG`, `500 ML`
- **Country:** Normalized country names (aliases: USA→United States, etc.)
- **Packaging Type:** Standardized enums
- **Text Fields:** Trimmed and titlecased

### 4. Duplicate Checker (`duplicate_checker.py`)
Identifies potential duplicate products.

**Matching Criteria:**
- Identical barcode
- Same brand + item_name + weight

### 5. Exporter (`exporter.py`)
Generates predictions in submission format.

**Output Formats:**
- **CSV:** UTF-8, comma-separated (UTF-8 BOM)
- **Excel:** .xlsx with auto-sized columns

**Column Order:** Matches ground truth exactly

## Workflow: End-to-End

### Phase 1: Data Preparation

1. **Organize Images by Product**
   - Directory structure: `product_images/`
   - Filename format: `<PRODUCT_ID>_<angle>.<ext>`
   - Example: `001_front.jpg`, `001_back.jpg`, `001_left.jpg`

2. **Optional: Load Ground Truth**
   ```bash
   python manage.py import_ground_truth --xlsx path/to/ground_truth.xlsx
   ```
   - Creates records with `overall_confidence=1.0`
   - Marks as ground truth for evaluation

### Phase 2: Image Analysis

#### Option A: Single Image Analysis
```bash
curl -X POST http://localhost:8000/api/products/analyze/ \
  -F "image=@product.jpg"
```

**Response:**
```json
{
  "extracted": {
    "item_name": "Blue Band Margarine Original 500G Tub",
    "barcode": "6001066022011",
    "brand": "Blue Band",
    ...
  },
  "confidence": {
    "item_name": 0.92,
    "barcode": 0.98,
    ...
  },
  "potential_duplicates": [...],
  "images_processed": 1
}
```

#### Option B: Multi-Image Analysis (Recommended)
```bash
curl -X POST http://localhost:8000/api/products/analyze_multi/ \
  -F "images=@front.jpg" \
  -F "images=@back.jpg" \
  -F "images=@left.jpg"
```

**Response:**
```json
{
  "extracted": {
    "item_name": "Blue Band Margarine Original 500G Tub",
    "promotion": "50% EXTRA FREE, BUY ONE GET ONE HALF PRICE",
    ...
  },
  "confidence": {...},
  "potential_duplicates": [...],
  "images_processed": 3,
  "images_failed": 0
}
```

#### Option C: Batch Processing (All Products)
```bash
curl -X POST http://localhost:8000/api/products/batch_process/ \
  -H "Content-Type: application/json" \
  -d '{
    "images_dir": "/path/to/product_images",
    "max_products": null,
    "update_existing": true
  }'
```

**Response:**
```json
{
  "total_products": 45,
  "created": 42,
  "updated": 0,
  "skipped": 3,
  "failed": 0,
  "summary": "Processed 45 products: 42 created, 0 updated, 3 skipped, 0 failed",
  "results": [...]
}
```

### Phase 3: Data Storage

- Each product group → single `IMDBRecord`
- Stores: all 13 fields + confidence scores + image paths
- Database: SQLite (or PostgreSQL in production)
- Automatic duplicate detection on save

### Phase 4: Evaluation (Optional)

Compare predictions against ground truth.

```bash
curl -X GET http://localhost:8000/api/products/evaluate/
```

**Response:**
```json
{
  "total_predictions": 42,
  "total_ground_truth": 45,
  "matched_pairs": 42,
  "overall_accuracy": 0.856,
  "field_stats": {
    "item_name": {
      "exact_matches": 40,
      "partial_matches": 2,
      "mismatches": 0,
      ...
    },
    ...
  },
  "comparisons": [...]
}
```

### Phase 5: Export Predictions

**Export as CSV:**
```bash
curl -X GET http://localhost:8000/api/products/export/?format=csv \
  > predictions.csv
```

**Export as Excel:**
```bash
curl -X GET http://localhost:8000/api/products/export/?format=excel \
  > predictions.xlsx
```

**Export specific records:**
```bash
curl -X POST http://localhost:8000/api/products/export/ \
  -H "Content-Type: application/json" \
  -d '{
    "format": "csv",
    "ids": [1, 2, 3, 4, 5]
  }' > predictions.csv
```

## API Endpoints

### Products CRUD
- `GET /api/products/` — List all records
- `GET /api/products/{id}/` — Get single record
- `POST /api/products/` — Create new record
- `PATCH /api/products/{id}/` — Update record
- `DELETE /api/products/{id}/` — Delete record

### Analysis
- `POST /api/products/analyze/` — Single image analysis
- `POST /api/products/analyze_multi/` — Multi-image analysis
- `POST /api/products/check_duplicates/` — Check for duplicates

### Processing
- `POST /api/products/batch_process/` — Batch process directory
- `GET /api/products/evaluate/` — Evaluate predictions

### Export
- `GET /api/products/export/` — Export all predictions
  - Query params:
    - `format`: "csv" (default) or "excel"
    - `ids`: comma-separated IDs (optional)

## Field Extraction Guidelines

### ITEM_NAME
- **Source:** Image tag at bottom (highest priority)
- **Format:** Full descriptive name
- **Example:** "Blue Band Margarine Original 500G Tub"
- **Rule:** Extract verbatim from image tag

### BARCODE
- **Source:** pyzbar → GPT-4o Vision
- **Format:** Numeric digits only (8-14)
- **Example:** "6001066022011"
- **Validation:** No spaces, dashes, or letters

### MANUFACTURER
- **Source:** "Manufactured by", "Made by", or company name
- **Format:** Full legal company name
- **Example:** "Unilever South Africa (Pty) Ltd"

### BRAND
- **Source:** Primary brand identifier on label
- **Format:** Exact as printed
- **Example:** "Blue Band", "Rama", "I Can't Believe It's Not Butter"

### WEIGHT
- **Source:** "Net weight", "Net volume" on label
- **Format:** `Amount + Unit (UPPERCASE)`
- **Examples:** `250G`, `1.5 KG`, `500 ML`, `2L`
- **Rules:**
  - Single-letter units: no space (250G, 1L)
  - Multi-letter units: space (1.5 KG, 500 ML)

### PACKAGING TYPE
- **Source:** Visual inspection
- **Format:** Standardized enum (UPPERCASE)
- **Valid Values:** TUB, GLASS JAR, SACHET, BOTTLE, CAN, BOX, BAG, POUCH, TETRA PAK, TUBE, JAR
- **Fallback:** null if unclear

### COUNTRY
- **Source:** "Made in X", "Packed in X" on label
- **Format:** Country name (normalized)
- **Examples:** "South Africa", "United States", "Ghana"

### VARIANT
- **Source:** Explicit variant label
- **Format:** UPPERCASE (or empty string)
- **Valid Examples:** "ORIGINAL", "LOW FAT", "LIGHT", "FULL CREAM", "SMOOTH", "CRUNCHY"
- **Rule:** Empty string "" if not applicable (not null)

### TYPE (PRODUCT_TYPE)
- **Source:** Inferred from product category or description
- **Format:** Short category in UPPERCASE
- **Examples:** "MARGARINE", "BUTTER", "MAYONNAISE", "YOGHURT", "JUICE", "OIL", "MILK"

### FRAGRANCE_FLAVOR
- **Source:** Actual taste/scent labels only
- **Format:** UPPERCASE (or empty string)
- **Valid Examples:** "STRAWBERRY", "VANILLA", "CHOCOLATE", "HONEY", "LEMON"
- **Rule:** NOT variants like "ORIGINAL" or "LOW FAT" — empty string "" if not applicable

### PROMOTION
- **Source:** On-pack promotional text
- **Format:** Verbatim text (or empty string)
- **Examples:** "50% OFF", "BUY 2 GET 1 FREE", "50% EXTRA FREE"
- **Rule:** Concatenate all unique promotions seen across images

### ADDONS
- **Source:** Included items or features
- **Format:** Text (or empty string)
- **Examples:** "SPOON INCLUDED", "FREE RECIPE BOOK", "BONUS PACK"

### TAGLINE
- **Source:** Short promotional/descriptive tagline on pack
- **Format:** Text (or empty string)
- **Examples:** "The Original Taste", "Naturally Fresh", "Premium Quality"

## Confidence Scores

Each extracted field has a confidence score (0.0 to 1.0):
- **1.0:** Ground truth or perfect extraction
- **0.92:** GPT-4o extraction (high reliability)
- **0.98:** Barcode via pyzbar (very high reliability)
- **0.5:** OCR fallback or partial extraction
- **0.0:** Field not present or extraction failed

**Overall Confidence:** Average of all field confidences
- **1.0:** Ground truth
- **≥0.7:** High confidence (publication-ready)
- **<0.7:** Needs review

## Best Practices

1. **Provide Multiple Images:**
   - 3-4 images per product (front, back, left, right)
   - Different angles capture different label sides
   - Aggregation improves data quality

2. **Quality Images:**
   - Clear, well-lit photos
   - Image tag visible at bottom
   - All label text legible
   - No rotations or severe angles

3. **Verify High-Value Fields:**
   - Barcode (critical for deduplication)
   - Brand and item_name (essential identifiers)
   - Weight (subject to validation)

4. **Review Low-Confidence Results:**
   - Records with confidence < 0.7 auto-marked for review
   - Use duplicate detection to resolve ambiguities
   - Manual review for edge cases

5. **Export Final Predictions:**
   - Use `/api/products/export/` endpoint
   - CSV or XLSX format
   - Matches ground truth column order exactly
   - Submit for evaluation

## Example: Complete Workflow

```bash
# 1. Import ground truth (if available)
python manage.py import_ground_truth --xlsx ground_truth.xlsx

# 2. Batch process all product images
curl -X POST http://localhost:8000/api/products/batch_process/ \
  -H "Content-Type: application/json" \
  -d '{"max_products": null}'

# 3. Evaluate predictions vs. ground truth
curl -X GET http://localhost:8000/api/products/evaluate/

# 4. Review records needing manual curation
curl -X GET "http://localhost:8000/api/products/?needs_review=true"

# 5. Export final predictions
curl -X GET http://localhost:8000/api/products/export/?format=csv \
  > predictions.csv

# 6. Submit predictions.csv for evaluation
```

## Troubleshooting

### Low confidence for a field
- **Barcode:** Not visible or unclear — may need pyzbar supplementation
- **Item name:** Image tag missing or illegible — ensure multi-image analysis
- **Weight:** Unusual format or ambiguous units — use validator logs
- **Variant/Flavor:** Misclassification — check extraction prompt rules

### Duplicates detected
- Use `/api/products/check_duplicates/` to verify
- Manual review may be needed if similarity is high
- Merge or keep separate based on barcode/batch info

### OCR fallback activating
- OpenAI API key not set or rate-limited
- Image too small or text illegible
- Consider retrying or improving image quality

## Dependencies

- Django 4.2+
- OpenAI (GPT-4o Vision API)
- pyzbar (barcode decoding)
- pytesseract (OCR fallback)
- Pillow (image processing)
- pandas, openpyxl (export formatting)
- djangorestframework (REST API)

## Environment Variables

```bash
OPENAI_API_KEY=sk-...
MEDIA_ROOT=/path/to/media
MEDIA_URL=/media/
```

## Output Format

**predictions.csv / predictions.xlsx**
```
ITEM_NAME,BARCODE,MANUFACTURER,BRAND,WEIGHT,PACKAGING TYPE,COUNTRY,VARIANT,TYPE,FRAGRANCE_FLAVOR,PROMOTION,ADDONS,TAGLINE
Blue Band Margarine Original 500G Tub,6001066022011,Unilever South Africa,Blue Band,500G,TUB,South Africa,ORIGINAL,MARGARINE,,50% EXTRA FREE,,
...
```

The exported file is the final submission file containing all extracted IMDB records in the exact ground truth format.
