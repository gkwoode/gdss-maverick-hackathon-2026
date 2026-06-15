# IMDB Auto-Fill — Item Master Database Tool

> **GDS Maverick Hackathon 2026**  
> Automatically extract 10 product attributes from a label image using AI vision, OCR, and barcode detection — then export the results to CSV / Excel for database upload.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend  (Next.js 14 · TypeScript · Tailwind CSS)         │
│  - Upload page: drag-drop image → AI extraction → edit form │
│  - Product catalog: filterable table + CSV/Excel export     │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API (JSON)
┌────────────────────────▼────────────────────────────────────┐
│  Backend  (Django 4.2 · Django REST Framework)              │
│  POST /api/products/analyze/    ← image → extracted fields  │
│  CRUD  /api/products/           ← product master records    │
│  GET  /api/products/export/     ← CSV / Excel download      │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  Extraction Pipeline        │
          │  1. GPT-4o Vision (primary) │
          │  2. pyzbar (barcode)        │
          │  3. pytesseract (OCR fallback)│
          └─────────────────────────────┘
```

## 10 IMDB Attributes Extracted

| # | Attribute | Example |
|---|-----------|---------|
| 1 | Barcode | `5901234123457` |
| 2 | Category Type | `Beverages` |
| 3 | Segment Type | `Carbonated Drinks` |
| 4 | Manufacturer | `The Coca-Cola Company` |
| 5 | Brand | `Coca-Cola` |
| 6 | Product Name | `Coca-Cola Original 500ml` |
| 7 | Weight / Unit | `500ml` |
| 8 | Packaging Type | `Bottle` |
| 9 | Country of Origin | `Ghana` |
| 10 | Promotional Messages | `No Sugar, New Formula` |

---

## Quick Start (Local)

### Prerequisites
- Python 3.11+
- Node.js 20+
- `tesseract-ocr` (for OCR fallback): `sudo apt install tesseract-ocr` or `brew install tesseract`
- `libzbar0` (for barcode): `sudo apt install libzbar0` or `brew install zbar`
- An **OpenAI API key** with GPT-4o access

### 1. Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# Run migrations
python manage.py migrate

# Create superuser (optional, for Django admin)
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

Backend runs at **http://localhost:8000**  
Django admin at **http://localhost:8000/admin**

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local

# Start development server
npm run dev
```

Frontend runs at **http://localhost:3000**

---

## Docker (Full Stack)

```bash
# Copy env files
cp backend/.env.example backend/.env
# Edit backend/.env with your OPENAI_API_KEY

cp frontend/.env.local.example frontend/.env.local

# Build and start
docker compose up --build
```

---

## API Reference

### `POST /api/products/analyze/`
Upload a product image and receive extracted IMDB attributes.

**Request:** `multipart/form-data` with `image` field.

**Response:**
```json
{
  "extracted": { "barcode": "...", "brand": "...", ... },
  "confidence": { "barcode": 0.95, "brand": 0.98, ... },
  "method": "gpt4o",
  "potential_duplicates": [...]
}
```

### `GET /api/products/`
List all IMDB records. Supports query params: `search`, `brand`, `category`, `barcode`, `needs_review`, `page`.

### `POST /api/products/`
Save a new IMDB record.

### `PATCH /api/products/{id}/`
Update an existing record.

### `GET /api/products/export/?format=csv`
Download all records as CSV. Use `format=excel` for Excel. Pass `ids=1&ids=2` to export specific records.

### `POST /api/products/check_duplicates/`
Check a candidate record for potential duplicates by barcode, brand, and product name.

---

## Key Design Decisions

- **GPT-4o Vision** is the primary extraction method — it handles complex multilingual labels, logos, and nutritional panels.
- **pyzbar** always runs in parallel to get the most reliable barcode reading.
- **pytesseract** is the no-API-key fallback for basic text and weight extraction.
- **Confidence scores** (0–1) are returned per field; fields below 0.7 are highlighted and the record is flagged `needs_review = True`.
- **Duplicate detection** runs by barcode (exact) and brand + product name + weight (fuzzy-insensitive).
- **Validation layer** normalises barcodes (digits only), weights (numeric + SI unit), countries (aliases → standard names), and packaging types before saving.

---

## Project Structure

```
gdss-maverick-hackathon-2026/
├── backend/
│   ├── imdb_project/          # Django project config
│   ├── apps/products/
│   │   ├── models.py          # IMDBRecord model
│   │   ├── serializers.py
│   │   ├── views.py           # API ViewSet + analyze/export actions
│   │   ├── urls.py
│   │   └── services/
│   │       ├── image_analyzer.py    # GPT-4o + pyzbar + OCR pipeline
│   │       ├── validator.py         # Field normalisation & validation
│   │       ├── exporter.py          # CSV / Excel generation
│   │       └── duplicate_checker.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx           # Upload & extraction page
│   │   │   └── products/page.tsx  # Product catalog
│   │   ├── components/
│   │   │   ├── ImageUpload.tsx
│   │   │   ├── IMDBForm.tsx
│   │   │   ├── ProductTable.tsx
│   │   │   ├── ExportPanel.tsx
│   │   │   ├── DuplicateAlert.tsx
│   │   │   ├── EditModal.tsx
│   │   │   └── Header.tsx
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   └── utils.ts
│   │   └── types/imdb.ts
│   ├── package.json
│   └── Dockerfile
└── docker-compose.yml
```
