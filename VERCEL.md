# Vercel Deployment Guide — Frontend

This guide explains how to connect this repository to the Vercel project at
[godwin-woodes-projects/gdss-maverick-hackathon-2026](https://vercel.com/godwin-woodes-projects/gdss-maverick-hackathon-2026)
so that the **Next.js frontend** (`frontend/`) is built and deployed correctly.

---

## 1. Vercel Project Settings

Open the project in the Vercel dashboard → **Settings** and apply the following:

### General → Root Directory

| Setting | Value |
|---|---|
| **Root Directory** | `frontend` |

> Setting the root directory tells Vercel to treat `frontend/` as the project
> root, so `package.json`, `next.config.mjs`, and `vercel.json` are all
> resolved from there.

### Build & Development Settings

Leave all fields on **default** (Vercel auto-detects Next.js):

| Setting | Value |
|---|---|
| Framework Preset | `Next.js` (auto-detected) |
| Build Command | `npm run build` |
| Output Directory | `.next` |
| Install Command | `npm install` |

### Environment Variables

Add the following environment variable under **Settings → Environment Variables**:

| Name | Value (example) | Environment |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://<your-backend-domain>/api` | Production, Preview |

Replace `<your-backend-domain>` with the actual URL of the deployed Django
backend (e.g. a Railway/Render/Fly.io URL such as
`https://gdss-backend.up.railway.app`).

> **Why is this required?**
> - The Next.js API rewrite (`/api/:path*`) proxies requests to this URL.
> - `mediaUrl()` in `frontend/src/lib/api.ts` derives media asset URLs from
>   this variable.
> - Next.js Image Optimization is configured at build time to allow images
>   served from this host (see `frontend/next.config.mjs`).

---

## 2. Connecting the Repository

1. In the Vercel dashboard, go to **Settings → Git** (or use the initial
   import flow).
2. Connect the **gkwoode/gdss-maverick-hackathon-2026** GitHub repository.
3. Set the **Production Branch** to `main`.
4. Apply the Root Directory and environment variable settings from Section 1.

---

## 3. Deploy

Trigger a deployment by either:

- Pushing a commit to `main` (automatic deployment).
- Clicking **Redeploy** in the Vercel dashboard.

The build will run `npm run build` inside the `frontend/` directory and publish
the resulting Next.js app.

---

## 4. Notes

- **Image Optimization**: `frontend/next.config.mjs` automatically adds the
  backend hostname derived from `NEXT_PUBLIC_API_URL` to the allowed
  `remotePatterns` list at build time. You do **not** need to edit
  `next.config.mjs` manually.
- **API Proxy / CORS**: The rewrite rule proxies `/api/*` calls to the backend,
  so the browser never makes a cross-origin request. Ensure the backend's
  `CORS_ALLOWED_ORIGINS` setting includes the Vercel deployment URL if you ever
  bypass the proxy (e.g. server-side fetches with a full backend URL).
- **No `vercel.json` at the repository root is required.** The `frontend/vercel.json`
  is picked up automatically once the Root Directory is set to `frontend`.
