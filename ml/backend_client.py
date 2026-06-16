"""
backend_client.py
=================
HTTP client for the Django REST backend.

All ML scripts should use this module instead of importing Django directly.
This keeps the ML pipeline decoupled from the Django ORM and allows the
backend to run as a separate process (or on a different machine).

Environment variables (read from backend/.env or shell):
  BACKEND_URL   – base URL of the Django server   (default: http://127.0.0.1:8000)
  BACKEND_TOKEN – optional Bearer token if auth is enabled

Endpoints used:
  POST /api/products/analyze_multi/   – images → extracted+validated IMDB data
  GET  /api/products/export/          – download predictions.csv or .xlsx
  POST /api/products/                 – create a saved IMDB record
  GET  /api/products/                 – list saved records (with filters)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Config ─────────────────────────────────────────────────────────────────────

_ENV_FILE = Path(__file__).resolve().parent.parent / "backend" / ".env"

def _load_env() -> None:
    """Load backend/.env into os.environ (skips keys already set)."""
    if not _ENV_FILE.exists():
        return
    with open(_ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

BACKEND_URL   = os.environ.get("BACKEND_URL",   "http://127.0.0.1:8000").rstrip("/")
BACKEND_TOKEN = os.environ.get("BACKEND_TOKEN", "")

# ── Session with retry logic ───────────────────────────────────────────────────

def _make_session(retries: int = 3, backoff: float = 0.5) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods={"POST", "GET"},
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    if BACKEND_TOKEN:
        session.headers.update({"Authorization": f"Bearer {BACKEND_TOKEN}"})
    return session


_SESSION: requests.Session | None = None

def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = _make_session()
    return _SESSION


# ── Public helpers ─────────────────────────────────────────────────────────────

class BackendError(Exception):
    """Raised when the backend returns a non-2xx response."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Backend {status_code}: {message}")


def health_check(timeout: float = 5.0) -> bool:
    """Return True if the backend is reachable."""
    try:
        r = _session().get(f"{BACKEND_URL}/api/products/", timeout=timeout, params={"page_size": 1})
        return r.status_code < 500
    except requests.exceptions.ConnectionError:
        return False


def analyze_images(
    image_paths: list[Path | str],
    timeout: float = 120.0,
) -> dict[str, Any]:
    """
    POST multiple product images to /api/products/analyze_multi/.

    Returns the JSON response dict:
    {
        "extracted":           { item_name, barcode, ... },
        "confidence":          { item_name: 0.9, ... },
        "method":              "gpt4o" | "ocr",
        "potential_duplicates": [...],
        "images_processed":    N,
        "images_failed":       M,
    }
    """
    url = f"{BACKEND_URL}/api/products/analyze_multi/"
    files = []
    open_handles = []

    try:
        for p in image_paths:
            fh = open(p, "rb")
            open_handles.append(fh)
            files.append(("images", (Path(p).name, fh, "image/jpeg")))

        r = _session().post(url, files=files, timeout=timeout)
    finally:
        for fh in open_handles:
            fh.close()

    if not r.ok:
        raise BackendError(r.status_code, r.text[:300])

    return r.json()


def analyze_single_image(
    image_path: Path | str,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """POST a single image to /api/products/analyze/."""
    url = f"{BACKEND_URL}/api/products/analyze/"
    with open(image_path, "rb") as fh:
        r = _session().post(
            url,
            files={"image": (Path(image_path).name, fh, "image/jpeg")},
            timeout=timeout,
        )
    if not r.ok:
        raise BackendError(r.status_code, r.text[:300])
    return r.json()


def create_record(extracted: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
    """POST to /api/products/ to persist an IMDB record in the database."""
    url = f"{BACKEND_URL}/api/products/"
    r = _session().post(url, json=extracted, timeout=timeout)
    if not r.ok:
        raise BackendError(r.status_code, r.text[:300])
    return r.json()


def list_records(
    page_size: int = 200,
    filters: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """GET /api/products/ — returns all records (auto-paginates)."""
    url = f"{BACKEND_URL}/api/products/"
    params = {"page_size": page_size, **(filters or {})}
    records = []
    while url:
        r = _session().get(url, params=params, timeout=timeout)
        if not r.ok:
            raise BackendError(r.status_code, r.text[:300])
        data = r.json()
        # Handle both paginated {"results": [...]} and plain list responses
        if isinstance(data, list):
            records.extend(data)
            break
        records.extend(data.get("results", []))
        url    = data.get("next")
        params = {}   # next URL already has params baked in
    return records


def download_export(
    fmt: str = "csv",
    output_path: Path | str | None = None,
    ids: list[int] | None = None,
    timeout: float = 60.0,
) -> bytes:
    """
    GET /api/products/export/?format=csv|excel
    Saves to `output_path` if given, always returns the raw bytes.
    """
    url = f"{BACKEND_URL}/api/products/export/"
    params: dict[str, Any] = {"format": fmt}
    if ids:
        params["ids"] = ",".join(str(i) for i in ids)

    r = _session().get(url, params=params, timeout=timeout)
    if not r.ok:
        raise BackendError(r.status_code, r.text[:300])

    content = r.content
    if output_path:
        Path(output_path).write_bytes(content)
    return content


def batch_analyze(
    entries: list[dict],
    *,
    max_images: int = 4,
    rate_limit_delay: float = 1.0,
    verbose: bool = True,
    on_result: Any = None,
) -> list[dict]:
    """
    Analyze a list of dataset entries through the backend.

    `entries` items must have an "images" key with relative image paths.

    Returns a list of dicts:
    {
        "product_id": ...,
        "num_images":  N,
        "response":    { extracted, confidence, method, ... },  # None on error
        "error":       None | "error message",
    }

    `on_result(i, total, entry, result_dict)` is called after each product
    if provided — useful for progress callbacks.
    """
    ROOT = Path(__file__).resolve().parent.parent
    results = []

    for i, entry in enumerate(entries, 1):
        pid    = entry.get("product_id", f"#{i}")
        images = [ROOT / p for p in entry.get("images", [])[:max_images] if (ROOT / p).exists()]

        if verbose:
            print(f"  [{i:3d}/{len(entries)}] {pid}  ({len(images)} imgs) … ", end="", flush=True)

        if not images:
            if verbose:
                print("SKIP (no images)")
            results.append({"product_id": pid, "num_images": 0, "response": None, "error": "no images"})
            continue

        try:
            response = analyze_images(images)
            result   = {"product_id": pid, "num_images": len(images), "response": response, "error": None}
            if verbose:
                conf = response.get("confidence", {})
                avg  = sum(conf.values()) / max(len(conf), 1) if isinstance(conf, dict) else 0
                print(f"conf={avg:.2f}  method={response.get('method', '?')}")
        except BackendError as exc:
            result = {"product_id": pid, "num_images": len(images), "response": None, "error": str(exc)}
            if verbose:
                print(f"ERROR {exc}")
        except Exception as exc:
            result = {"product_id": pid, "num_images": len(images), "response": None, "error": str(exc)}
            if verbose:
                print(f"ERROR {exc}")

        results.append(result)

        if on_result:
            on_result(i, len(entries), entry, result)

        if i < len(entries):
            time.sleep(rate_limit_delay)

    return results
