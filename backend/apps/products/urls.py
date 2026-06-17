from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import IMDBRecordViewSet, export_records

router = DefaultRouter()
router.register(r"products", IMDBRecordViewSet, basename="products")

urlpatterns = [
    path("products/export/", export_records, name="products-export-explicit"),
    path("", include(router.urls)),
]
