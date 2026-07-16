import logging
import os
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .auth import CurrentUser, get_current_user
from .config import Settings, get_settings
from .db import get_supabase
from .models.schemas import MeOut
from .rate_limit import limiter
from .routers import admin, documents, exams, usage
from .routers.admin import is_super_admin
from .services import account


def _configure_logging() -> None:
    """Emit the app's logger.* calls at the configured level so platform log
    drains (and any alerting built on them) can see warnings/errors."""
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app() -> FastAPI:
    _configure_logging()
    settings = get_settings()
    app = FastAPI(title="Exam Generator API")

    # Per-client HTTP rate limiting (see app/rate_limit.py). The middleware
    # applies default_limits to every route; hot/expensive routes add stricter
    # per-route limits via the @limiter.limit decorator.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Restrict CORS to the exact origins/methods/headers the SPA uses rather
    # than wildcards — a permissive policy combined with credentials is a
    # security risk (SonarQube S5122).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(documents.router)
    app.include_router(exams.router)
    app.include_router(usage.router)
    app.include_router(admin.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/me")
    @limiter.limit("30/minute")
    def me(
        request: Request,
        user: Annotated[CurrentUser, Depends(get_current_user)],
        cfg: Annotated[Settings, Depends(get_settings)],
    ) -> MeOut:
        return MeOut(
            id=user.id,
            email=user.email,
            is_admin=is_super_admin(user.email, cfg),
        )

    @app.delete("/api/me", status_code=204)
    @limiter.limit("5/minute")
    async def delete_me(
        request: Request,
        user: Annotated[CurrentUser, Depends(get_current_user)],
        cfg: Annotated[Settings, Depends(get_settings)],
    ) -> Response:
        """GDPR/CCPA "delete my data": erase all of the caller's storage objects
        and database rows. The Supabase auth user itself is managed by Supabase
        and is not removed here."""
        sb = get_supabase()
        await run_in_threadpool(account.delete_all_user_data, sb, cfg, user.id)
        return Response(status_code=204)

    return app


app = create_app()
