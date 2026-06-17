"""
Management command: batch_process
==================================
Batch process all product images from a directory.

Usage:
    python manage.py batch_process
    python manage.py batch_process --images-dir /path/to/images
    python manage.py batch_process --max-products 10
    python manage.py batch_process --skip-existing
"""

import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.products.services.batch_processor import batch_process_directory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Batch process product images from a directory"

    def add_arguments(self, parser):
        parser.add_argument(
            "--images-dir",
            type=str,
            default=None,
            help="Path to images directory (defaults to MEDIA_ROOT/product_images)",
        )
        parser.add_argument(
            "--max-products",
            type=int,
            default=None,
            help="Maximum number of products to process (None = all)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip updating existing records",
        )

    def handle(self, *args, **options):
        # Resolve images directory
        if options["images_dir"]:
            images_dir = Path(options["images_dir"]).resolve()
        else:
            images_dir = Path(settings.MEDIA_ROOT) / "product_images"

        if not images_dir.exists():
            self.stdout.write(
                self.style.ERROR(f"Images directory not found: {images_dir}")
            )
            return

        self.stdout.write(f"Processing images from: {images_dir}")
        update_existing = not options["skip_existing"]

        try:
            result = batch_process_directory(
                images_dir,
                update_existing=update_existing,
                max_products=options["max_products"],
            )

            # Display results
            self.stdout.write(self.style.SUCCESS(f"\n{result['summary']}"))
            self.stdout.write(f"  Created: {result['created']}")
            self.stdout.write(f"  Updated: {result['updated']}")
            self.stdout.write(f"  Skipped: {result['skipped']}")
            self.stdout.write(f"  Failed: {result['failed']}")

            if result["failed"] > 0:
                self.stdout.write(self.style.WARNING("\nFailed products:"))
                for res in result["results"]:
                    if res["status"] == "failed":
                        self.stdout.write(
                            f"  {res['product_id']}: {res['error']}"
                        )

        except Exception as exc:
            logger.exception("Batch processing failed")
            self.stdout.write(
                self.style.ERROR(f"Batch processing failed: {exc}")
            )
