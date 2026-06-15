from django.contrib import admin
from .models import IMDBRecord


@admin.register(IMDBRecord)
class IMDBRecordAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "item_name",
        "barcode",
        "brand",
        "weight",
        "packaging_type",
        "country",
        "product_type",
        "overall_confidence",
        "needs_review",
        "created_at",
    ]
    list_filter = ["needs_review", "is_duplicate_candidate", "product_type", "packaging_type"]
    search_fields = ["barcode", "brand", "item_name", "manufacturer"]
    readonly_fields = ["overall_confidence", "needs_review", "created_at", "updated_at"]
    fieldsets = (
        (
            "13 IMDB Attributes",
            {
                "fields": (
                    "item_name",
                    "barcode",
                    "manufacturer",
                    "brand",
                    "weight",
                    "packaging_type",
                    "country",
                    "variant",
                    "product_type",
                    "fragrance_flavor",
                    "promotion",
                    "addons",
                    "tagline",
                )
            },
        ),
        (
            "Source Images",
            {"fields": ("image_paths",)},
        ),
        (
            "Quality & Metadata",
            {
                "fields": (
                    "confidence_scores",
                    "overall_confidence",
                    "needs_review",
                    "is_duplicate_candidate",
                    "duplicate_of",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
