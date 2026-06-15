"""
exporter.py
-----------
Generates CSV and Excel files from a queryset of IMDBRecord instances.
"""

import io
from typing import Iterable

import pandas as pd

from apps.products.models import IMDBRecord

# Ground-truth column order as specified in the hackathon brief
IMDB_COLUMN_ORDER = [
    "ITEM_NAME",
    "BARCODE",
    "MANUFACTURER",
    "BRAND",
    "WEIGHT",
    "PACKAGING TYPE",
    "COUNTRY",
    "VARIANT",
    "TYPE",
    "FRAGRANCE_FLAVOR",
    "PROMOTION",
    "ADDONS",
    "TAGLINE",
]


def _records_to_dataframe(records: Iterable[IMDBRecord]) -> pd.DataFrame:
    rows = []
    for rec in records:
        rows.append(
            {
                "ITEM_NAME": rec.item_name or "",
                "BARCODE": rec.barcode or "",
                "MANUFACTURER": rec.manufacturer or "",
                "BRAND": rec.brand or "",
                "WEIGHT": rec.weight or "",
                "PACKAGING TYPE": rec.packaging_type or "",
                "COUNTRY": rec.country or "",
                "VARIANT": rec.variant or "",
                "TYPE": rec.product_type or "",
                "FRAGRANCE_FLAVOR": rec.fragrance_flavor or "",
                "PROMOTION": rec.promotion or "",
                "ADDONS": rec.addons or "",
                "TAGLINE": rec.tagline or "",
            }
        )
    df = pd.DataFrame(rows, columns=IMDB_COLUMN_ORDER)
    return df


def export_csv(records: Iterable[IMDBRecord]) -> bytes:
    df = _records_to_dataframe(records)
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    return buf.getvalue().encode("utf-8-sig")


def export_excel(records: Iterable[IMDBRecord]) -> bytes:
    df = _records_to_dataframe(records)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="IMDB Records")

        # Auto-size columns
        worksheet = writer.sheets["IMDB Records"]
        for col in worksheet.columns:
            max_len = max(
                len(str(cell.value)) if cell.value is not None else 0 for cell in col
            )
            worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    return buf.getvalue()
