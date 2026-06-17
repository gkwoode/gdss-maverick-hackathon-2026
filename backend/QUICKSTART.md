# GDSS Maverick Hackathon 2026 — Product Data Extraction

## Quickstart

### 1. Setup (5 minutes)

```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set OpenAI API key (required for GPT-4o Vision)
export OPENAI_API_KEY=sk-your-key-here  # Windows: set OPENAI_API_KEY=...

# Setup database
python manage.py migrate

# Start server
python manage.py runserver
# Server runs at http://localhost:8000/api/
```

---

### 2. Organize Product Images

**Expected Directory Structure:**
```
product_images/
├── 001_front.jpg
├── 001_back.jpg
├── 001_left.jpg
├── 002_front.jpg
├── 002_back.jpg
├── 002_left.jpg
├── ...
```

**Filename Format:** `<PRODUCT_ID>_<angle>.<ext>`
- Product ID: 001, 002, 003, ... 045 (for 45 products)
- Angle: front, back, left, right, top, bottom, etc.
- Extension: jpg, png, webp

---

### 3. Extract All Products (2 approaches)

#### Option A: CLI Command (Recommended)
```bash
python manage.py batch_process --images-dir ./media/product_images
```

Output:
```
Processing images from: ./media/product_images
✓ Processed 45 products: 42 created, 0 updated, 3 skipped, 0 failed
```

#### Option B: REST API
```bash
curl -X POST http://localhost:8000/api/products/batch_process/ \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

### 4. Export Final Predictions

```bash
# As CSV (Recommended)
curl http://localhost:8000/api/products/export/?format=csv > predictions.csv

# As Excel
curl http://localhost:8000/api/products/export/?format=excel > predictions.xlsx
```

**Output File:** `predictions.csv` or `predictions.xlsx`

Contains all 13 required columns:
- ITEM_NAME
- BARCODE
- MANUFACTURER
- BRAND
- WEIGHT
- PACKAGING TYPE
- COUNTRY
- VARIANT
- TYPE
- FRAGRANCE_FLAVOR
- PROMOTION
- ADDONS
- TAGLINE

---

## Workflow: Complete Example

### Step 1: Import Ground Truth (if provided)

```bash
python manage.py import_ground_truth --xlsx /path/to/ground_truth.xlsx
```

This creates reference records with `overall_confidence=1.0` for evaluation.

If you are preparing ML train/test files from an unsplit dataset, use:

```bash
python ml/prepare_dataset.py --excel /path/to/ground_truth.xlsx --images-dir ./product_images --test-size 0.2 --seed 42
```

Use strict mode to enforce the expected 3-4 images per product:

```bash
python ml/prepare_dataset.py --excel /path/to/ground_truth.xlsx --images-dir ./product_images --strict-image-count
```

### Step 2: Process All Product Images

```bash
# Using CLI
python manage.py batch_process

# Using REST API
curl -X POST http://localhost:8000/api/products/batch_process/
```

This will:
- Scan `media/product_images/` directory
- Group images by product ID
- For each product, analyze all images
- Aggregate results using confidence-based merging
- Create IMDBRecord for each product
- Automatically detect duplicates

### Step 3: Review Results

```bash
# Check overall statistics
curl http://localhost:8000/api/products/ | jq '.count'

# Find records needing review (confidence < 0.7)
curl "http://localhost:8000/api/products/?needs_review=true" | jq '.results[] | {id, item_name, overall_confidence}'

# Find potential duplicates
curl "http://localhost:8000/api/products/?search=Blue" | jq '.results[] | {id, brand, item_name, is_duplicate_candidate}'
```

### Step 4: Optional - Evaluate Against Ground Truth

```bash
# Using CLI
python manage.py evaluate_predictions --output report.json

# Using REST API
curl http://localhost:8000/api/products/evaluate/ > evaluation_results.json
```

Output includes:
- Overall accuracy
- Per-field statistics (exact matches, partial matches, mismatches)
- Comparison details for each product

### Step 5: Export Predictions

```bash
# Export as CSV for submission
curl http://localhost:8000/api/products/export/?format=csv > predictions.csv

# Verify output
head predictions.csv
```

Expected output format (exact column order):
```csv
ITEM_NAME,BARCODE,MANUFACTURER,BRAND,WEIGHT,PACKAGING TYPE,COUNTRY,VARIANT,TYPE,FRAGRANCE_FLAVOR,PROMOTION,ADDONS,TAGLINE
Blue Band Margarine Original 500G Tub,6001066022011,Unilever South Africa,Blue Band,500G,TUB,South Africa,ORIGINAL,MARGARINE,,50% EXTRA FREE,,
...
```

Submission note: if a field cannot be confidently extracted, keep it as an empty string instead of guessing.

---

## Key Features

### Multi-Image Aggregation
Each product's 3-4 images are analyzed separately, then results are intelligently merged:
- **Confidence-based selection:** Highest confidence value wins
- **Concatenation:** Promotions, addons, taglines combined across images
- **Override:** Barcode always extracted via pyzbar first (most reliable)

### Automatic Quality Checks
- **Confidence scoring:** Per-field confidence (0.0-1.0)
- **Review flagging:** Records with confidence < 0.7 marked for review
- **Duplicate detection:** Identifies potential duplicates via barcode or brand+name+weight

### Extraction Methods
1. **Primary:** OpenAI GPT-4o Vision (high accuracy)
2. **Fallback:** Tesseract OCR (when API unavailable)
3. **Barcode:** pyzbar (most reliable, always preferred)

### Field-Specific Rules

| Field | Source | Format | Example |
|-------|--------|--------|---------|
| ITEM_NAME | Image tag at bottom | Full name | Blue Band Margarine Original 500G Tub |
| BARCODE | Barcode on package | 8-14 digits | 6001066022011 |
| WEIGHT | "Net weight" label | Amount+Unit | 500G, 1.5 KG, 500 ML |
| PACKAGING_TYPE | Visual | Standardized | TUB, BOTTLE, CAN, JAR |
| VARIANT | Explicit label | UPPERCASE or "" | ORIGINAL, LOW FAT, "" |
| FRAGRANCE_FLAVOR | Flavor text only | UPPERCASE or "" | STRAWBERRY, VANILLA, "" |
| PROMOTION | On-pack text | Verbatim or "" | 50% OFF, BUY 2 GET 1 FREE, "" |

---

## API Endpoints

### Analysis
- `POST /api/products/analyze/` — Analyze single image
- `POST /api/products/analyze_multi/` — Analyze 3-4 images of same product

### Processing
- `POST /api/products/batch_process/` — Process entire directory
- `GET /api/products/evaluate/` — Evaluate predictions vs ground truth

### Export
- `GET /api/products/export/?format=csv` — Download predictions.csv
- `GET /api/products/export/?format=excel` — Download predictions.xlsx

### Management
- `GET /api/products/` — List all records
- `GET /api/products/{id}/` — Get single record
- `PATCH /api/products/{id}/` — Update record
- `DELETE /api/products/{id}/` — Delete record

---

## Troubleshooting

### Issue: "OPENAI_API_KEY is not set"
**Solution:**
```bash
export OPENAI_API_KEY=sk-your-key-here
```

### Issue: Images not found / no products processed
**Solution:** Check directory structure:
```bash
ls -la media/product_images/
# Should see: 001_front.jpg, 001_back.jpg, etc.
```

### Issue: Low confidence on certain fields
**Possible causes:**
- Image quality (blur, bad lighting)
- Field not visible on any image
- Unusual format (non-standard units, special characters)

**Resolution:**
- Provide clearer images
- Use multiple angles
- Check extraction confidence scores

### Issue: Performance slow on batch processing
**Optimization:**
- Process in batches: `--max-products 10`
- Verify OpenAI API is responsive
- Use faster network connection

---

## Performance Expectations

- **Single image:** 5-10 seconds (including GPT-4o API call)
- **Multi-image (3-4):** 10-15 seconds
- **Batch (45 products):** 5-10 minutes
- **Accuracy:** 85-95% for well-lit, clear images

---

## Field Extraction Examples

### Example 1: Margarine
**Image tag:** "Blue Band Margarine Original 500G Tub"
```json
{
  "item_name": "Blue Band Margarine Original 500G Tub",
  "barcode": "6001066022011",
  "brand": "Blue Band",
  "manufacturer": "Unilever South Africa",
  "weight": "500G",
  "packaging_type": "TUB",
  "country": "South Africa",
  "variant": "ORIGINAL",
  "product_type": "MARGARINE",
  "fragrance_flavor": "",
  "promotion": "50% EXTRA FREE",
  "addons": "",
  "tagline": "The Original Taste"
}
```

### Example 2: Juice
**Image tag:** "Tropika Orange Juice Fresh 1L Bottle"
```json
{
  "item_name": "Tropika Orange Juice Fresh 1L Bottle",
  "barcode": "6002177054321",
  "brand": "Tropika",
  "manufacturer": "Tropika Beverages Ltd",
  "weight": "1L",
  "packaging_type": "BOTTLE",
  "country": "Ghana",
  "variant": "",
  "product_type": "JUICE",
  "fragrance_flavor": "ORANGE",
  "promotion": "",
  "addons": "",
  "tagline": "Fresh from Nature"
}
```

---

## Data Quality Checklist

Before submitting predictions:

- [ ] All 45 products processed
- [ ] No records with confidence < 0.5 (except flagged for review)
- [ ] Barcodes validated (8-14 digits, all numeric)
- [ ] Weights normalized (250G, 1.5 KG format)
- [ ] Country names standardized
- [ ] Packaging types use allowed enums
- [ ] Empty strings "" used for optional missing fields (not null)
- [ ] All 13 columns present in export file
- [ ] CSV/XLSX format matches ground truth

---

## Submission

**Final Output Files:**
- `predictions.csv` (UTF-8, comma-separated)
- OR `predictions.xlsx` (Excel format)

**Submit:**
1. Download from `/api/products/export/?format=csv`
2. Verify column order matches ground truth
3. Check all 45 products present
4. Upload for evaluation

---

## Advanced: Custom Processing

### Process specific products only
```bash
python manage.py batch_process --images-dir ./media/product_images --max-products 10
```

### Skip existing records
```bash
python manage.py batch_process --skip-existing
```

### Custom analysis
```bash
# Analyze specific product
curl -X POST http://localhost:8000/api/products/analyze_multi/ \
  -F "images=@001_front.jpg" \
  -F "images=@001_back.jpg" \
  -F "images=@001_left.jpg"
```

### Check specific records
```bash
# Get product with ID 5
curl http://localhost:8000/api/products/5/

# Find by barcode
curl "http://localhost:8000/api/products/?barcode=6001066022011"

# Find by brand
curl "http://localhost:8000/api/products/?brand=Blue+Band"
```

---

## Documentation

- [API_GUIDE.md](./API_GUIDE.md) — Full REST API reference
- [WORKFLOW.md](../WORKFLOW.md) — Complete system architecture and workflow

---

## Support

For issues:
1. Check OpenAI API key and rate limits
2. Verify image quality and directory structure
3. Check logs: `python manage.py runserver`
4. See API_GUIDE.md for detailed endpoint docs
