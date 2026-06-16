import logging

from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import IMDBRecord
from .serializers import (
    AnalyzeImageSerializer,
    AnalyzeMultiImageSerializer,
    ExportQuerySerializer,
    IMDBRecordSerializer,
)
from .services.aggregator import aggregate_extractions
from .services.duplicate_checker import find_duplicates
from .services.exporter import export_csv, export_excel
from .services.image_analyzer import analyze_image
from .services.validator import validate_and_normalise

logger = logging.getLogger(__name__)


class IMDBRecordViewSet(ModelViewSet):
    """
    CRUD + extra actions for IMDB records.

    Extra actions:
      POST /api/products/analyze/           — single image → extracted data preview
      POST /api/products/analyze_multi/     — multiple images → aggregated data preview
      POST /api/products/check_duplicates/  — check a candidate dict for duplicates
      GET  /api/products/export/            — download CSV or Excel (ground-truth format)
    """

    queryset = IMDBRecord.objects.all()
    serializer_class = IMDBRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        if brand := params.get("brand"):
            qs = qs.filter(brand__icontains=brand)
        if product_type := params.get("type"):
            qs = qs.filter(product_type__icontains=product_type)
        if barcode := params.get("barcode"):
            qs = qs.filter(barcode__icontains=barcode)
        if needs_review := params.get("needs_review"):
            qs = qs.filter(needs_review=(needs_review.lower() == "true"))
        if search := params.get("search"):
            qs = (
                qs.filter(item_name__icontains=search)
                | qs.filter(brand__icontains=search)
                | qs.filter(barcode__icontains=search)
            )

        return qs.distinct()

    # ------------------------------------------------------------------
    # Single-image analyze
    # ------------------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        url_path="analyze",
        parser_classes=[MultiPartParser, FormParser],
    )
    def analyze(self, request):
        """Upload one product image; returns extracted + validated IMDB data."""
        serializer = AnalyzeImageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        image_bytes = serializer.validated_data["image"].read()

        try:
            raw = analyze_image(image_bytes)
        except Exception as exc:
            logger.exception("Single-image analysis failed")
            return Response(
                {"error": f"Image analysis failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cleaned = validate_and_normalise(raw)
        confidence = cleaned.pop("confidence", {})
        method = cleaned.pop("method", "unknown")
        duplicates = find_duplicates(cleaned)

        return Response(
            {
                "extracted": cleaned,
                "confidence": confidence,
                "method": method,
                "potential_duplicates": duplicates,
                "images_processed": 1,
            },
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # Multi-image analyze (aggregate across 3-4 images of same product)
    # ------------------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        url_path="analyze_multi",
        parser_classes=[MultiPartParser, FormParser],
    )
    def analyze_multi(self, request):
        """
        Upload multiple images of the same product.
        Each image is analysed independently then results are aggregated.
        """
        images = request.FILES.getlist("images")
        if not images:
            return Response(
                {"error": "No images provided. Send files under the 'images' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        per_image_results = []
        errors = []
        for img_file in images:
            img_bytes = img_file.read()
            try:
                raw = analyze_image(img_bytes)
                cleaned = validate_and_normalise(raw)
                per_image_results.append(cleaned)
            except Exception as exc:
                logger.warning("Failed to analyze image '%s': %s", img_file.name, exc)
                errors.append(str(exc))

        if not per_image_results:
            return Response(
                {"error": "All image analyses failed.", "details": errors},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        aggregated = aggregate_extractions(per_image_results)
        confidence = aggregated.pop("confidence", {})
        method = aggregated.pop("method", "unknown")
        duplicates = find_duplicates(aggregated)

        return Response(
            {
                "extracted": aggregated,
                "confidence": confidence,
                "method": method,
                "potential_duplicates": duplicates,
                "images_processed": len(per_image_results),
                "images_failed": len(errors),
            },
            status=status.HTTP_200_OK,
        )

    # ------------------------------------------------------------------
    # Duplicate-check endpoint
    # ------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="check_duplicates")
    def check_duplicates(self, request):
        candidate = dict(request.data)
        exclude_id = candidate.pop("id", None)
        duplicates = find_duplicates(candidate, exclude_id=exclude_id)
        return Response({"potential_duplicates": duplicates})

    # ------------------------------------------------------------------
    # Export — produces predictions.csv / predictions.xlsx
    # ------------------------------------------------------------------
    @action(detail=False, methods=["get", "post"], url_path="export")
    def export(self, request):
        serializer = ExportQuerySerializer(
            data=request.query_params if request.method == "GET" else request.data
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        fmt = serializer.validated_data.get("format", "csv")
        ids = serializer.validated_data.get("ids", [])

        qs = IMDBRecord.objects.all()
        if ids:
            qs = qs.filter(pk__in=ids)

        if fmt == "excel":
            content = export_excel(qs)
            content_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            filename = "predictions.xlsx"
        else:
            content = export_csv(qs)
            content_type = "text/csv; charset=utf-8"
            filename = "predictions.csv"

        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

