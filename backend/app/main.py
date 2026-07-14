import asyncio
import logging
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .api.v1 import auth as auth_router
from .api.v1 import people as people_router
from .api.v1 import contracts as contracts_router
from .api.v1 import photos as photos_router
from .api.v1 import cards as cards_router
from .api.v1 import imports as imports_router
from .api.v1 import setup as setup_router
from .api.v1 import outlook as outlook_router
from .api.v1 import companies as companies_router
from .api.v1 import access as access_router
from .api.v1 import audit as audit_router
from .api.v1 import printers as printers_router
from .core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(self)"
        # Bridge agent runs locally on the user's machine — allow its WebSocket
        # connection on both localhost hostnames (browsers treat them separately).
        csp_connect = "'self' ws://localhost:8765 ws://127.0.0.1:8765"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            f"connect-src {csp_connect};"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Cache-Control"] = "no-store"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In the collapsed single-process (desktop) build there is no separate
    # scheduler container, so run the daily sweep in-process as a background task.
    task = None
    if settings.RUN_SCHEDULER_IN_PROCESS:
        from app.jobs.scheduler import main as scheduler_main
        task = asyncio.create_task(scheduler_main())
        logger.info("in-process scheduler started")
    try:
        yield
    finally:
        if task:
            task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(auth_router.router, prefix="/api/v1")
    app.include_router(people_router.router, prefix="/api/v1")
    app.include_router(contracts_router.router, prefix="/api/v1")
    app.include_router(photos_router.router, prefix="/api/v1")
    app.include_router(cards_router.router, prefix="/api/v1")
    app.include_router(imports_router.router, prefix="/api/v1")
    app.include_router(setup_router.router, prefix="/api/v1")
    app.include_router(outlook_router.router, prefix="/api/v1")
    app.include_router(companies_router.router, prefix="/api/v1")
    app.include_router(access_router.router, prefix="/api/v1")
    app.include_router(audit_router.router, prefix="/api/v1")
    app.include_router(printers_router.router, prefix="/api/v1")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        if settings.DEBUG:
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "traceback": traceback.format_exc()},
            )
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # ── Serve the built frontend (collapsed / desktop mode only) ──────────────
    # When SERVE_FRONTEND points at the built SPA, the backend serves it directly
    # so no separate Nginx is needed. Registered LAST so it never shadows the API
    # routes above. Real files (JS/CSS/assets) are served as-is; every other path
    # returns index.html so client-side (React Router) routes resolve.
    frontend_dir = settings.SERVE_FRONTEND
    if frontend_dir and os.path.isdir(frontend_dir):
        index_file = os.path.join(frontend_dir, "index.html")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            candidate = os.path.normpath(os.path.join(frontend_dir, full_path))
            # guard against path traversal outside the frontend dir
            if (
                full_path
                and candidate.startswith(os.path.abspath(frontend_dir))
                and os.path.isfile(candidate)
            ):
                return FileResponse(candidate)
            return FileResponse(index_file)

        logger.info("serving frontend from %s", frontend_dir)

    return app


app = create_app()
