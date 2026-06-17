"""
batch_processor.py
------------------
Batch processing service for handling multiple product images organized by product ID.

Workflow:
  1. Scan a directory for product images (organized by product ID).
  2. Group images by product.
  3. For each product group, analyze all images and aggregate results.
  4. Create or update IMDBRecord for each product.
  5. Return processing summary (created, updated, failed).
"""

import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from apps.products.models import IMDBRecord
from .aggregator import aggregate_extractions
from .duplicate_checker import find_duplicates
from .image_analyzer import analyze_image
from .validator import validate_and_normalise

logger = logging.getLogger(__name__)


def group_images_by_product(images_dir: Path) -> dict[str, list[Path]]:
    """
    Scan images_dir and group images by product ID (first token before '_').
    
    Expected filename format: <PRODUCT_ID>_<angle|side>.<ext>
    Example: 001_front.jpg, 001_back.jpg, 001_left.jpg
    
    Returns: {product_id: [Path(image1), Path(image2), ...], ...}
    """
    groups: dict[str, list[Path]] = defaultdict(list)
    
    if not images_dir.exists():
        logger.warning(f"Images directory not found: {images_dir}")
        return groups
    
    for filename in sorted(os.listdir(images_dir)):
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            continue
        
        filepath = images_dir / filename
        if not filepath.is_file():
            continue
        
        # Extract product ID (first token before '_')
        product_id = filename.split('_')[0] if '_' in filename else filename.split('.')[0]
        groups[product_id].append(filepath)
    
    return dict(groups)


def process_product_group(
    product_id: str,
    image_paths: list[Path],
    update_existing: bool = True,
) -> dict[str, Any]:
    """
    Process all images for a single product and create/update the IMDBRecord.
    
    Args:
        product_id: Unique product identifier
        image_paths: List of Path objects pointing to product images
        update_existing: If True, update existing record; if False, skip
    
    Returns: {
        'product_id': str,
        'status': 'created' | 'updated' | 'failed' | 'skipped',
        'record_id': int or None,
        'images_processed': int,
        'images_failed': int,
        'extracted_data': dict or None,
        'confidence': dict or None,
        'error': str or None,
    }
    """
    result = {
        'product_id': product_id,
        'status': 'failed',
        'record_id': None,
        'images_processed': 0,
        'images_failed': 0,
        'extracted_data': None,
        'confidence': None,
        'error': None,
    }
    
    # Try to read and analyze each image
    per_image_results = []
    for image_path in image_paths:
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            raw = analyze_image(image_bytes)
            cleaned = validate_and_normalise(raw)
            per_image_results.append(cleaned)
            result['images_processed'] += 1
        except Exception as exc:
            logger.warning(f"Failed to analyze {image_path}: {exc}")
            result['images_failed'] += 1
    
    if not per_image_results:
        result['error'] = f"All {len(image_paths)} images failed to analyze"
        return result
    
    # Aggregate results from all images
    try:
        aggregated = aggregate_extractions(per_image_results)
        confidence = aggregated.pop("confidence", {})
        method = aggregated.pop("method", "unknown")
        duplicates = find_duplicates(aggregated)
        
        # Store relative image paths
        aggregated['image_paths'] = [str(p.relative_to(p.parent.parent)) for p in image_paths]
        
        # Check for duplicates
        if duplicates:
            logger.info(f"Product {product_id}: Found {len(duplicates)} potential duplicates")
            aggregated['is_duplicate_candidate'] = True
            aggregated['duplicate_of'] = duplicates[0]['id']
        
        aggregated['confidence_scores'] = confidence
        aggregated['overall_confidence'] = IMDBRecord.objects.model().compute_overall_confidence.__func__(
            type('obj', (object,), {'confidence_scores': confidence})()
        ) if hasattr(IMDBRecord, 'compute_overall_confidence') else sum(confidence.values()) / len(confidence) if confidence else 0.0
        
        result['extracted_data'] = aggregated
        result['confidence'] = confidence
        
        # Create or update the record
        existing = IMDBRecord.objects.filter(barcode=aggregated.get('barcode')).first() if aggregated.get('barcode') else None
        
        if existing:
            if not update_existing:
                result['status'] = 'skipped'
                result['record_id'] = existing.pk
                return result
            # Update existing
            for key, value in aggregated.items():
                if hasattr(existing, key) and key != 'id':
                    setattr(existing, key, value)
            existing.save()
            result['status'] = 'updated'
            result['record_id'] = existing.pk
        else:
            # Create new
            record = IMDBRecord.objects.create(**aggregated)
            result['status'] = 'created'
            result['record_id'] = record.pk
    
    except Exception as exc:
        logger.exception(f"Error aggregating results for product {product_id}")
        result['error'] = str(exc)
        result['status'] = 'failed'
    
    return result


def batch_process_directory(
    images_dir: Path,
    update_existing: bool = True,
    max_products: int | None = None,
) -> dict[str, Any]:
    """
    Scan and process all products in a directory.
    
    Args:
        images_dir: Path to directory containing product images
        update_existing: If True, update existing records; if False, skip
        max_products: Limit number of products to process (None = all)
    
    Returns: {
        'total_products': int,
        'created': int,
        'updated': int,
        'skipped': int,
        'failed': int,
        'results': [process_product_group() results],
        'summary': str,
    }
    """
    groups = group_images_by_product(images_dir)
    
    if not groups:
        logger.warning(f"No images found in {images_dir}")
        return {
            'total_products': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'failed': 0,
            'results': [],
            'summary': 'No images found',
        }
    
    results = []
    counts = {'created': 0, 'updated': 0, 'skipped': 0, 'failed': 0}
    
    product_ids = sorted(groups.keys())
    if max_products:
        product_ids = product_ids[:max_products]
    
    logger.info(f"Processing {len(product_ids)} products from {images_dir}")
    
    for idx, product_id in enumerate(product_ids, 1):
        image_paths = groups[product_id]
        logger.info(f"[{idx}/{len(product_ids)}] Processing product {product_id} ({len(image_paths)} images)")
        
        result = process_product_group(product_id, image_paths, update_existing=update_existing)
        results.append(result)
        counts[result['status']] += 1
    
    summary = (
        f"Processed {len(product_ids)} products: "
        f"{counts['created']} created, {counts['updated']} updated, "
        f"{counts['skipped']} skipped, {counts['failed']} failed"
    )
    logger.info(summary)
    
    return {
        'total_products': len(product_ids),
        'created': counts['created'],
        'updated': counts['updated'],
        'skipped': counts['skipped'],
        'failed': counts['failed'],
        'results': results,
        'summary': summary,
    }
