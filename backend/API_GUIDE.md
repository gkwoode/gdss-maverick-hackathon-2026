# Backend API Guide

## Quick Start

### 1. Setup

```bash
# Create virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=sk-...  # Your OpenAI API key
export MEDIA_ROOT=./media

# Run migrations
python manage.py migrate

# Create superuser (optional, for admin panel)
python manage.py createsuperuser
```

### 2. Start Server

```bash
python manage.py runserver
```

Visit: `http://localhost:8000/api/`

### 3. Import Ground Truth (Optional)

```bash
python manage.py import_ground_truth --xlsx ground_truth.xlsx
```

### 4. Process Product Images

#### Option A: CLI Command
```bash
python manage.py batch_process --images-dir ./product_images
```

#### Option B: REST API
```bash
curl -X POST http://localhost:8000/api/products/batch_process/ \
  -H "Content-Type: application/json" \
  -d '{"max_products": null}'
```

### 5. Evaluate Predictions

#### CLI
```bash
python manage.py evaluate_predictions --output report.json
```

#### REST API
```bash
curl http://localhost:8000/api/products/evaluate/
```

### 6. Export Results

```bash
curl http://localhost:8000/api/products/export/?format=csv > predictions.csv
```

## REST API Reference

### Base URL
```
http://localhost:8000/api/
```

### Authentication
Currently no authentication (development mode). Add token authentication for production.

---

## Endpoints

### 1. List All Products
```
GET /api/products/
```

**Query Parameters:**
- `brand=<string>` — Filter by brand
- `type=<string>` — Filter by product type
- `barcode=<string>` — Filter by barcode
- `needs_review=<true|false>` — Filter by review status
- `search=<string>` — Full-text search

**Response:**
```json
{
  "count": 45,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "item_name": "Blue Band Margarine Original 500G Tub",
      "barcode": "6001066022011",
      "brand": "Blue Band",
      "overall_confidence": 0.92,
      "needs_review": false,
      ...
    }
  ]
}
```

---

### 2. Get Single Product
```
GET /api/products/{id}/
```

**Response:**
```json
{
  "id": 1,
  "item_name": "Blue Band Margarine Original 500G Tub",
  "barcode": "6001066022011",
  "manufacturer": "Unilever South Africa",
  "brand": "Blue Band",
  "weight": "500G",
  "packaging_type": "TUB",
  "country": "South Africa",
  "variant": "ORIGINAL",
  "product_type": "MARGARINE",
  "fragrance_flavor": "",
  "promotion": "50% EXTRA FREE",
  "addons": "",
  "tagline": "The Original Taste",
  "image_paths": ["product_images/001_front.jpg", "product_images/001_back.jpg"],
  "confidence_scores": {
    "item_name": 0.92,
    "barcode": 0.98,
    ...
  },
  "overall_confidence": 0.92,
  "needs_review": false,
  "is_duplicate_candidate": false,
  "duplicate_of": null,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

---

### 3. Create Product Record
```
POST /api/products/
Content-Type: application/json
```

**Request Body:**
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
  "tagline": "The Original Taste",
  "image_paths": ["product_images/001_front.jpg"]
}
```

---

### 4. Update Product Record
```
PATCH /api/products/{id}/
Content-Type: application/json
```

**Request Body:** (only include fields to update)
```json
{
  "promotion": "50% EXTRA FREE, BUY ONE GET ONE HALF PRICE"
}
```

---

### 5. Delete Product Record
```
DELETE /api/products/{id}/
```

---

### 6. Analyze Single Image
```
POST /api/products/analyze/
Content-Type: multipart/form-data
```

**Request:**
```bash
curl -X POST http://localhost:8000/api/products/analyze/ \
  -F "image=@product_front.jpg"
```

**Response:**
```json
{
  "extracted": {
    "item_name": "Blue Band Margarine Original 500G Tub",
    "barcode": "6001066022011",
    ...
  },
  "confidence": {
    "item_name": 0.92,
    "barcode": 0.98,
    ...
  },
  "method": "gpt4o",
  "potential_duplicates": [],
  "images_processed": 1
}
```

---

### 7. Analyze Multiple Images
```
POST /api/products/analyze_multi/
Content-Type: multipart/form-data
```

**Request:**
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
    "item_name": "...",
    "promotion": "50% EXTRA FREE, BUY ONE GET ONE HALF PRICE",
    ...
  },
  "confidence": {...},
  "method": "gpt4o",
  "potential_duplicates": [...],
  "images_processed": 3,
  "images_failed": 0
}
```

---

### 8. Check for Duplicates
```
POST /api/products/check_duplicates/
Content-Type: application/json
```

**Request:**
```json
{
  "barcode": "6001066022011",
  "brand": "Blue Band",
  "item_name": "Blue Band Margarine Original 500G Tub",
  "weight": "500G"
}
```

**Response:**
```json
{
  "potential_duplicates": [
    {
      "id": 5,
      "barcode": "6001066022011",
      "brand": "Blue Band",
      "item_name": "Blue Band Margarine Original 500G Tub",
      "weight": "500G",
      "overall_confidence": 0.92
    }
  ]
}
```

---

### 9. Batch Process Directory
```
POST /api/products/batch_process/
Content-Type: application/json
```

**Request:**
```json
{
  "images_dir": "/path/to/product_images",
  "max_products": null,
  "update_existing": true
}
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
  "results": [
    {
      "product_id": "001",
      "status": "created",
      "record_id": 1,
      "images_processed": 3,
      "images_failed": 0,
      "extracted_data": {...},
      "confidence": {...},
      "error": null
    },
    ...
  ]
}
```

---

### 10. Evaluate Predictions
```
GET /api/products/evaluate/
```

**Query Parameters:**
- `include_low_confidence=true` — Include records with confidence < 0.7

**Response:**
```json
{
  "total_predictions": 42,
  "total_ground_truth": 45,
  "matched_pairs": 42,
  "unmatched_predictions": 0,
  "unmatched_ground_truth": 3,
  "overall_accuracy": 0.856,
  "field_stats": {
    "item_name": {
      "exact_matches": 40,
      "partial_matches": 2,
      "mismatches": 0,
      "missing": 0,
      "false_positives": 0
    },
    "barcode": {
      "exact_matches": 42,
      ...
    },
    ...
  },
  "comparisons": [
    {
      "prediction_id": 1,
      "ground_truth_id": 1,
      "overall_accuracy": 0.923,
      "fields_correct": 12,
      "fields_total": 13,
      "field_details": [
        {
          "field": "item_name",
          "predicted": "Blue Band Margarine Original 500G Tub",
          "ground_truth": "Blue Band Margarine Original 500G Tub",
          "match": "exact",
          "similarity": 1.0,
          "correct": true
        },
        ...
      ],
      "prediction_confidence": 0.92,
      "ground_truth_confidence": 1.0
    },
    ...
  ]
}
```

---

### 11. Export Records (CSV)
```
GET /api/products/export/?format=csv
```

**Query Parameters:**
- `format=csv` (default) or `format=excel`
- `ids=1,2,3,...` (optional, specific records)

**Response:** Binary file (predictions.csv)

---

### 12. Export Records (Excel)
```
GET /api/products/export/?format=excel
```

**Response:** Binary file (predictions.xlsx)

---

## Management Commands

### Import Ground Truth
```bash
python manage.py import_ground_truth [OPTIONS]
```

**Options:**
- `--xlsx PATH` — Path to Excel file (default: repo_root/output_results.xlsx)
- `--clear` — Delete existing records before importing

**Example:**
```bash
python manage.py import_ground_truth --xlsx ground_truth.xlsx --clear
```

---

### Batch Process Images
```bash
python manage.py batch_process [OPTIONS]
```

**Options:**
- `--images-dir PATH` — Path to images directory
- `--max-products N` — Limit products to process
- `--skip-existing` — Don't update existing records

**Example:**
```bash
python manage.py batch_process --images-dir /data/product_images --max-products 10
```

---

### Evaluate Predictions
```bash
python manage.py evaluate_predictions [OPTIONS]
```

**Options:**
- `--include-low-confidence` — Include records with confidence < 0.7
- `--output FILE` — Save report to JSON file

**Example:**
```bash
python manage.py evaluate_predictions --output report.json
```

---

## Error Handling

All endpoints return appropriate HTTP status codes:

- **200 OK** — Success
- **201 Created** — Record created successfully
- **204 No Content** — Deletion successful
- **400 Bad Request** — Invalid input
- **404 Not Found** — Record not found
- **500 Internal Server Error** — Server error

**Error Response Format:**
```json
{
  "error": "Image analysis failed: API rate limit exceeded"
}
```

---

## Performance Tips

1. **Use Batch Processing:** Process multiple images at once for better aggregation
2. **Limit Request Size:** Max 10 images per analyze_multi request
3. **Cache Results:** Use export endpoint to cache predictions
4. **Pagination:** List endpoint uses Django pagination (limit=20 by default)
5. **Filtering:** Use query parameters to reduce result set

---

## Development

### Running Tests
```bash
python manage.py test apps.products
```

### Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Admin Panel
```
http://localhost:8000/admin/
```

---

## Production Deployment

1. **Set DEBUG=False** in settings.py
2. **Add ALLOWED_HOSTS**
3. **Use PostgreSQL** instead of SQLite
4. **Add authentication** (Token or JWT)
5. **Enable HTTPS**
6. **Configure CORS** for frontend
7. **Use Gunicorn + Nginx**

Example settings for production:
```python
DEBUG = False
ALLOWED_HOSTS = ['api.example.com']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'imdb_db',
        'USER': 'postgres',
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': 'db.example.com',
    }
}
CORS_ALLOWED_ORIGINS = [
    'https://example.com',
    'https://app.example.com',
]
```

---

## Support

For issues, check:
1. OpenAI API status and rate limits
2. Image quality and format
3. Database connectivity
4. Environment variables (OPENAI_API_KEY, MEDIA_ROOT)
