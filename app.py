"""Homelab-friendly web wrapper for the Life Science Watch pipeline."""

from __future__ import annotations

import json
import os
import sqlite3
from argparse import Namespace
from pathlib import Path
from time import perf_counter, time
from typing import Any
from uuid import uuid4

from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core.auth import path_requires_auth, request_has_valid_auth, request_has_valid_viewer_auth, viewer_request_is_allowed
from core.config import (
    ALLOWED_HOSTS,
    API_AUTH_TOKEN,
    API_ENABLE_DOCS,
    API_REQUIRE_AUTH,
    API_TITLE,
    API_VERSION,
    CHAT_RATE_LIMIT_MAX_REQUESTS,
    PUBLIC_RATE_LIMIT_MAX_REQUESTS,
    PUBLIC_RATE_LIMIT_WINDOW_SECONDS,
    RATE_LIMIT_ENABLED,
    VIEWER_ACCESS_TOKEN,
)
from core.dashboard import chat_about_news, fetch_dashboard_payload
from db.session import engine
from orchestration.LS_MAIN_REFACTORED import PROJECT_ROOT, run_pipeline


app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    docs_url="/docs" if API_ENABLE_DOCS else None,
    redoc_url="/redoc" if API_ENABLE_DOCS else None,
    openapi_url="/openapi.json" if API_ENABLE_DOCS else None,
)
_run_lock = Lock()
_rate_limit_lock = Lock()
RATE_LIMIT_BUCKETS = {
    "public": defaultdict(deque),
    "chat": defaultdict(deque),
}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class ChatRequest(BaseModel):
    question: str
    company_name: str | None = None
    period: str = "week"


def _default_paths() -> dict[str, str]:
    data_dir = PROJECT_ROOT / "data"
    outputs_dir = PROJECT_ROOT / "outputs"
    return {
        "sources": os.getenv("LSW_SOURCES", str(data_dir / "sources.csv")),
        "load_config": os.getenv("LSW_LOAD_CONFIG", str(data_dir / "load_config.csv")),
        "scraping_config": os.getenv("LSW_SCRAPING_CONFIG", str(data_dir / "scraping_config.json")),
        "db_path": os.getenv("LSW_DB_PATH", str(data_dir / "lifescience_watch.db")),
        "output_dir": os.getenv("LSW_OUTPUT_DIR", str(outputs_dir)),
    }


def _pipeline_args(dry_run: bool = False, max_workers: int | None = None, verbose: bool = False) -> Namespace:
    paths = _default_paths()
    return Namespace(
        sources=paths["sources"],
        load_config=paths["load_config"],
        scraping_config=paths["scraping_config"],
        db_path=paths["db_path"],
        output_dir=paths["output_dir"],
        max_workers=max_workers,
        dry_run=dry_run,
        verbose=verbose,
    )


def _db_info() -> dict[str, Any]:
    db_path = Path(_default_paths()["db_path"])
    if not db_path.exists():
        return {"exists": False}

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        tables = [row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        latest_run = connection.execute(
            """
            SELECT run_id, run_name, company_name, run_status, records_inserted, run_end_ts
            FROM load_monitoring
            ORDER BY run_end_ts DESC
            LIMIT 1
            """
        ).fetchone()

    return {
        "exists": True,
        "tables": tables,
        "latest_run": dict(latest_run) if latest_run else None,
    }


def _postgres_info() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            current = connection.execute(
                text("SELECT current_database() AS db, current_user AS user")
            ).mappings().one()
            schemas = [
                row["schema_name"]
                for row in connection.execute(
                    text(
                        """
                        SELECT schema_name
                        FROM information_schema.schemata
                        WHERE schema_name IN ('public', 'tech')
                        ORDER BY schema_name
                        """
                    )
                ).mappings()
            ]
        return {
            "reachable": True,
            "current_database": current["db"],
            "current_user": current["user"],
            "schemas": schemas,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "error": str(exc),
        }


def _database_ready() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _get_request_id(headers: dict) -> str:
    return headers.get("x-request-id") or str(uuid4())


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first_hop = forwarded_for.split(",")[0].strip()
        if first_hop:
            return first_hop
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _is_secure_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip() == "https"
    return request.url.scheme == "https"


def _rate_limit_scope(method: str, path: str) -> str | None:
    if method == "POST" and path == "/api/dashboard/chat":
        return "chat"
    if path in {"/", "/dashboard", "/viewer", "/viewer/logout"}:
        return "public"
    if path.startswith("/static/"):
        return "public"
    if method == "GET" and path == "/api/dashboard/news":
        return "public"
    return None


def _rate_limit_max_requests(scope: str) -> int:
    if scope == "chat":
        return CHAT_RATE_LIMIT_MAX_REQUESTS
    return PUBLIC_RATE_LIMIT_MAX_REQUESTS


def _consume_rate_limit(scope: str, client_ip: str, now: float | None = None) -> tuple[bool, int]:
    timestamp = now if now is not None else time()
    window_start = timestamp - PUBLIC_RATE_LIMIT_WINDOW_SECONDS
    max_requests = _rate_limit_max_requests(scope)

    with _rate_limit_lock:
        bucket = RATE_LIMIT_BUCKETS[scope][client_ip]
        while bucket and bucket[0] <= window_start:
            bucket.popleft()
        if len(bucket) >= max_requests:
            retry_after = max(1, int(bucket[0] + PUBLIC_RATE_LIMIT_WINDOW_SECONDS - timestamp))
            return False, retry_after
        bucket.append(timestamp)
    return True, 0


app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")
if ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = _get_request_id(request.headers)
    started_at = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - started_at) * 1000
    response.headers["X-Request-ID"] = request_id
    for key, value in SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    if _is_secure_request(request):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    print(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            }
        ),
        flush=True,
    )
    return response


@app.middleware("http")
async def enforce_api_auth(request: Request, call_next):
    if API_REQUIRE_AUTH and path_requires_auth(request.url.path):
        if request_has_valid_auth(request.headers, API_AUTH_TOKEN):
            return await call_next(request)
        if request_has_valid_viewer_auth(request, VIEWER_ACCESS_TOKEN):
            if viewer_request_is_allowed(request.method, request.url.path):
                return await call_next(request)
            response = JSONResponse(status_code=403, content={"detail": "Viewer access is read-only for this route"})
            response.headers["X-Request-ID"] = _get_request_id(request.headers)
            return response
        response = JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        response.headers["X-Request-ID"] = _get_request_id(request.headers)
        return response
    return await call_next(request)


@app.middleware("http")
async def enforce_rate_limits(request: Request, call_next):
    if not RATE_LIMIT_ENABLED:
        return await call_next(request)
    if request_has_valid_auth(request.headers, API_AUTH_TOKEN):
        return await call_next(request)

    scope = _rate_limit_scope(request.method, request.url.path)
    if not scope:
        return await call_next(request)

    allowed, retry_after = _consume_rate_limit(scope, _get_client_ip(request))
    if allowed:
        return await call_next(request)

    response = JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please slow down and try again shortly."},
    )
    response.headers["Retry-After"] = str(retry_after)
    response.headers["X-Request-ID"] = _get_request_id(request.headers)
    return response


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    html_path = PROJECT_ROOT / "templates" / "dashboard.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/viewer", include_in_schema=False, response_class=HTMLResponse, response_model=None)
def viewer(request: Request):
    if request.cookies.get("liscihub_viewer_token") == VIEWER_ACCESS_TOKEN and VIEWER_ACCESS_TOKEN:
        response = RedirectResponse(url="/dashboard", status_code=307)
        response.headers["Cache-Control"] = "no-store"
        return response

    html_path = PROJECT_ROOT / "templates" / "viewer_login.html"
    html = html_path.read_text(encoding="utf-8")
    response = HTMLResponse(content=html, status_code=200)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/viewer", include_in_schema=False, response_model=None)
def viewer_login(request: Request, access_token: str = Form(...)) -> RedirectResponse:
    if not VIEWER_ACCESS_TOKEN or access_token != VIEWER_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid viewer token")

    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(
        key="liscihub_viewer_token",
        value=VIEWER_ACCESS_TOKEN,
        httponly=True,
        secure=_is_secure_request(request),
        samesite="lax",
        max_age=60 * 60 * 12,
        path="/",
    )
    response.set_cookie(
        key="liscihub_viewer_mode",
        value="1",
        httponly=False,
        secure=_is_secure_request(request),
        samesite="lax",
        max_age=60 * 60 * 12,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/viewer/logout", include_in_schema=False)
def viewer_logout() -> RedirectResponse:
    response = RedirectResponse(url="/dashboard", status_code=307)
    response.delete_cookie(key="liscihub_viewer_token")
    response.delete_cookie(key="liscihub_viewer_mode")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health/live")
def health_live() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "lifescience_watch",
    }


@app.get("/health/ready")
def health_ready() -> dict[str, Any]:
    db_ok = _database_ready()
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "lifescience_watch",
        "database": "ok" if db_ok else "error",
        "lock_held": _run_lock.locked(),
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return health_ready()


@app.get("/status")
def status() -> dict[str, Any]:
    return {
        "service": "lifescience_watch",
        "sqlite": _db_info(),
        "postgres": _postgres_info(),
        "config": {
            "sources_configured": Path(_default_paths()["sources"]).exists(),
            "load_config_configured": Path(_default_paths()["load_config"]).exists(),
            "scraping_config_configured": Path(_default_paths()["scraping_config"]).exists(),
            "output_dir_exists": Path(_default_paths()["output_dir"]).exists(),
        },
    }


@app.post("/run")
def run_now() -> dict[str, Any]:
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A pipeline run is already in progress")

    try:
        exit_code = run_pipeline(_pipeline_args())
    finally:
        _run_lock.release()

    return {
        "service": "lifescience_watch",
        "exit_code": exit_code,
        "sqlite": _db_info(),
        "postgres": _postgres_info(),
    }


@app.get("/api/dashboard/news")
def dashboard_news(
    company: str = "ALL",
    period: str = "week",
) -> dict[str, Any]:
    return fetch_dashboard_payload(company_name=company, period=period)


@app.post("/api/dashboard/chat")
def dashboard_chat(request: ChatRequest) -> dict[str, Any]:
    return chat_about_news(
        question=request.question,
        company_name=request.company_name,
        period=request.period,
    )
