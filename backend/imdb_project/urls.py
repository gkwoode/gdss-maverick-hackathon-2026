from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


def health(request):
    return JsonResponse({"status": "ok", "service": "GDSS Maverick IMDB API"})


def db_health(request):
    """Diagnostic endpoint — exposes actual DB error so we can fix it."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        from apps.products.models import IMDBRecord
        count = IMDBRecord.objects.count()
        return JsonResponse({"db": "ok", "records": count, "debug": settings.DEBUG})
    except Exception as exc:
        import traceback
        return JsonResponse(
            {"db": "error", "error": str(exc), "traceback": traceback.format_exc()},
            status=500,
        )


urlpatterns = [
    path("", health),
    path("db-health/", db_health),
    path("admin/", admin.site.urls),
    path("api/", include("apps.products.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
