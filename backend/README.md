# Industrial Knowledge Brain — Backend

AI-powered Industrial Knowledge Intelligence Platform. Admins ingest documents
(manuals, inspection/maintenance/incident reports, SOPs, spreadsheets, scanned
images); users query the knowledge base in natural language and get source-backed
answers via RAG + Gemini.

> Backend only. The React/JSX (Vite) frontend lives at the repo root and talks to
> this API over JSON REST. OpenAPI docs are served at `/docs`.

## Supported files

Any file. Rich formats have dedicated extractors — **PDF** (PyMuPDF), **DOCX**,
**PPTX** (stdlib), **XLSX**, **CSV**, **HTML**, and **images** (OCR, optional).
Everything else (TXT, MD, JSON, XML, YAML, source code, logs, …) goes through a
universal text decoder. True binaries are rejected with a clear error and the
document is marked `failed`. Uploads stream to **Supabase Storage** (bucket
auto-created); chunks + embeddings land in **Supabase Postgres (pgvector)**.

## Knowledge graph

During ingestion, Gemini also extracts **industrial entities** (equipment,
failures, maintenance, inspections, incidents, people, locations) and the
**relationships** between them into `kg_entities` / `kg_relations` (Supabase
Postgres — no Neo4j, so it stays Vercel-deployable). This powers structured,
cross-document queries that RAG alone can't answer:

- `GET /equipment` — every asset mentioned across all documents
- `GET /equipment/{key}/history` — that asset's failures, maintenance, and
  inspections as a timeline (e.g. `/equipment/p101/history`)
- `GET /failure-patterns` — recurring failures ranked by occurrence + affected assets

Toggle with `ENABLE_KG` (requires `GEMINI_API_KEY`).

## Architecture

```
Admin → POST /documents/upload → Supabase Storage + documents row
        extract (any file) → clean → chunk (1000/200) → batch-embed → pgvector
        → entity/relation extraction → kg_entities/kg_relations
        → status=ready  (synchronous ingestion, so it works on serverless / Vercel)

User → POST /query → embed → pgvector top-k → context → Gemini
                 → { answer, sources[], confidence_score, related_documents[] }
```

- **API:** FastAPI (async), repository pattern (router → service → repository)
- **Auth + Storage + Postgres + vectors:** Supabase (Postgres + **pgvector**)
- **LLM + embeddings:** Gemini (768-d `text-embedding-004`); deterministic mock
  embeddings when no key is set, so it runs offline

> Deployable on **Vercel** as a Python serverless function — see
> [`../DEPLOY_VERCEL.md`](../DEPLOY_VERCEL.md). Heavy deps (torch, ChromaDB,
> PaddleOCR) are intentionally excluded to fit the serverless size limit.

## Layout

```
app/
  core/        config, logging, exceptions, security, deps, container
  db/          sqlalchemy engine, supabase storage
  models/      ORM tables (incl. pgvector embedding) + Pydantic schemas
  repositories/
  services/    document_processing, chunking, embedding, vector_store,
               ingestion, rag, summarization, llm
  api/v1/      health, auth, documents, query, chat
sql/schema.sql
tests/
```

## Quick start (Docker — local pgvector Postgres)

```bash
cd backend
cp .env.example .env        # add GEMINI_API_KEY (DB/auth are overridden for local)
docker compose up --build
```

Spins up a local `pgvector/pgvector` Postgres + the API at http://localhost:8000
(docs at `/docs`), with `AUTH_ENABLED=false` and tables auto-created.

## Quick start (local Python)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

To run with **no external services** (mock LLM + mock embeddings, no auth) you
still need a Postgres with pgvector for storage/search; the Docker path above is
the easiest. For a pure smoke test without a DB:

```bash
AUTH_ENABLED=false uvicorn app.main:app --reload   # /health works; queries need a DB
```

## Supabase setup

1. Create a project; copy URL, anon key, service-role key, and JWT secret into `.env`.
2. Set `DATABASE_URL` to the connection string with the async driver:
   `postgresql+asyncpg://postgres:PASSWORD@db.<project>.supabase.co:5432/postgres`
3. Run `sql/schema.sql` in the SQL editor (creates tables + a profile trigger).
4. Create a Storage bucket named `documents` (or change `SUPABASE_BUCKET`).
5. Create a user, then promote to admin:
   `update public.profiles set role='admin' where email='you@example.com';`

## Auth (frontend handshake)

The frontend logs in with the Supabase JS SDK and sends the JWT as
`Authorization: Bearer <token>`. The backend verifies the same token (HS256) and
resolves the role from `profiles`. `require_admin` guards write endpoints;
`require_user` guards copilot endpoints.

## Key endpoints

| Method | Path                              | Role  |
|--------|-----------------------------------|-------|
| GET    | `/health`                         | open  |
| GET    | `/api/v1/auth/me`                 | user  |
| POST   | `/api/v1/documents/upload`        | admin |
| GET    | `/api/v1/documents`               | admin |
| GET    | `/api/v1/documents/{id}`          | admin |
| GET    | `/api/v1/documents/{id}/status`   | admin |
| DELETE | `/api/v1/documents/{id}`          | admin |
| POST   | `/api/v1/query`                   | user  |
| POST   | `/api/v1/search`                  | user  |
| POST   | `/api/v1/summarize`               | user  |
| GET    | `/api/v1/library`                 | user  |
| GET    | `/api/v1/equipment`               | user  |
| GET    | `/api/v1/equipment/{key}/history` | user  |
| GET    | `/api/v1/failure-patterns`        | user  |
| GET    | `/api/v1/graph/stats`             | user  |
| GET    | `/api/v1/chat/sessions`           | user  |
| GET    | `/api/v1/chat/sessions/{id}`      | user  |

## Demo seed

Load sample industrial documents (`backend/sample_data/`) and run example queries
against a running backend:

```bash
# easiest: start the API with AUTH_ENABLED=false, then
cd backend
python scripts/seed.py

# against an auth-enabled API, pass an admin Supabase access token
SEED_TOKEN=<jwt> API_URL=http://localhost:8000 python scripts/seed.py
```

It uploads 5 sample docs (pump maintenance report, boiler inspection + startup SOP,
compressor incident report, equipment CSV log), waits for ingestion, then asks demo
questions like *"Why did Pump P101 fail?"* and *"What inspections are overdue?"*.

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

## Configuration

See `.env.example`. Notable flags:

- `EMBEDDING_PROVIDER` — `gemini` (768-d), `huggingface` (HF Inference API,
  `BAAI/bge-base-en-v1.5`, 768-d; set `HF_API_TOKEN`), or `mock` (offline
  deterministic). The pgvector column is fixed at `EMBEDDING_DIM` (768); changing
  the model's dimension needs a schema change + re-index. Switching providers
  also requires re-indexing existing documents (different vector spaces).
- `ENABLE_OCR` — off by default (PaddleOCR is heavy and excluded from the Vercel
  build). Enable + install paddleocr locally to process images/scanned documents.
- `AUTH_ENABLED=false` — local dev escape hatch (returns a synthetic admin).
- `AUTO_CREATE_TABLES` — create tables + enable pgvector on startup (handy for the
  Docker/local DB; set `false` on Supabase where you run `sql/schema.sql`).

## Extension points (not in this MVP)

- **Neo4j knowledge graph** — entity/relationship layer over equipment & failures.
- **LangGraph agents** — Search / Summary / Maintenance / RCA / Compliance.
