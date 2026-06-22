"""FastAPI dependencies: DB session, current user, role guards, container access."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.container import ServiceContainer
from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_supabase_jwt
from app.db.session import get_session
from app.models.schemas import CurrentUser
from app.repositories.profile_repo import ProfileRepository

# auto_error=False so we can raise our own structured AuthError.
_bearer = HTTPBearer(auto_error=False)

# Stable synthetic identity used when AUTH_ENABLED=false (local dev).
_DEV_USER = CurrentUser(
    id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    email="dev@local",
    role="admin",
)


def get_container(request: Request) -> ServiceContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        # Serverless runtimes (e.g. Vercel) may not run ASGI lifespan startup,
        # so build the container lazily and cache it on first request.
        from app.core.container import build_container

        container = build_container()
        request.app.state.container = container
    return container


async def get_db() -> AsyncSession:
    async for session in get_session():
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """Resolve the authenticated user from the Supabase JWT.

    Role comes from the `profiles` table when present, else from the JWT's
    app_metadata/user_metadata role claim, else defaults to "user".
    """
    if not settings.auth_enabled:
        return _DEV_USER

    if credentials is None:
        raise AuthError("Missing bearer token")

    payload = decode_supabase_jwt(credentials.credentials)
    sub = payload.get("sub")
    if not sub:
        raise AuthError("Token missing subject")

    try:
        user_id = uuid.UUID(str(sub))
    except ValueError as exc:
        raise AuthError("Token subject is not a valid user id") from exc

    email = payload.get("email")
    role = _role_from_claims(payload)

    profile = await ProfileRepository(db).get(user_id)
    if profile is not None:
        role = profile.role

    return CurrentUser(id=user_id, email=email, role=role if role in ("admin", "user") else "user")


def _role_from_claims(payload: dict) -> str:
    for container_key in ("app_metadata", "user_metadata"):
        meta = payload.get(container_key) or {}
        if isinstance(meta, dict) and meta.get("role") in ("admin", "user"):
            return meta["role"]
    if payload.get("role") in ("admin", "user"):
        return payload["role"]
    return "user"


async def require_user(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Any authenticated user (admin or user)."""
    return user


async def require_admin(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if user.role != "admin":
        raise ForbiddenError("Admin privileges required")
    return user
