FROM python:3.11-slim

# System dependencies (Pillow, pyzbar, pytesseract)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libzbar0 \
    tesseract-ocr \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to avoid pip/permissions warnings
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Install dependencies as root before switching users (needs write to site-packages)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and hand ownership to appuser
COPY . .
RUN chown -R appuser:appuser /app

USER appuser

# Create directories and bake static files into the image at build time
RUN mkdir -p /app/media /app/staticfiles
RUN SECRET_KEY=build-time-placeholder DEBUG=False ALLOWED_HOSTS=* python manage.py collectstatic --noinput

EXPOSE 8000

# Only run migrations at startup (collectstatic already done at build time)
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn imdb_project.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120 --log-level info"]
