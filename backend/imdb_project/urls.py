from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


def health(request):
    return JsonResponse({"status": "ok", "service": "GDSS Maverick IMDB API"})


urlpatterns = [
    path("", health),
    path("admin/", admin.site.urls),
    path("api/", include("apps.products.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
