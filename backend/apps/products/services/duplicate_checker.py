"""
duplicate_checker.py
--------------------
Compare a candidate record against existing IMDB records to surface
potential duplicates before saving.
"""

from django.db.models import Q

from apps.products.models import IMDBRecord


def find_duplicates(candidate: dict, exclude_id: int | None = None) -> list[dict]:
    """
    Return a list of existing records that may be duplicates of *candidate*.

    Matching strategy (any one of the following triggers a hit):
      1. Identical barcode.
      2. Same brand + item_name + weight.
    """
    qs = IMDBRecord.objects.all()
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)

    filters = Q()

    barcode = (candidate.get("barcode") or "").strip()
    if barcode:
        filters |= Q(barcode=barcode)

    brand = (candidate.get("brand") or "").strip().lower()
    item_name = (candidate.get("item_name") or "").strip().lower()
    weight = (candidate.get("weight") or "").strip().lower()

    if brand and item_name and weight:
        filters |= Q(brand__iexact=brand, item_name__iexact=item_name, weight__iexact=weight)
    elif brand and item_name:
        filters |= Q(brand__iexact=brand, item_name__iexact=item_name)

    if not filters:
        return []

    matches = qs.filter(filters)[:10]
    return [
        {
            "id": m.pk,
            "barcode": m.barcode,
            "brand": m.brand,
            "item_name": m.item_name,
            "weight": m.weight,
            "overall_confidence": m.overall_confidence,
        }
        for m in matches
    ]
