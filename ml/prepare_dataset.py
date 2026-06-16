"""
prepare_dataset.py
==================
Reads product_images/ and output_results.xlsx, links images to ground-truth
labels, then splits at the PRODUCT level (not image level) into train / test
sets to avoid data leakage.

Output files (written to ml/data/):
  train.json        – list of product dicts with images + labels (80 %)
  test.json         – list of product dicts with images + labels (20 %)
  dataset.json      – full combined dataset with split annotations
  train_index.csv   – human-readable train manifest
  test_index.csv    – human-readable test manifest

Usage:
  python ml/prepare_dataset.py
  python ml/prepare_dataset.py --test-size 0.2 --seed 42
"""

import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "product_images"
EXCEL_PATH = ROOT / "output_results.xlsx"
OUT_DIR = ROOT / "ml" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Ground-truth column mapping (Excel header → canonical key) ────────────────
COLUMN_MAP = {
    "ITEM_NAME":        "item_name",
    "BARCODE":          "barcode",
    "MANUFACTURER":     "manufacturer",
    "BRAND":            "brand",
    "WEIGHT":           "weight",
    "PACKAGING  TYPE":  "packaging_type",   # Excel has double-space
    "PACKAGING TYPE":   "packaging_type",   # fallback single-space
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_excel_labels(path: Path) -> list[dict]:
    """Return a list of label dicts, one per row in the Excel file."""
    df = pd.read_excel(path)

    # Normalise column names using the map
    rename = {}
    for col in df.columns:
        key = col.strip()
        if key in COLUMN_MAP:
            rename[col] = COLUMN_MAP[key]
    df = df.rename(columns=rename)

    records = []
    for _, row in df.iterrows():
        label = {}
        for field in LABEL_FIELDS:
            raw = row.get(field, None)
            # Treat NaN / float NaN as empty string
            if raw is None or (isinstance(raw, float) and math.isnan(raw)):
                label[field] = ""
            elif field == "barcode":
                # Barcodes stored as float (e.g. 6.034e12) → integer string
                try:
                    label[field] = str(int(float(raw)))
                except (ValueError, TypeError):
                    label[field] = str(raw).strip()
            else:
                label[field] = str(raw).strip()
        records.append(label)
    return records


def group_images_by_product(images_dir: Path) -> dict[str, list[str]]:
    """
    Returns {product_id: [relative_path, ...]} sorted by filename within each group.
    Relative paths are relative to the workspace ROOT.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for fname in sorted(os.listdir(images_dir)):
        if not fname.lower().endswith(".jpg"):
            continue
        product_id = fname.split("_")[0]
        rel = str(Path("product_images") / fname)
        groups[product_id].append(rel)
    return dict(sorted(groups.items()))  # sort by product ID


def build_dataset(labels: list[dict], groups: dict[str, list[str]]) -> list[dict]:
    """
    Positionally match sorted product-image groups to Excel rows.

    If counts differ, print a warning and only match what aligns.
    Each entry: { product_id, images, labels, row_index }
    """
    product_ids = list(groups.keys())       # already sorted alphabetically
    n_img = len(product_ids)
    n_lbl = len(labels)

    if n_img != n_lbl:
        print(
            f"[WARN] Mismatch: {n_img} image product groups vs {n_lbl} Excel rows. "
            f"Using first {min(n_img, n_lbl)} products."
        )
    n = min(n_img, n_lbl)

    dataset = []
    for i in range(n):
        pid = product_ids[i]
        entry = {
            "product_id":  pid,
            "row_index":   i,
            "images":      groups[pid],
            "num_images":  len(groups[pid]),
            "labels":      labels[i],
        }
        dataset.append(entry)
    return dataset


def split_dataset(
    dataset: list[dict],
    test_size: float = 0.2,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """
    Splits at the product level (each product → either train OR test, never both).
    Shuffles deterministically with `seed` before splitting.
    """
    items = dataset.copy()
    rng = random.Random(seed)
    rng.shuffle(items)

    n_test = max(1, round(len(items) * test_size))
    test_set  = items[:n_test]
    train_set = items[n_test:]

    # Re-sort by product_id for readability
    train_set.sort(key=lambda x: x["product_id"])
    test_set.sort(key=lambda x: x["product_id"])
    return train_set, test_set


def save_json(data, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved {len(data):3d} records → {path.relative_to(ROOT)}")


def save_csv_index(data: list[dict], path: Path) -> None:
    rows = []
    for entry in data:
        row = {"product_id": entry["product_id"], "num_images": entry["num_images"]}
        row.update(entry["labels"])
        rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)
    print(f"  Saved CSV index    → {path.relative_to(ROOT)}")


def print_summary(train: list[dict], test: list[dict]) -> None:
    total = len(train) + len(test)
    n_train_img = sum(e["num_images"] for e in train)
    n_test_img  = sum(e["num_images"] for e in test)
    print()
    print("═" * 50)
    print("  DATASET SPLIT SUMMARY")
    print("═" * 50)
    print(f"  Total products : {total}")
    print(f"  Train products : {len(train)}  ({len(train)/total:.0%})  |  {n_train_img} images")
    print(f"  Test  products : {len(test)}   ({len(test)/total:.0%})  |  {n_test_img} images")
    print()
    print("  Label field coverage (non-empty in training set):")
    for field in LABEL_FIELDS:
        count = sum(1 for e in train if e["labels"].get(field, ""))
        pct = count / len(train) * 100
        bar = "█" * int(pct / 5)
        print(f"    {field:<20} {count:3d}/{len(train)}  {pct:5.1f}%  {bar}")
    print("═" * 50)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Prepare train/test dataset splits")
    parser.add_argument("--test-size", type=float, default=0.2, help="Fraction for test set (default: 0.2)")
    parser.add_argument("--seed",      type=int,   default=42,  help="Random seed (default: 42)")
    args = parser.parse_args()

    print(f"\n[1/4] Loading ground-truth labels from {EXCEL_PATH.name} …")
    labels = load_excel_labels(EXCEL_PATH)
    print(f"      {len(labels)} product rows loaded.")

    print(f"\n[2/4] Scanning images in {IMAGES_DIR.name}/ …")
    groups = group_images_by_product(IMAGES_DIR)
    total_imgs = sum(len(v) for v in groups.values())
    print(f"      {total_imgs} images across {len(groups)} product groups.")

    print("\n[3/4] Building dataset (positional match: sorted ProductID → Excel row) …")
    dataset = build_dataset(labels, groups)
    print(f"      {len(dataset)} matched products.")

    print(f"\n[4/4] Splitting: test_size={args.test_size:.0%}, seed={args.seed} …")
    train_set, test_set = split_dataset(dataset, test_size=args.test_size, seed=args.seed)

    # Annotate split in full dataset
    train_ids = {e["product_id"] for e in train_set}
    for entry in dataset:
        entry["split"] = "train" if entry["product_id"] in train_ids else "test"

    # Save outputs
    print()
    save_json(train_set, OUT_DIR / "train.json")
    save_json(test_set,  OUT_DIR / "test.json")
    save_json(dataset,   OUT_DIR / "dataset.json")
    save_csv_index(train_set, OUT_DIR / "train_index.csv")
    save_csv_index(test_set,  OUT_DIR / "test_index.csv")

    print_summary(train_set, test_set)
    print("\nDone. Run ml/train_openai.py next to prepare fine-tuning data.")


if __name__ == "__main__":
    main()
