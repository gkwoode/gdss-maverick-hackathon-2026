"""
Management command: import_ground_truth
=======================================
Seeds the database from output_results.xlsx (the hackathon ground-truth file).

Usage:
    python manage.py import_ground_truth
    python manage.py import_ground_truth --clear   # wipe existing records first
    python manage.py import_ground_truth --xlsx path/to/file.xlsx
"""

import math
from collections import defaultdict
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from apps.products.models import IMDBRecord

# ── Column mapping (Excel header → Django field name) ─────────────────────────
COLUMN_MAP = {
    "ITEM_NAME":        "item_name",
    "BARCODE":          "barcode",
    "MANUFACTURER":     "manufacturer",
    "BRAND":            "brand",
    "WEIGHT":           "weight",
    "PACKAGING  TYPE":  "packaging_type",   # double-space variant
    "PACKAGING TYPE":   "packaging_type",   # single-space fallback
    "COUNTRY":          "country",
    "VARIANT":          "variant",
    "TYPE":             "product_type",
    "FRAGRANCE_FLAVOR": "fragrance_flavor",
    "PROMOTION":        "promotion",
    "ADDONS":           "addons",
    "TAGLINE":          "tagline",
}

LABEL_FIELDS = [
    "item_name", "barcode", "manufacturer", "brand", "weight",
    "packaging_type", "country", "variant", "product_type",
    "fragrance_flavor", "promotion", "addons", "tagline",
]

# Fields that default to empty string (not null) when missing
EMPTY_STRING_FIELDS = {"variant", "fragrance_flavor", "promotion", "addons", "tagline"}


class Command(BaseCommand):
    help = "Import ground-truth product records from output_results.xlsx into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--xlsx",
            type=str,
            default=None,
            help="Path to the Excel file (defaults to <repo_root>/output_results.xlsx)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing IMDBRecord rows before importing",
        )

    def handle(self, *args, **options):
        # ── Resolve repo root (5 levels up from this file) ────────────────────
        repo_root = Path(__file__).resolve().parents[5]

        # ── Resolve Excel path ────────────────────────────────────────────────
        if options["xlsx"]:
            xlsx_path = Path(options["xlsx"]).resolve()
        else:
            # Try repo root first, then one level up (where the file may live)
            xlsx_path = repo_root / "output_results.xlsx"
            if not xlsx_path.exists():
                xlsx_path = repo_root.parent / "output_results.xlsx"

        if not xlsx_path.exists():
            raise CommandError(f"Excel file not found: {xlsx_path}")

        # ── Resolve product_images dir (always inside repo root) ──────────────
        images_dir = repo_root / "product_images"

        # ── Optional clear ────────────────────────────────────────────────────
        if options["clear"]:
            count = IMDBRecord.objects.count()
            IMDBRecord.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing records."))

        # ── Load Excel ────────────────────────────────────────────────────────
        self.stdout.write(f"Reading {xlsx_path} …")
        df = pd.read_excel(xlsx_path)

        # Normalise column names
        rename = {}
        for col in df.columns:
            key = col.strip()
            if key in COLUMN_MAP:
                rename[col] = COLUMN_MAP[key]
        df = df.rename(columns=rename)

        # ── Group images by product ───────────────────────────────────────────
        image_groups: dict[str, list[str]] = defaultdict(list)
        if images_dir.exists():
            import os
            for fname in sorted(os.listdir(images_dir)):
                if fname.lower().endswith(".jpg"):
                    product_id = fname.split("_")[0]
                    image_groups[product_id].append(f"product_images/{fname}")

        sorted_product_ids = sorted(image_groups.keys())

        # ── Import rows ───────────────────────────────────────────────────────
        created = 0
        skipped = 0

        for row_idx, (_, row) in enumerate(df.iterrows()):
            fields: dict = {}
            for field in LABEL_FIELDS:
                raw = row.get(field)
                if raw is None or (isinstance(raw, float) and math.isnan(raw)):
                    fields[field] = "" if field in EMPTY_STRING_FIELDS else None
                elif field == "barcode":
                    try:
                        fields[field] = str(int(float(raw)))
                    except (ValueError, TypeError):
                        fields[field] = str(raw).strip() or None
                else:
                    val = str(raw).strip()
                    fields[field] = val if val else ("" if field in EMPTY_STRING_FIELDS else None)

            # Attach matching image paths positionally
            if row_idx < len(sorted_product_ids):
                pid = sorted_product_ids[row_idx]
                fields["image_paths"] = image_groups[pid]
            else:
                fields["image_paths"] = []

            # Set high confidence for ground-truth records
            fields["confidence_scores"] = {f: 1.0 for f in LABEL_FIELDS}
            fields["overall_confidence"] = 1.0
            fields["needs_review"] = False

            # Skip completely blank rows
            has_data = any(
                fields.get(f) for f in ("item_name", "barcode", "brand")
            )
            if not has_data:
                skipped += 1
                continue

            IMDBRecord.objects.create(**fields)
            created += 1
            if created % 10 == 0:
                self.stdout.write(f"  … {created} records imported")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Imported {created} records. Skipped {skipped} blank rows."
            )
        )
