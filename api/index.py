"""Vercel Python serverless entrypoint.

Exposes the FastAPI ASGI app so Vercel can serve it. `vercel.json` rewrites
`/api/*` to this function; the `backend/` package is bundled via `includeFiles`.
"""
import os
import sys

# Make the backend package importable from the repo root.
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.main import app  # noqa: E402  (re-exported as the ASGI handler)

__all__ = ["app"]
