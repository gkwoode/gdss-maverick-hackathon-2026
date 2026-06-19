"""
train_openai.py
===============
Converts train.json (produced by prepare_dataset.py) into OpenAI fine-tuning
JSONL format for GPT-4o / GPT-4o-mini vision models, then optionally uploads
the file and launches a fine-tuning job.

Output files (written to ml/data/):
  train_finetune.jsonl   – fine-tuning conversations (images encoded as base64)
  val_finetune.jsonl     – validation conversations (first 10 % of train set)

Usage:
  # Step 1 – just build the JSONL (no upload)
  python ml/train_openai.py

  # Step 2 – build + upload + start fine-tuning job
  python ml/train_openai.py --upload --model gpt-4o-mini-2024-07-18

Requirements:
  pip install openai requests
  Set OPENAI_API_KEY in backend/.env or as an environment variable.
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

# -- Paths ---------------------------------------------------------------------
ROOT     = Path(__file__).resolve().parent.parent
ML_DIR   = ROOT / "ml"
DATA_DIR = ML_DIR / "data"

# Load env (OPENAI_API_KEY, BACKEND_URL, etc.) from backend/.env via client
sys.path.insert(0, str(ML_DIR))
from backend_client import _load_env  # noqa: E402
_load_env()

# ── Prompt template ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert IMDB (Item Master Data Base) data extractor for FMCG products.
Given one or more product images, extract the following 13 attributes exactly as they appear on the label:

1. ITEM_NAME        – Full descriptive product name (BRAND + WEIGHT + PACKAGING + PRODUCT TYPE + MANUFACTURER)
2. BARCODE          – Numeric barcode digits only
3. MANUFACTURER     – Full legal name of manufacturing company
4. BRAND            – Brand name as printed on label
5. WEIGHT           – Net weight/volume with unit in UPPERCASE (e.g. 250G, 500 ML, 1.5 KG)
6. PACKAGING TYPE   – Packaging form: TUB / BOTTLE / CAN / JAR / SACHET / BOX / BAG / POUCH / TUBE / TETRA PAK
7. COUNTRY          – Country of manufacture or packing
8. VARIANT          – Product variant (ORIGINAL, LOW FAT, LIGHT, SALTED, etc.) — empty string if none
9. PRODUCT TYPE     – Product category (MARGARINE, MAYONNAISE, BUTTER, YOGHURT, JUICE, etc.)
10. FRAGRANCE_FLAVOR – Flavor or fragrance — empty string if not applicable
11. PROMOTION       – On-pack promo text (e.g. 50% OFF) — empty string if none
12. ADDONS          – Bundled extras (e.g. SPOON INCLUDED) — empty string if none
13. TAGLINE         – Short promotional tagline printed on pack — empty string if none

Return ONLY a valid JSON object with these exact keys:
item_name, barcode, manufacturer, brand, weight, packaging_type, country,
variant, product_type, fragrance_flavor, promotion, addons, tagline

Do not include any explanation outside the JSON."""

EXTRACTION_PROMPT = "Extract all 13 IMDB attributes from the product image(s) and return them as a JSON object."



def image_to_data_url(path: Path) -> str:
    """Encode image file as base64 data URL for the OpenAI API."""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/jpeg;base64,{b64}"


def build_conversation(entry: dict) -> dict:
    """
    Build a single fine-tuning conversation dict for one product entry.

    Messages format:
      system  → extraction instructions
      user    → image(s) + extraction prompt
      assistant → ground-truth JSON
    """
    # Build user content: up to 4 images (cost control for fine-tuning)
    image_paths = entry["images"][:4]
    user_content = []
    for rel_path in image_paths:
        abs_path = ROOT / rel_path
        if abs_path.exists():
            user_content.append({
                "type": "image_url",
                "image_url": {"url": image_to_data_url(abs_path), "detail": "low"},
            })
    user_content.append({"type": "text", "text": EXTRACTION_PROMPT})

    # Ground-truth assistant response
    labels = entry["labels"]
    assistant_json = {
        "item_name":        labels.get("item_name", ""),
        "barcode":          labels.get("barcode", ""),
        "manufacturer":     labels.get("manufacturer", ""),
        "brand":            labels.get("brand", ""),
        "weight":           labels.get("weight", ""),
        "packaging_type":   labels.get("packaging_type", ""),
        "country":          labels.get("country", ""),
        "variant":          labels.get("variant", ""),
        "product_type":     labels.get("product_type", ""),
        "fragrance_flavor": labels.get("fragrance_flavor", ""),
        "promotion":        labels.get("promotion", ""),
        "addons":           labels.get("addons", ""),
        "tagline":          labels.get("tagline", ""),
    }

    return {
        "messages": [
            {"role": "system",    "content": SYSTEM_PROMPT},
            {"role": "user",      "content": user_content},
            {"role": "assistant", "content": json.dumps(assistant_json, ensure_ascii=False)},
        ]
    }


def write_jsonl(conversations: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for conv in conversations:
            f.write(json.dumps(conv, ensure_ascii=False) + "\n")
    size_kb = path.stat().st_size / 1024
    print(f"  Saved {len(conversations):3d} examples → {path.relative_to(ROOT)}  ({size_kb:.1f} KB)")


def upload_and_finetune(
    train_jsonl: Path,
    val_jsonl: Path,
    model: str,
    n_epochs: int,
    suffix: str,
) -> None:
    """Upload JSONL files and launch an OpenAI fine-tuning job."""
    from openai import OpenAI  # import here so script works without openai installed

    client = OpenAI()

    print("\n[Uploading training file …]")
    with open(train_jsonl, "rb") as f:
        train_file = client.files.create(file=f, purpose="fine-tune")
    print(f"  Training file ID: {train_file.id}")

    val_file_id = None
    if val_jsonl.exists() and val_jsonl.stat().st_size > 0:
        print("[Uploading validation file …]")
        with open(val_jsonl, "rb") as f:
            val_file = client.files.create(file=f, purpose="fine-tune")
        val_file_id = val_file.id
        print(f"  Validation file ID: {val_file_id}")

    print(f"\n[Launching fine-tuning job: {model}, {n_epochs} epochs …]")
    kwargs = {
        "training_file": train_file.id,
        "model": model,
        "hyperparameters": {"n_epochs": n_epochs},
    }
    if suffix:
        kwargs["suffix"] = suffix
    if val_file_id:
        kwargs["validation_file"] = val_file_id

    job = client.fine_tuning.jobs.create(**kwargs)
    print(f"  Job ID    : {job.id}")
    print(f"  Status    : {job.status}")
    print(f"\n  Monitor with:")
    print(f"    python -c \"from openai import OpenAI; c=OpenAI(); print(c.fine_tuning.jobs.retrieve('{job.id}'))\"")
    print(f"\n  Once complete, set OPENAI_MODEL={job.fine_tuned_model} in backend/.env")

    # Save job metadata
    job_info = {"job_id": job.id, "model": model, "status": job.status}
    out = DATA_DIR / "finetune_job.json"
    with open(out, "w") as f:
        json.dump(job_info, f, indent=2)
    print(f"\n  Job info saved → {out.relative_to(ROOT)}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build OpenAI fine-tuning JSONL from train.json")
    parser.add_argument("--upload",   action="store_true",                      help="Upload JSONL and start fine-tuning job")
    parser.add_argument("--model",    default="gpt-4o-mini-2024-07-18",         help="Base model to fine-tune")
    parser.add_argument("--epochs",   type=int, default=3,                      help="Number of training epochs")
    parser.add_argument("--suffix",   default="imdb-extractor",                 help="Fine-tuned model name suffix")
    parser.add_argument("--val-frac", type=float, default=0.1,                  help="Fraction of train set to use as validation")
    args = parser.parse_args()

    train_json = DATA_DIR / "train.json"
    if not train_json.exists():
        print(f"[ERROR] {train_json} not found. Run prepare_dataset.py first.")
        sys.exit(1)

    print(f"\n[1/3] Loading train.json …")
    with open(train_json) as f:
        train_data = json.load(f)
    print(f"      {len(train_data)} training products loaded.")

    # Split off a small validation set from within train
    n_val = max(1, round(len(train_data) * args.val_frac))
    import random
    rng = random.Random(0)
    shuffled = train_data.copy()
    rng.shuffle(shuffled)
    val_data   = shuffled[:n_val]
    finetune_data = shuffled[n_val:]
    print(f"      Fine-tune: {len(finetune_data)} | Validation: {len(val_data)}")

    print("\n[2/3] Building conversation JSONL (encoding images as base64) …")
    print("      This may take a minute for large image sets …")

    train_convs = []
    skipped = 0
    for entry in finetune_data:
        available = [p for p in entry["images"] if (ROOT / p).exists()]
        if not available:
            skipped += 1
            continue
        entry = {**entry, "images": available}
        train_convs.append(build_conversation(entry))

    val_convs = []
    for entry in val_data:
        available = [p for p in entry["images"] if (ROOT / p).exists()]
        if not available:
            continue
        entry = {**entry, "images": available}
        val_convs.append(build_conversation(entry))

    if skipped:
        print(f"      [WARN] Skipped {skipped} products with no accessible images.")

    train_jsonl = DATA_DIR / "train_finetune.jsonl"
    val_jsonl   = DATA_DIR / "val_finetune.jsonl"

    print()
    write_jsonl(train_convs, train_jsonl)
    write_jsonl(val_convs,   val_jsonl)

    print("\n[3/3] JSONL files ready.")
    if args.upload:
        upload_and_finetune(train_jsonl, val_jsonl, args.model, args.epochs, args.suffix)
    else:
        print("\n  To upload and start fine-tuning, run:")
        print(f"    python ml/train_openai.py --upload --model {args.model} --epochs {args.epochs}")


if __name__ == "__main__":
    main()
