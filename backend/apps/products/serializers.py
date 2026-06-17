from rest_framework import serializers
from .models import IMDBRecord


class IMDBRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = IMDBRecord
        fields = [
            "id",
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
            "image_paths",
            "confidence_scores",
            "overall_confidence",
            "needs_review",
            "is_duplicate_candidate",
            "duplicate_of",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "overall_confidence",
            "needs_review",
            "is_duplicate_candidate",
            "created_at",
            "updated_at",
        ]


class AnalyzeImageSerializer(serializers.Serializer):
    image = serializers.ImageField(required=True)


class AnalyzeMultiImageSerializer(serializers.Serializer):
    images = serializers.ListField(
        child=serializers.ImageField(),
        min_length=1,
        max_length=10,
    )


class ExportQuerySerializer(serializers.Serializer):
    FORMAT_CHOICES = [("csv", "CSV"), ("excel", "Excel")]
    file_format = serializers.ChoiceField(choices=FORMAT_CHOICES, default="csv")
    ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )

