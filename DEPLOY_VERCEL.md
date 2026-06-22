# Deploying IndusMind to Vercel (full stack)

The whole app runs on Vercel: the Vite frontend as static files, and the FastAPI
backend as a Python serverless function (`api/index.py`). Vectors live in Supabase
Postgres via **pgvector**, so no separate vector database is needed.

```
Browser ──► Vercel static (dist/)         ← React/Vite UI
        └─► /api/* ──► Vercel Python fn   ← FastAPI (api/index.py → backend/app)
                          │
                          ├─► Supabase Postgres + pgvector (chunks, vectors, chat)
                          ├─► Supabase Storage (raw files)
                          └─► Gemini API (embeddings + answers)
```

## 1. Prepare Supabase

1. Create a Supabase project.
2. In the SQL editor, run `backend/sql/schema.sql` (enables `vector`, creates the
   tables, the profile trigger, and the embedding index).
3. Create a Storage bucket named `documents`.
4. Create a user, then promote to admin:
   `update public.profiles set role='admin' where email='you@example.com';`
5. Collect: Project URL, anon key, service-role key, JWT secret, and the
   **connection string** (Project Settings → Database).

## 2. Import the repo into Vercel

Vercel auto-detects the Vite frontend. `vercel.json` adds the Python function and
routes `/api/*` to it, with an SPA fallback for everything else.

## 3. Set Environment Variables (Vercel dashboard)

Backend (Python function):

| Key | Value |
|-----|-------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:PASSWORD@db.<project-ref>.supabase.co:5432/postgres` (direct IPv6-capable connection) |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `SUPABASE_SERVICE_KEY` | your `service_role` (or `sb_secret_` format) key |
| `SUPABASE_JWT_SECRET` | JWT secret / secret key value |
| `SUPABASE_ANON_KEY` | your `anon` (or `sb_publishable_` format) key |
| `SUPABASE_BUCKET` | `documents` |
| `GEMINI_API_KEY` | your Gemini API key |
| `AUTH_ENABLED` | `true` |
| `AUTO_CREATE_TABLES` | `true` (executes `schema.sql` automatically on startup) |
| `CORS_ORIGINS` | not needed for same-origin, but harmless to set your domain |

Frontend (build-time, must be prefixed `VITE_`):

| Key | Value |
|-----|-------|
| `VITE_SUPABASE_URL` | `https://<project>.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | anon key |
| `VITE_API_URL` | leave **unset** (same-origin `/api`) |

## 4. Deploy

Push to the connected branch (or click Deploy). Vercel runs `npm run build` for the
frontend and installs `requirements.txt` for the Python function.

## 5. Verify

- `https://<app>.vercel.app/api/health` → `{"status":"ok"}`
- Log in, upload a document (admin), then ask the copilot a question.

## Constraints to know

- **Function time limit.** Ingestion is synchronous (serverless has no durable
  background workers). Embedding many chunks via Gemini can be slow; keep
  individual documents modest, or run heavy ingestion against a non-serverless
  backend. `maxDuration` is set to 60s (Pro plan; Hobby may cap lower).
- **Cold starts.** First request after idle pays import + connection latency.
- **No OCR / heavy ML on Vercel.** `sentence-transformers`, `torch`, ChromaDB, and
  PaddleOCR are intentionally excluded to fit the serverless size limit.
- **Embeddings.** Gemini `text-embedding-004` (768-d). Without `GEMINI_API_KEY`,
  the backend uses deterministic mock embeddings (runs, but low retrieval quality).

## Alternative: backend on a container host

If you outgrow serverless limits, deploy `backend/` (Dockerfile / docker-compose)
to Railway/Render/Fly, point `VITE_API_URL` at it, and keep only the frontend on
Vercel. The code is identical — only `VITE_API_URL` and CORS change.
