# Vercel Deployment Guide

This monorepo deploys as **two separate Vercel projects** — one for the Next.js
frontend and one for the Django backend.

---

## Quick overview

| Project | Root Directory | Framework preset |
|---------|---------------|-----------------|
| Frontend | `frontend/` | Next.js (auto-detected) |
| Backend | `backend/` | Other (Python / `@vercel/python`) |

---

## 1. Backend (Django)

### 1a. Create a new Vercel project

1. Go to <https://vercel.com/new> and import this repository.
2. Under **Root Directory** select **`backend`**.
3. Leave the framework preset as **Other**.
4. Click **Deploy** — the first build will likely fail until you add the required
   environment variables (step 1b).

### 1b. Set environment variables

In your Vercel backend project → **Settings → Environment Variables**, add:

| Variable | Required | Example / notes |
|----------|----------|-----------------|
| `SECRET_KEY` | ✅ | Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | ✅ | `False` |
| `ALLOWED_HOSTS` | ✅ | Comma-separated list of your backend Vercel hostname(s), e.g. `gdss-backend.vercel.app` — Vercel's auto-set `VERCEL_URL` is added automatically, so this is mainly for custom domains |
| `CORS_ALLOWED_ORIGINS` | ✅ | Your frontend URL, e.g. `https://gdss-maverick-hackathon-2026.vercel.app` |
| `CSRF_TRUSTED_ORIGINS` | ✅ | Same as `CORS_ALLOWED_ORIGINS`, e.g. `https://gdss-maverick-hackathon-2026.vercel.app` |
| `DB_ENGINE` | ✅ | `django.db.backends.postgresql` |
| `DB_NAME` | ✅ | Your Postgres database name |
| `DB_USER` | ✅ | Postgres username |
| `DB_PASSWORD` | ✅ | Postgres password |
| `DB_HOST` | ✅ | Postgres host (e.g. from Neon, Supabase, Railway, etc.) |
| `DB_PORT` | ✅ | `5432` |
| `OPENAI_API_KEY` | ✅ (for image analysis) | `sk-...` |
| `USE_S3` | optional | `True` to store uploaded images in S3 instead of the ephemeral filesystem |
| `AWS_ACCESS_KEY_ID` | if `USE_S3=True` | |
| `AWS_SECRET_ACCESS_KEY` | if `USE_S3=True` | |
| `AWS_STORAGE_BUCKET_NAME` | if `USE_S3=True` | |
| `AWS_S3_REGION_NAME` | if `USE_S3=True` | e.g. `us-east-1` |
| `AWS_S3_CUSTOM_DOMAIN` | optional | CloudFront domain for faster delivery |

> **Note — `VERCEL_URL`**: Vercel automatically injects `VERCEL_URL` (the
> deployment hostname without scheme) into the runtime environment. The Django
> settings already read this variable and append it to `ALLOWED_HOSTS` and
> `CSRF_TRUSTED_ORIGINS` automatically, so you do **not** need to set it manually.

### 1c. Run migrations

Vercel doesn't run Django management commands automatically. After the first
successful deployment, run migrations via a one-off console or your database
provider's query tool:

```bash
# Example using the Vercel CLI (requires vercel login)
vercel env pull .env.vercel  # pull env vars locally
cd backend && source .env.vercel && python manage.py migrate
```

Or connect to your hosted database directly and run migrations from your local
machine with the production environment variables set.

### 1d. Limitations on Vercel

| Feature | Status |
|---------|--------|
| REST API endpoints | ✅ Fully supported |
| Django Admin | ✅ Works (static files served via WhiteNoise) |
| Image uploads (`/api/products/analyze/`) | ⚠️ **Ephemeral filesystem** — uploaded files are lost between invocations. Use S3 (`USE_S3=True`) for persistent media storage. |
| `pyzbar` (barcode scanning) | ⚠️ Requires `libzbar0` system library. If missing on the Vercel runtime the barcode path is skipped gracefully and the GPT-4o path is used instead. |
| `pytesseract` (OCR fallback) | ⚠️ Requires `tesseract-ocr`. Same as above — fails gracefully if missing. |
| Long-running requests | ⚠️ Vercel functions time out at 10 s (Hobby) / 60 s (Pro). Image analysis with GPT-4o may be slow. |

---

## 2. Frontend (Next.js)

### 2a. Create a new Vercel project

1. Go to <https://vercel.com/new> and import this repository again.
2. Under **Root Directory** select **`frontend`**.
3. The **Next.js** framework preset will be detected automatically.
4. Click **Deploy**.

### 2b. Set environment variables

| Variable | Required | Example |
|----------|----------|---------|
| `NEXT_PUBLIC_API_URL` | ✅ | `https://<your-backend-project>.vercel.app/api` |

The frontend proxies all `/api/*` calls to this URL via Next.js rewrites, so
CORS is handled transparently and the browser never makes cross-origin API calls.

> Replace `<your-backend-project>` with the actual backend Vercel subdomain from
> step 1. If you use a custom domain, use that instead.

---

## 3. Database (PostgreSQL)

Vercel does not provide a hosted database. You can use any external Postgres
service, for example:

- [Neon](https://neon.tech) — generous free tier, serverless Postgres
- [Supabase](https://supabase.com) — free tier, includes Postgres + storage
- [Railway](https://railway.app) — simple setup

Set the connection details in the backend Vercel project's environment variables
as described in step 1b.

---

## 4. Media / File Uploads (S3)

Vercel's serverless functions run on ephemeral infrastructure — any file written
to disk during a request is lost afterwards. To persist uploaded product images
you must configure S3-compatible storage:

1. Create an S3 bucket (or use Supabase Storage / Cloudflare R2).
2. Set the `USE_S3=True` environment variable in the backend Vercel project.
3. Fill in the remaining `AWS_*` variables (see table in step 1b).

Without S3, the analyze endpoints still work (images are processed in memory),
but the saved image URLs will point to paths that no longer exist after the
function returns.

---

## 5. Re-deploying / Promoting

Every push to the `main` branch triggers automatic re-deployments for both
Vercel projects. You can also trigger a manual redeploy from the Vercel
dashboard.

After schema-changing migrations, re-run `python manage.py migrate` against the
production database as described in step 1c.
