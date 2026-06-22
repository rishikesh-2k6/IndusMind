"""FastAPI application entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.container import build_container
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def _maybe_create_tables() -> None:
    """Read schema.sql and execute the statements on the database."""
    if not settings.has_database:
        logger.warning("DATABASE_URL not set; skipping table creation")
        return
    if os.getenv("AUTO_CREATE_TABLES", "true").lower() != "true":
        return
    try:
        from sqlalchemy import text
        from app.db.session import get_engine

        # Resolve path to schema.sql
        app_dir = os.path.dirname(os.path.dirname(__file__))
        schema_path = os.path.join(app_dir, "sql", "schema.sql")
        if not os.path.exists(schema_path):
            logger.warning("schema.sql not found at %s", schema_path)
            return

        logger.info("Reading schema from %s", schema_path)
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        # Split into individual statements, respecting $$ function bodies
        statements = []
        current = []
        in_function = False

        for line in schema_sql.split('\n'):
            stripped = line.strip()
            if not stripped and not in_function and not current:
                continue

            dollar_count = stripped.count('$$')
            if dollar_count % 2 == 1:
                in_function = not in_function

            current.append(line)

            if stripped.endswith(';') and not in_function:
                stmt = '\n'.join(current).strip()
                if stmt and not stmt.startswith('--'):
                    statements.append(stmt)
                current = []

        engine = get_engine()
        async with engine.begin() as conn:
            for stmt in statements:
                first_line = stmt.split('\n')[0][:80]
                logger.info("Executing statement: %s", first_line)
                await conn.execute(text(stmt))

        logger.info("Database schema initialized successfully from schema.sql!")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not initialize database schema (continuing): %s", exc)



@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Starting %s", settings.app_name)
    await _maybe_create_tables()
    app.state.container = build_container()
    logger.info("Service container ready")
    try:
        yield
    finally:
        from app.db.session import dispose_engine

        await dispose_engine()
        logger.info("Shutdown complete")


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="AI-powered Industrial Knowledge Intelligence Platform — backend API.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
