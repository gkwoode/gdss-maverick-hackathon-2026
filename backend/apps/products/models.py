from django.db import models


class IMDBRecord(models.Model):
    """
    Central product-master record with the exact 13 IMDB columns required
    by the hackathon ground-truth schema.
    """

    # -----------------------------------------------------------------------
    # 13 IMDB columns (column names match ground-truth export headers)
    # -----------------------------------------------------------------------
    item_name = models.CharField(max_length=500, blank=True, null=True)
    barcode = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    manufacturer = models.CharField(max_length=200, blank=True, null=True)
    brand = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    weight = models.CharField(max_length=100, blank=True, null=True)
    packaging_type = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    variant = models.CharField(max_length=200, blank=True, null=True)
    product_type = models.CharField(max_length=100, blank=True, null=True)   # exported as "TYPE"
    fragrance_flavor = models.CharField(max_length=200, blank=True, null=True)
    promotion = models.CharField(max_length=500, blank=True, null=True)
    addons = models.CharField(max_length=500, blank=True, null=True)
    tagline = models.CharField(max_length=500, blank=True, null=True)

    # -----------------------------------------------------------------------
    # Source images (multiple images per product stored as list of paths/URLs)
    # -----------------------------------------------------------------------
    image_paths = models.JSONField(default=list, blank=True)

    # -----------------------------------------------------------------------
    # Confidence & review
    # -----------------------------------------------------------------------
    confidence_scores = models.JSONField(default=dict, blank=True)
    overall_confidence = models.FloatField(default=0.0)
    needs_review = models.BooleanField(default=False)
    is_duplicate_candidate = models.BooleanField(default=False)
    duplicate_of = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="potential_duplicates",
    )

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "IMDB Record"
        verbose_name_plural = "IMDB Records"

    def __str__(self):
        return f"{self.brand or 'Unknown'} — {self.item_name or 'Unnamed'}"

    def compute_overall_confidence(self) -> float:
        if not self.confidence_scores:
            return 0.0
        scores = [v for v in self.confidence_scores.values() if isinstance(v, (int, float))]
        return round(sum(scores) / len(scores), 3) if scores else 0.0

    def save(self, *args, **kwargs):
        self.overall_confidence = self.compute_overall_confidence()
        self.needs_review = self.overall_confidence < 0.7
        super().save(*args, **kwargs)
