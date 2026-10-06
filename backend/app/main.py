"""
app/main.py
===========
FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.router import api_router
from app.core.config import settings


# --- Rate limiter (SlowAPI) ---
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Boot-time setup (DB tables for dev only — Alembic is the source of truth in prod)
    if not settings.is_production and not settings.DATABASE_URL.startswith("postgresql"):
        from app.db.base import Base
        from app.db.session import engine
        Base.metadata.create_all(bind=engine)
        # Seed roles, currencies
        from app.db.session import SessionLocal
        from app.services.auth_service import _seed_default_roles
        from app.api.v1.endpoints.currencies import _ensure_currencies_seeded
        with SessionLocal() as db:
            _seed_default_roles(db)
            _ensure_currencies_seeded(db)
            db.commit()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI Business Workforce backend — multi-currency, multi-tenant, AI-augmented. "
        "USD is the system default currency; every organization can override its own."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Security headers middleware ---
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# --- Healthcheck ---
@app.get("/health", tags=["meta"])
def healthcheck():
    return {"status": "ok", "env": settings.APP_ENV}


# --- Routes ---
app.include_router(api_router, prefix=settings.APP_API_PREFIX)


# --- Global error handler for auth errors ---
from app.services.auth_service import AuthError  # noqa: E402


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"detail": str(exc) or exc.code, "code": exc.code},
    )
