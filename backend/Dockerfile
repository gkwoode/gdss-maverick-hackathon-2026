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

EXPOSE 8000

CMD ["gunicorn", "imdb_project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
