"""
evaluate.py
===========
Scores predictions from the backend API against ground-truth labels.

All image analysis is performed by calling the running Django backend via
ml/backend_client.py.  No direct Django imports are needed here.

Metrics per field:
  exact_match  - prediction exactly equals ground truth (case-insensitive)
  non_empty    - field was populated
  lev_sim      - edit-distance similarity (0-1)

Usage:
  python ml/evaluate.py
  python ml/evaluate.py --split test        # default (held-out set)
  python ml/evaluate.py --split train       # sanity-check on train set
  python ml/evaluate.py --limit 5 --verbose
  python ml/evaluate.py --backend http://host:8000
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
from backend_client import BACKEND_URL, BackendError, batch_analyze, health_check  # noqa: E402

# -- Schema --------------------------------------------------------------------
LABEL_FIELDS = [
    "item_name", "barcode", "manufacturer", "brand", "weight",
    "packaging_type", "country", "variant", "product_type",
    "fragrance_flavor", "promotion", "addons", "tagline",
]


# -- Scoring helpers -----------------------------------------------------------

def levenshtein_similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[:], i
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev[j - 1] + cost)
    return 1.0 - dp[n] / max(m, n)


def score_prediction(predicted: dict, ground_truth: dict) -> dict:
    scores = {}
    for field in LABEL_FIELDS:
        pred = str(predicted.get(field) or "").strip().upper()
        true = str(ground_truth.get(field) or "").strip().upper()
        scores[field] = {
            "predicted":    predicted.get(field, ""),
            "ground_truth": ground_truth.get(field, ""),
            "exact_match":  int(pred == true),
            "non_empty":    int(bool(pred)),
            "lev_sim":      round(levenshtein_similarity(pred, true), 3),
        }
    return scores


def aggregate_scores(field_scores: dict) -> dict:
    em  = [v["exact_match"] for v in field_scores.values()]
    lev = [v["lev_sim"]     for v in field_scores.values()]
    ne  = [v["non_empty"]   for v in field_scores.values()]
    return {
        "field_accuracy":     round(sum(em)  / len(em),  4),
        "avg_lev_similarity": round(sum(lev) / len(lev), 4),
        "coverage":           round(sum(ne)  / len(ne),  4),
        "exact_fields":       sum(em),
        "total_fields":       len(em),
    }


def print_diff_table(pid: str, n_images: int, field_scores: dict) -> None:
    w = 34
    print(f"\n  Product: {pid}  (images: {n_images})")
    print(f"  {'Field':<22} {'Predicted':<{w}} {'Ground Truth':<{w}} {'EM':>4} {'Lev':>6}")
    print(f"  {'-'*22} {'-'*w} {'-'*w} {'-'*4} {'-'*6}")
    for field, s in field_scores.items():
        em   = "OK" if s["exact_match"] else "X "
        lev  = f"{s['lev_sim']:.2f}"
        pred = str(s["predicted"]    or "-")[:w]
        true = str(s["ground_truth"] or "-")[:w]
        print(f"  {field:<22} {pred:<{w}} {true:<{w}} {em:>4} {lev:>6}")


# -- Main ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate image analysis via backend API")
    parser.add_argument("--split",   choices=["test", "train", "all"], default="test")
    parser.add_argument("--limit",   type=int,   default=None,  help="Only evaluate first N products")
    parser.add_argument("--verbose", action="store_true",         help="Print per-product field diffs")
    parser.add_argument("--delay",   type=float, default=1.0,    help="Seconds between API calls")
    parser.add_argument("--backend", type=str,   default=None,   help="Override backend URL")
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

    print(f"Evaluating {len(data)} products ({args.split} split) ...")
    print("-" * 70)

    raw_results = batch_analyze(data, max_images=4, rate_limit_delay=args.delay, verbose=True)

    eval_results: list[dict] = []
    all_exact: dict[str, list] = {f: [] for f in LABEL_FIELDS}
    all_lev:   dict[str, list] = {f: [] for f in LABEL_FIELDS}

    for entry, raw in zip(data, raw_results):
        if raw["error"] or raw["response"] is None:
            print(f"  [SKIP] {raw['product_id']}: {raw['error']}")
            continue

        predicted    = raw["response"].get("extracted", {})
        ground_truth = entry["labels"]
        field_scores = score_prediction(predicted, ground_truth)
        summary      = aggregate_scores(field_scores)

        for f in LABEL_FIELDS:
            all_exact[f].append(field_scores[f]["exact_match"])
            all_lev[f].append(field_scores[f]["lev_sim"])

        eval_results.append({
            "product_id":   raw["product_id"],
            "num_images":   raw["num_images"],
            "method":       raw["response"].get("method", "unknown"),
            "field_scores": field_scores,
            "summary":      summary,
        })

        if args.verbose:
            print_diff_table(raw["product_id"], raw["num_images"], field_scores)

    if not eval_results:
        print("\n[WARN] No results to score.")
        return

    n = len(eval_results)
    overall_acc = sum(r["summary"]["field_accuracy"]     for r in eval_results) / n
    overall_lev = sum(r["summary"]["avg_lev_similarity"] for r in eval_results) / n

    per_field_acc = {f: round(sum(all_exact[f]) / max(len(all_exact[f]), 1), 4) for f in LABEL_FIELDS}
    per_field_lev = {f: round(sum(all_lev[f])   / max(len(all_lev[f]),   1), 4) for f in LABEL_FIELDS}

    print("\n" + "=" * 70)
    print("  EVALUATION RESULTS")
    print("=" * 70)
    print(f"\n  Products evaluated      : {n}")
    print(f"  Overall field accuracy  : {overall_acc:.2%}")
    print(f"  Overall Levenshtein sim : {overall_lev:.3f}")
    print(f"\n  {'Field':<22} {'Exact Match':>12} {'Lev Sim':>10}")
    print(f"  {'-'*22} {'-'*12} {'-'*10}")
    for f in LABEL_FIELDS:
        bar = "#" * int(per_field_acc[f] * 10)
        print(f"  {f:<22} {per_field_acc[f]:>11.1%}  {per_field_lev[f]:>9.3f}  {bar}")
    print("=" * 70)

    out_json = DATA_DIR / "evaluation_results.json"
    payload = {
        "overall": {
            "split":                    args.split,
            "products_evaluated":       n,
            "overall_field_accuracy":   round(overall_acc, 4),
            "overall_lev_similarity":   round(overall_lev, 4),
            "per_field_exact_match":    per_field_acc,
            "per_field_lev_similarity": per_field_lev,
        },
        "per_product": eval_results,
    }
    with open(out_json, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2, ensure_ascii=False)

    rows = [{"product_id": r["product_id"], **r["summary"]} for r in eval_results]
    pd.DataFrame(rows).to_csv(DATA_DIR / "evaluation_summary.csv", index=False)

    print(f"\n  Results -> {out_json.relative_to(ROOT)}")
    print(f"  Summary -> ml/data/evaluation_summary.csv\n")


if __name__ == "__main__":
    main()
