"""
Vercel serverless entry point for the Django backend.

Vercel's Python runtime looks for a WSGI `app` variable (or an ASGI `application`)
in this file and routes every incoming request through it.

The project root directory for this Vercel project must be set to `backend/`
so that Python can resolve `imdb_project.*` imports correctly.
"""
import os
import sys

# Ensure the backend root is on sys.path when Vercel runs from the repo root.
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "imdb_project.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()

# Vercel's @vercel/python builder picks up the variable named `app`.
app = application
