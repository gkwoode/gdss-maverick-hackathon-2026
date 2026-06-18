import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "imdb_project.settings")

# Run any pending migrations before the first request is served.
# This is the fallback for platforms (e.g. Render free tier) where
# preDeployCommand is not executed.
def _run_migrations():
    try:
        import django
        django.setup()
        from django.core.management import call_command
        call_command("migrate", "--noinput", verbosity=1)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Auto-migration failed: %s", exc)

_run_migrations()

application = get_wsgi_application()
