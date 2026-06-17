"""
Management command: evaluate_predictions
==========================================
Evaluate predictions against ground truth records.

Usage:
    python manage.py evaluate_predictions
    python manage.py evaluate_predictions --include-low-confidence
    python manage.py evaluate_predictions --output report.json
"""

import json
import logging
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.products.models import IMDBRecord
from apps.products.services.evaluation import get_evaluation_report

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Evaluate predictions against ground truth records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-low-confidence",
            action="store_true",
            help="Include records with low confidence (< 0.7)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Save report to JSON file",
        )

    def handle(self, *args, **options):
        # Get querysets
        ground_truth_qs = IMDBRecord.objects.filter(overall_confidence=1.0)
        
        if options["include_low_confidence"]:
            prediction_qs = IMDBRecord.objects.filter(overall_confidence__lt=1.0)
        else:
            prediction_qs = IMDBRecord.objects.filter(
                overall_confidence__gte=0.7,
                overall_confidence__lt=1.0,
            )

        gt_count = ground_truth_qs.count()
        pred_count = prediction_qs.count()

        self.stdout.write(f"Ground truth records: {gt_count}")
        self.stdout.write(f"Prediction records: {pred_count}")

        if gt_count == 0:
            self.stdout.write(
                self.style.WARNING("No ground truth records found. Import ground truth first.")
            )
            return

        if pred_count == 0:
            self.stdout.write(
                self.style.WARNING("No prediction records found to evaluate.")
            )
            return

        self.stdout.write("Evaluating...")

        try:
            result = get_evaluation_report(
                ground_truth_queryset=ground_truth_qs,
                prediction_queryset=prediction_qs,
            )

            # Display summary
            self.stdout.write(self.style.SUCCESS(f"\n=== Evaluation Results ==="))
            self.stdout.write(f"Overall Accuracy: {result['overall_accuracy']:.1%}")
            self.stdout.write(f"Matched Pairs: {result['matched_pairs']} / {result['total_predictions']}")
            self.stdout.write(f"Unmatched Predictions: {result['unmatched_predictions']}")
            self.stdout.write(f"Unmatched Ground Truth: {result['unmatched_ground_truth']}")

            # Field statistics
            self.stdout.write(f"\n=== Field Statistics ===")
            field_stats = result.get("field_stats", {})
            for field, stats in field_stats.items():
                if not stats:
                    continue
                total = sum(stats.values())
                if total == 0:
                    continue
                exact_pct = stats.get("exact_matches", 0) / total * 100 if total > 0 else 0
                partial_pct = stats.get("partial_matches", 0) / total * 100 if total > 0 else 0
                self.stdout.write(
                    f"{field:20} Exact: {exact_pct:5.1f}% | Partial: {partial_pct:5.1f}%"
                )

            # Save to file if requested
            if options["output"]:
                output_path = Path(options["output"])
                with open(output_path, "w") as f:
                    json.dump(result, f, indent=2, default=str)
                self.stdout.write(
                    self.style.SUCCESS(f"\nReport saved to {output_path}")
                )

        except Exception as exc:
            logger.exception("Evaluation failed")
            self.stdout.write(
                self.style.ERROR(f"Evaluation failed: {exc}")
            )
