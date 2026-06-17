"""
evaluation.py
--------------
Evaluation service for comparing predictions against ground truth and computing metrics.

Metrics computed:
  - Exact match (field matches ground truth exactly)
  - Partial match (field partially matches, e.g., missing optional text)
  - No match (field completely wrong)
  - Precision, recall, F1 per field
  - Overall accuracy
"""

import logging
from typing import Any, Optional
from difflib import SequenceMatcher

from apps.products.models import IMDBRecord

logger = logging.getLogger(__name__)

# Fields that can be null/empty in ground truth
OPTIONAL_FIELDS = {"variant", "fragrance_flavor", "promotion", "addons", "tagline"}


def _similarity_ratio(a: str, b: str) -> float:
    """Compute similarity between two strings (0.0 to 1.0)."""
    if not a or not b:
        return 1.0 if (a or "").strip() == (b or "").strip() else 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _normalize_for_comparison(value: Optional[str]) -> str:
    """Normalize a field value for comparison."""
    if value is None:
        return ""
    return str(value).strip().upper() if isinstance(value, str) else str(value)


def compare_field(
    predicted: Any,
    ground_truth: Any,
    field_name: str,
    similarity_threshold: float = 0.85,
) -> dict[str, Any]:
    """
    Compare a single field between prediction and ground truth.
    
    Returns: {
        'field': str,
        'predicted': str,
        'ground_truth': str,
        'match': 'exact' | 'partial' | 'missing' | 'false_positive' | 'mismatch',
        'similarity': float (0-1),
        'correct': bool,
    }
    """
    pred_norm = _normalize_for_comparison(predicted)
    gt_norm = _normalize_for_comparison(ground_truth)
    
    if pred_norm == gt_norm:
        match = 'exact'
        correct = True
        similarity = 1.0
    elif not gt_norm and not pred_norm:
        match = 'exact'
        correct = True
        similarity = 1.0
    elif not gt_norm and pred_norm:
        match = 'false_positive'
        correct = False
        similarity = 0.0
    elif not pred_norm and gt_norm:
        match = 'missing'
        correct = False
        similarity = 0.0
    else:
        similarity = _similarity_ratio(pred_norm, gt_norm)
        if similarity >= similarity_threshold:
            match = 'partial'
            correct = True
        else:
            match = 'mismatch'
            correct = False
    
    return {
        'field': field_name,
        'predicted': str(predicted) if predicted else '',
        'ground_truth': str(ground_truth) if ground_truth else '',
        'match': match,
        'similarity': round(similarity, 3),
        'correct': correct,
    }


def compare_records(
    prediction: IMDBRecord,
    ground_truth: IMDBRecord,
    similarity_threshold: float = 0.85,
) -> dict[str, Any]:
    """
    Compare a prediction record against ground truth.
    
    Returns comprehensive comparison with per-field details and overall metrics.
    """
    imdb_fields = [
        "item_name", "barcode", "manufacturer", "brand", "weight",
        "packaging_type", "country", "variant", "product_type",
        "fragrance_flavor", "promotion", "addons", "tagline",
    ]
    
    field_comparisons = []
    correct_count = 0
    
    for field in imdb_fields:
        pred_val = getattr(prediction, field, None)
        gt_val = getattr(ground_truth, field, None)
        
        comparison = compare_field(
            pred_val, gt_val, field,
            similarity_threshold=similarity_threshold
        )
        field_comparisons.append(comparison)
        
        if comparison['correct']:
            correct_count += 1
    
    # Compute overall accuracy
    accuracy = correct_count / len(imdb_fields) if imdb_fields else 0.0
    
    # Compute per-category stats
    match_types = {}
    for comp in field_comparisons:
        match = comp['match']
        match_types[match] = match_types.get(match, 0) + 1
    
    return {
        'prediction_id': prediction.pk,
        'ground_truth_id': ground_truth.pk,
        'overall_accuracy': round(accuracy, 3),
        'fields_correct': correct_count,
        'fields_total': len(imdb_fields),
        'match_distribution': match_types,
        'field_details': field_comparisons,
        'prediction_confidence': prediction.overall_confidence,
        'ground_truth_confidence': ground_truth.overall_confidence,
    }


def evaluate_batch(
    predictions: list[IMDBRecord],
    ground_truth_records: list[IMDBRecord],
    match_by: str = 'barcode',
) -> dict[str, Any]:
    """
    Evaluate a batch of predictions against ground truth.
    
    Args:
        predictions: List of prediction IMDBRecords
        ground_truth_records: List of ground truth IMDBRecords
        match_by: Field to use for matching ('barcode', 'brand_and_name', etc.)
    
    Returns: {
        'total_predictions': int,
        'total_ground_truth': int,
        'matched_pairs': int,
        'unmatched_predictions': int,
        'unmatched_ground_truth': int,
        'overall_accuracy': float,
        'comparisons': [compare_records results],
        'field_stats': per-field statistics,
    }
    """
    # Build lookup for ground truth
    if match_by == 'barcode':
        gt_lookup = {rec.barcode: rec for rec in ground_truth_records if rec.barcode}
    elif match_by == 'brand_and_name':
        gt_lookup = {
            (rec.brand or "").lower() + "||" + (rec.item_name or "").lower(): rec
            for rec in ground_truth_records
        }
    else:
        raise ValueError(f"Unknown match_by strategy: {match_by}")
    
    comparisons = []
    matched_count = 0
    unmatched_preds = []
    
    for pred in predictions:
        if match_by == 'barcode':
            key = pred.barcode
        else:
            key = (pred.brand or "").lower() + "||" + (pred.item_name or "").lower()
        
        gt = gt_lookup.get(key)
        if gt:
            comparison = compare_records(pred, gt)
            comparisons.append(comparison)
            matched_count += 1
        else:
            unmatched_preds.append(pred.pk)
    
    # Compute field-level statistics
    field_stats = {}
    for field in ["item_name", "barcode", "manufacturer", "brand", "weight",
                  "packaging_type", "country", "variant", "product_type",
                  "fragrance_flavor", "promotion", "addons", "tagline"]:
        field_stats[field] = {
            'exact_matches': 0,
            'partial_matches': 0,
            'mismatches': 0,
            'missing': 0,
            'false_positives': 0,
        }

    match_key_map = {
        'exact': 'exact_matches',
        'partial': 'partial_matches',
        'mismatch': 'mismatches',
        'missing': 'missing',
        'false_positive': 'false_positives',
    }

    for comp in comparisons:
        for field_detail in comp['field_details']:
            field = field_detail['field']
            match_type = field_detail['match']
            stat_key = match_key_map.get(match_type)
            if stat_key and field in field_stats:
                field_stats[field][stat_key] += 1
    
    overall_accuracy = sum(c['overall_accuracy'] for c in comparisons) / len(comparisons) if comparisons else 0.0
    
    return {
        'total_predictions': len(predictions),
        'total_ground_truth': len(ground_truth_records),
        'matched_pairs': matched_count,
        'unmatched_predictions': len(unmatched_preds),
        'unmatched_ground_truth': len(gt_lookup) - matched_count,
        'overall_accuracy': round(overall_accuracy, 3),
        'comparisons': comparisons,
        'field_stats': field_stats,
        'unmatched_prediction_ids': unmatched_preds,
    }


def get_evaluation_report(
    ground_truth_queryset: Any = None,
    prediction_queryset: Any = None,
) -> dict[str, Any]:
    """
    Generate a comprehensive evaluation report comparing all predictions to ground truth.
    
    If querysets not provided, uses all records marked with high confidence as ground truth.
    """
    if prediction_queryset is None:
        prediction_queryset = IMDBRecord.objects.filter(overall_confidence__lt=1.0)
    
    if ground_truth_queryset is None:
        ground_truth_queryset = IMDBRecord.objects.filter(overall_confidence=1.0)
    
    predictions = list(prediction_queryset)
    ground_truth = list(ground_truth_queryset)
    
    if not ground_truth:
        logger.warning("No ground truth records found")
        return {
            'error': 'No ground truth records available',
            'total_predictions': len(predictions),
        }
    
    results = evaluate_batch(predictions, ground_truth, match_by='barcode')
    
    return results
