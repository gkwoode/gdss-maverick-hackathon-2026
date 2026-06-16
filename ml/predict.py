"""
predict.py
==========
Generates predictions.csv and predictions.xlsx by sending product images
to the running Django backend and collecting the extracted IMDB attributes.

All heavy lifting (GPT-4o vision / OCR / validation) runs inside the backend.
This script just orchestrates the HTTP calls via ml/backend_client.py.

Output files (at workspace root):
  predictions.csv   – 13-column hackathon submission file
  predictions.xlsx  – same data as Excel

Usage:
  python ml/predict.py                          # run all products
  python ml/predict.py --split test             # only test split
  python ml/predict.py --split train            # only train split
  python ml/predict.py --limit 5                # quick smoke test
  python ml/predict.py --save-to-db             # also persist records in DB
  python ml/predict.py --backend http://host:8000
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# -- Paths ---------------------------------------------------------------------
ROOT     = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "ml" / "data"

# -- Backend client ------------------------------------------------------------
sys.path.insert(0, str(ROOT / "ml"))
from backend_client import (  # noqa: E402
    BACKEND_URL,
    BackendError,
    batch_analyze,
    create_record,
    health_check,
)

# -- Column mapping (internal key -> CSV header) --------------------------------
EXPORT_COLUMNS = [
    ("item_name",        "ITEM_NAME"),
    ("barcode",          "BARCODE"),
    ("manufacturer",     "MANUFACTURER"),
    ("brand",            "BRAND"),
    ("weight",           "WEIGHT"),
    ("packaging_type",   "PACKAGING TYPE"),
    ("country",          "COUNTRY"),
    ("variant",          "VARIANT"),
    ("product_type",     "TYPE"),
    ("fragrance_flavor", "FRAGRANCE_FLAVOR"),
    ("promotion",        "PROMOTION"),
    ("addons",           "ADDONS"),
    ("tagline",          "TAGLINE"),
]


# -- Main ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate predictions via backend API")
    parser.add_argument("--split",      choices=["all", "train", "test"], default="all")
    parser.add_argument("--limit",      type=int,   default=None)
    parser.add_argument("--delay",      type=float, default=1.0, help="Seconds between API calls")
    parser.add_argument("--save-to-db", action="store_true",     help="Persist each record in the backend DB")
    parser.add_argument("--backend",    type=str,   default=None)
    args = parser.parse_args()

    if args.backend:
        import backend_client as _bc
        _bc.BACKEND_URL = args.backend.rstrip("/")

    print(f"\nConnecting to backend at {BACKEND_URL} ...")
    if not health_check():
        print(f"\n[ERROR] Backend not reachable at {BACKEND_URL}")
        print("  Start it: cd backend && .\\venv\\Scripts\\python.exe manage.py runserver")
        sys.exit(1)
    print("  Backend is up.\n")

    src = DATA_DIR / ("dataset.json" if args.split == "all" else f"{args.split}.json")
    if not src.exists():
        print(f"[ERROR] {src} not found. Run ml/prepare_dataset.py first.")
        sys.exit(1)

    with open(src) as f:
        data = json.load(f)

    if args.split != "all":
        data = [e for e in data if e.get("split", args.split) == args.split]
    if args.limit:
        data = data[:args.limit]

    print(f"Generating predictions for {len(data)} products ({args.split} split) ...")
    print("-" * 70)

    raw_results = batch_analyze(data, max_images=4, rate_limit_delay=args.delay, verbose=True)

    rows = []
    saved = 0
    for entry, raw in zip(data, raw_results):
        if raw["error"] or raw["response"] is None:
            print(f"  [SKIP] {raw['product_id']}: {raw['error']}")
            continue

        extracted = raw["response"].get("extracted", {})
        confidence = raw["response"].get("confidence", {})

        # Build submission row
        row = {"product_id": raw["product_id"]}
        for field, col in EXPORT_COLUMNS:
            row[col] = extracted.get(field, "") or ""
        rows.append(row)

        # Optionally persist in backend DB
        if args.save_to_db:
            try:
                payload = {**extracted, "confidence_scores": confidence}
                create_record(payload)
                saved += 1
            except BackendError as exc:
                print(f"  [WARN] DB save failed for {raw['product_id']}: {exc}")

    if not rows:
        print("\n[WARN] No predictions generated.")
        return

    # Build export dataframe (drop internal product_id column)
    df = pd.DataFrame(rows)
    export_df = df[[col for _, col in EXPORT_COLUMNS]]

    csv_path  = ROOT / "predictions.csv"
    xlsx_path = ROOT / "predictions.xlsx"
    export_df.to_csv(csv_path,  index=False, encoding="utf-8-sig")
    export_df.to_excel(xlsx_path, index=False)

    print(f"\n  Rows      : {len(export_df)}")
    print(f"  Columns   : {len(export_df.columns)}")
    print(f"  CSV       -> predictions.csv")
    print(f"  Excel     -> predictions.xlsx")
    if args.save_to_db:
        print(f"  DB records saved : {saved}")
    print()


if __name__ == "__main__":
    main()
