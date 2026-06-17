import json
import logging
import uuid
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
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
from .services.batch_processor import batch_process_directory
from .services.duplicate_checker import find_duplicates
from .services.evaluation import get_evaluation_report
from .services.exporter import export_csv, export_excel
from .services.image_analyzer import analyze_image
from .services.validator import validate_and_normalise

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
def export_records(request):
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
    # Internal helper: persist an uploaded image and return its URL path
    # ------------------------------------------------------------------
    def _save_image(self, img_file) -> str:
        """Save an uploaded image file to MEDIA_ROOT and return its relative path."""
        ext = img_file.name.rsplit(".", 1)[-1].lower() if "." in img_file.name else "jpg"
        filename = f"product_images/{uuid.uuid4().hex}.{ext}"
        img_file.seek(0)
        saved_path = default_storage.save(filename, ContentFile(img_file.read()))
        return saved_path

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

        img_file = serializer.validated_data["image"]
        image_bytes = img_file.read()
        img_file.seek(0)
        saved_path = self._save_image(img_file)

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
        cleaned["image_paths"] = [saved_path]

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
        saved_paths = []
        errors = []
        for img_file in images:
            img_bytes = img_file.read()
            # Persist the image file
            try:
                saved_paths.append(self._save_image(img_file))
            except Exception as exc:
                logger.warning("Failed to save image '%s': %s", img_file.name, exc)

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
        aggregated["image_paths"] = saved_paths

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
    # Batch process directory endpoint
    # ------------------------------------------------------------------
    @action(detail=False, methods=["post"], url_path="batch_process")
    def batch_process(self, request):
        """
        Batch process all product images from a directory.
        
        POST data:
          - images_dir: path to directory (or uses default MEDIA_ROOT/product_images)
          - max_products: optional limit on number of products
          - update_existing: whether to update existing records (default: true)
        """
        images_dir = request.data.get("images_dir", "")
        max_products = request.data.get("max_products")
        update_existing = request.data.get("update_existing", True)
        
        try:
            max_products = int(max_products) if max_products else None
        except (ValueError, TypeError):
            max_products = None
        
        if not images_dir:
            # Use default media directory
            from django.conf import settings
            images_dir = Path(settings.MEDIA_ROOT) / "product_images"
        else:
            images_dir = Path(images_dir)
        
        try:
            result = batch_process_directory(
                images_dir,
                update_existing=update_existing,
                max_products=max_products,
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("Batch processing failed")
            return Response(
                {"error": f"Batch processing failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ------------------------------------------------------------------
    # Evaluation endpoint
    # ------------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="evaluate")
    def evaluate(self, request):
        """
        Evaluate predictions against ground truth records.
        
        Query params:
          - include_low_confidence: include records below 0.7 confidence (default: false)
        """
        include_low_confidence = request.query_params.get("include_low_confidence", "false").lower() == "true"
        
        try:
            # Ground truth: records with confidence = 1.0
            ground_truth_qs = IMDBRecord.objects.filter(overall_confidence=1.0)
            
            # Predictions: records with confidence < 1.0
            if include_low_confidence:
                prediction_qs = IMDBRecord.objects.filter(overall_confidence__lt=1.0)
            else:
                prediction_qs = IMDBRecord.objects.filter(
                    overall_confidence__gte=0.7,
                    overall_confidence__lt=1.0,
                )
            
            result = get_evaluation_report(
                ground_truth_queryset=ground_truth_qs,
                prediction_queryset=prediction_qs,
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("Evaluation failed")
            return Response(
                {"error": f"Evaluation failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

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

