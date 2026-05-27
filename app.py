"""Homelab-friendly web wrapper for the Life Science Watch pipeline."""

from __future__ import annotations

import json
import os
import sqlite3
from argparse import Namespace
from html import escape
from pathlib import Path
from time import perf_counter, time
from typing import Any
from uuid import uuid4

from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core.auth import (
    build_signed_role_cookie,
    credentials_are_valid,
    path_requires_auth,
    read_signed_role_cookie,
    request_has_valid_auth,
    request_has_valid_viewer_auth,
    web_session_request_is_allowed,
    viewer_account_credentials_are_valid,
    viewer_credentials_are_valid,
    viewer_request_is_allowed,
)
from core.activity import (
    ACTIVITY_AI_CHAT,
    ACTIVITY_LOGIN,
    ACTIVITY_NEWS_FILTER,
    fetch_activity_summary_filtered,
    fetch_recent_activity_filtered,
    list_activity_accounts,
    record_activity,
)
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
    REQUEST_ADMIN_PASSWORD,
    REQUEST_ADMIN_USERNAME,
    REQUEST_GUEST_PASSWORD,
    REQUEST_GUEST_USERNAME,
    REQUEST_SESSION_SECRET,
    VIEWER_ACCOUNTS,
    VIEWER_ACCESS_TOKEN,
    VIEWER_PASSWORD_HASH,
    VIEWER_USERNAME,
)
from core.dashboard import chat_about_news, fetch_dashboard_payload
from core.request_portal import create_company_request, ensure_request_tables, list_company_requests, review_company_request
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
REQUEST_PORTAL_COOKIE = "liscihub_request_session"
jinja_env = Environment(
    loader=FileSystemLoader(str(PROJECT_ROOT / "templates")),
    autoescape=select_autoescape(["html", "xml"]),
)
ACTIVITY_PERIOD_OPTIONS = [
    {"value": 1, "label": "Last 24 hours"},
    {"value": 7, "label": "Last 7 days"},
    {"value": 30, "label": "Last 30 days"},
]
ACTIVITY_TYPE_OPTIONS = [
    {"value": "ALL", "label": "All activity"},
    {"value": ACTIVITY_LOGIN, "label": "Logins"},
    {"value": ACTIVITY_NEWS_FILTER, "label": "News filtering"},
    {"value": ACTIVITY_AI_CHAT, "label": "AI chat"},
]
DASHBOARD_ASSET_VERSION = str(
    max(
        int((PROJECT_ROOT / "static" / "dashboard.css").stat().st_mtime),
        int((PROJECT_ROOT / "static" / "dashboard.js").stat().st_mtime),
    )
)


class ChatRequest(BaseModel):
    question: str
    company_name: str | None = None
    period: str = "all"


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


def _effective_session(request: Request | None) -> dict[str, str] | None:
    if request is None:
        return None
    session = _portal_session(request)
    if session:
        return session
    if request.cookies.get("liscihub_viewer_token") == VIEWER_ACCESS_TOKEN and VIEWER_ACCESS_TOKEN:
        return {"role": "viewer", "username": "Authenticated user"}
    return None


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
    if path.startswith("/requests"):
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
        web_session = _portal_session(request)
        if web_session:
            if web_session_request_is_allowed(request.method, request.url.path, web_session["role"]):
                return await call_next(request)
            response = JSONResponse(status_code=403, content={"detail": "Your account does not have access to this route"})
            response.headers["X-Request-ID"] = _get_request_id(request.headers)
            return response
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
def dashboard(request: Request):
    session = _portal_session(request)
    viewer_cookie_active = bool(request.cookies.get("liscihub_viewer_token") == VIEWER_ACCESS_TOKEN and VIEWER_ACCESS_TOKEN)
    show_signed_in = bool(session or viewer_cookie_active)
    is_admin = bool(session and session["role"] == "admin")
    response = _render_template(
        "dashboard.html",
        current_username=session["username"] if session else "Authenticated user",
        current_role=session["role"] if session else ("viewer" if viewer_cookie_active else ""),
        show_signed_in=show_signed_in,
        is_admin=is_admin,
        asset_version=DASHBOARD_ASSET_VERSION,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/activity", include_in_schema=False, response_class=HTMLResponse, response_model=None)
def activity_monitoring(request: Request):
    session = _require_portal_session(request, {"admin"})
    try:
        selected_days = int(str(request.query_params.get("days", "7")))
    except ValueError:
        selected_days = 7
    if selected_days not in {1, 7, 30}:
        selected_days = 7
    selected_username = str(request.query_params.get("username", "ALL")).strip() or "ALL"
    selected_activity_type = str(request.query_params.get("activity_type", "ALL")).strip() or "ALL"

    accounts = ["ALL", *list_activity_accounts(days=max(selected_days, 30))]
    if selected_username not in accounts:
        selected_username = "ALL"
    if selected_activity_type not in {item["value"] for item in ACTIVITY_TYPE_OPTIONS}:
        selected_activity_type = "ALL"

    response = _render_template(
        "activity_monitoring.html",
        current_role=session["role"],
        current_username=session["username"],
        activity_summary=fetch_activity_summary_filtered(
            days=selected_days,
            username=selected_username,
            activity_type=selected_activity_type,
        ),
        recent_activity=fetch_recent_activity_filtered(
            days=selected_days,
            username=selected_username,
            activity_type=selected_activity_type,
            limit=50,
        ),
        account_options=accounts,
        selected_username=selected_username,
        activity_type_options=ACTIVITY_TYPE_OPTIONS,
        selected_activity_type=selected_activity_type,
        period_options=ACTIVITY_PERIOD_OPTIONS,
        selected_days=selected_days,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/viewer", include_in_schema=False, response_class=HTMLResponse, response_model=None)
def viewer(request: Request):
    session = _portal_session(request)
    if session:
        response = RedirectResponse(url="/dashboard", status_code=307)
        response.headers["Cache-Control"] = "no-store"
        return response
    if request.cookies.get("liscihub_viewer_token") == VIEWER_ACCESS_TOKEN and VIEWER_ACCESS_TOKEN:
        response = RedirectResponse(url="/dashboard", status_code=307)
        response.headers["Cache-Control"] = "no-store"
        return response

    html_path = PROJECT_ROOT / "templates" / "viewer_login.html"
    html = html_path.read_text(encoding="utf-8")
    response = HTMLResponse(content=html, status_code=200)
    response.headers["Cache-Control"] = "no-store"
    return response


def _render_template(template_name: str, **context: Any) -> HTMLResponse:
    template = jinja_env.get_template(template_name)
    return HTMLResponse(content=template.render(**context), status_code=200)


def _portal_session(request: Request) -> dict[str, str] | None:
    return read_signed_role_cookie(request.cookies.get(REQUEST_PORTAL_COOKIE), REQUEST_SESSION_SECRET)


def _set_portal_session_cookie(response: RedirectResponse, request: Request, role: str, username: str) -> None:
    response.set_cookie(
        key=REQUEST_PORTAL_COOKIE,
        value=build_signed_role_cookie(role, username, REQUEST_SESSION_SECRET),
        httponly=True,
        secure=_is_secure_request(request),
        samesite="lax",
        max_age=60 * 60 * 12,
        path="/",
    )


def _require_portal_session(request: Request, allowed_roles: set[str] | None = None) -> dict[str, str]:
    session = _portal_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Sign in required")
    if allowed_roles and session["role"] not in allowed_roles:
        raise HTTPException(status_code=403, detail="You do not have access to this action")
    return session


def _portal_message(request: Request) -> str:
    return str(request.query_params.get("message", "")).strip()


def _normalize_company_name(value: str) -> str:
    return " ".join(value.strip().split()).upper()


def _normalize_source_url(value: str) -> str:
    return value.strip()


def _validate_request_input(company_name: str, source_url: str) -> tuple[str, str]:
    normalized_company_name = _normalize_company_name(company_name)
    normalized_source_url = _normalize_source_url(source_url)
    if not normalized_company_name:
        raise HTTPException(status_code=400, detail="Company name is required")
    if len(normalized_company_name) > 100:
        raise HTTPException(status_code=400, detail="Company name is too long")
    if not normalized_source_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Source URL must start with http:// or https://")
    return normalized_company_name, normalized_source_url


def _viewer_login_is_valid(username: str, password: str | None) -> bool:
    if viewer_account_credentials_are_valid(username, password, VIEWER_ACCOUNTS):
        return True
    return viewer_credentials_are_valid(username, password, VIEWER_USERNAME, VIEWER_PASSWORD_HASH)


@app.get("/requests/login", include_in_schema=False, response_class=HTMLResponse, response_model=None)
def request_portal_login_page(request: Request):
    session = _portal_session(request)
    if session:
        response = RedirectResponse(url="/requests", status_code=307)
        response.headers["Cache-Control"] = "no-store"
        return response
    response = _render_template(
        "request_login.html",
        guest_username=REQUEST_GUEST_USERNAME,
        admin_username=REQUEST_ADMIN_USERNAME,
        message=_portal_message(request),
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/requests/login", include_in_schema=False, response_model=None)
def request_portal_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    normalized_username = username.strip()
    role: str | None = None
    if credentials_are_valid(normalized_username, password, REQUEST_ADMIN_USERNAME, REQUEST_ADMIN_PASSWORD):
        role = "admin"
    elif _viewer_login_is_valid(normalized_username, password):
        role = "viewer"
    elif credentials_are_valid(normalized_username, password, REQUEST_GUEST_USERNAME, REQUEST_GUEST_PASSWORD):
        role = "guest"
    if not role:
        raise HTTPException(status_code=401, detail="Invalid request portal credentials")

    response = RedirectResponse(url="/requests", status_code=303)
    _set_portal_session_cookie(response, request, role, normalized_username)
    record_activity(
        normalized_username,
        role,
        ACTIVITY_LOGIN,
        "/requests/login",
        request_id=_get_request_id(request.headers),
        client_ip=_get_client_ip(request),
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/requests/logout", include_in_schema=False, response_model=None)
def request_portal_logout() -> RedirectResponse:
    response = RedirectResponse(url="/requests/login?message=Signed+out", status_code=303)
    response.delete_cookie(key=REQUEST_PORTAL_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/requests", include_in_schema=False, response_class=HTMLResponse, response_model=None)
def request_portal(request: Request):
    session = _portal_session(request)
    if not session:
        response = RedirectResponse(url="/requests/login", status_code=307)
        response.headers["Cache-Control"] = "no-store"
        return response

    ensure_request_tables()
    requests = list_company_requests(session["role"], session["username"])
    response = _render_template(
        "request_portal.html",
        current_role=session["role"],
        current_username=session["username"],
        is_admin=session["role"] == "admin",
        requests=requests,
        message=_portal_message(request),
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/requests/submit", include_in_schema=False, response_model=None)
def request_portal_submit(
    request: Request,
    company_name: str = Form(...),
    source_url: str = Form(...),
) -> RedirectResponse:
    session = _require_portal_session(request, {"guest", "viewer", "admin"})
    normalized_company_name, normalized_source_url = _validate_request_input(company_name, source_url)
    create_company_request(normalized_company_name, normalized_source_url, session["username"], session["role"])
    response = RedirectResponse(url="/requests?message=Request+submitted", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/requests/{request_id}/approve", include_in_schema=False, response_model=None)
def request_portal_approve(request: Request, request_id: str, review_note: str | None = Form(default=None)) -> RedirectResponse:
    session = _require_portal_session(request, {"admin"})
    try:
        review_company_request(request_id, session["username"], approved=True, review_note=review_note)
        message = "Request+approved"
    except ValueError as exc:
        message = escape(str(exc)).replace(" ", "+")
    response = RedirectResponse(url=f"/requests?message={message}", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/requests/{request_id}/reject", include_in_schema=False, response_model=None)
def request_portal_reject(request: Request, request_id: str, review_note: str | None = Form(default=None)) -> RedirectResponse:
    session = _require_portal_session(request, {"admin"})
    try:
        review_company_request(request_id, session["username"], approved=False, review_note=review_note)
        message = "Request+rejected"
    except ValueError as exc:
        message = escape(str(exc)).replace(" ", "+")
    response = RedirectResponse(url=f"/requests?message={message}", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/viewer", include_in_schema=False, response_model=None)
def viewer_login(
    request: Request,
    username: str | None = Form(default=None),
    password: str | None = Form(default=None),
    access_token: str | None = Form(default=None),
) -> RedirectResponse:
    normalized_username = (username or "").strip()
    token_login_is_valid = bool(VIEWER_ACCESS_TOKEN and access_token == VIEWER_ACCESS_TOKEN)
    role: str | None = None
    if credentials_are_valid(normalized_username, password, REQUEST_ADMIN_USERNAME, REQUEST_ADMIN_PASSWORD):
        role = "admin"
    elif _viewer_login_is_valid(normalized_username, password):
        role = "viewer"
    elif credentials_are_valid(normalized_username, password, REQUEST_GUEST_USERNAME, REQUEST_GUEST_PASSWORD):
        role = "guest"
    if not token_login_is_valid and not role:
        raise HTTPException(status_code=401, detail="Invalid viewer credentials")

    response = RedirectResponse(url="/dashboard", status_code=303)
    if token_login_is_valid or role in {"viewer", "admin"}:
        response.set_cookie(
            key="liscihub_viewer_token",
            value=VIEWER_ACCESS_TOKEN,
            httponly=True,
            secure=_is_secure_request(request),
            samesite="lax",
            max_age=60 * 60 * 12,
            path="/",
        )
    else:
        response.delete_cookie(key="liscihub_viewer_token", path="/")
    if role:
        _set_portal_session_cookie(response, request, role, normalized_username)
        record_activity(
            normalized_username,
            role,
            ACTIVITY_LOGIN,
            "/viewer",
            request_id=_get_request_id(request.headers),
            client_ip=_get_client_ip(request),
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
    response.delete_cookie(key=REQUEST_PORTAL_COOKIE, path="/")
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
    request: Request = None,
    company: str = "ALL",
    period: str = "week",
    topic: str = "ALL",
) -> dict[str, Any]:
    session = _effective_session(request)
    if session:
        record_activity(
            session["username"],
            session["role"],
            ACTIVITY_NEWS_FILTER,
            "/api/dashboard/news",
            activity_meta={"company": company, "period": period, "topic": topic},
            request_id=_get_request_id(request.headers) if request is not None else None,
            client_ip=_get_client_ip(request) if request is not None else None,
        )
    return fetch_dashboard_payload(company_name=company, period=period, topic=topic)


@app.post("/api/dashboard/chat")
def dashboard_chat(request: ChatRequest, http_request: Request = None) -> dict[str, Any]:
    chat_period = "all"
    session = _effective_session(http_request)
    if session:
        record_activity(
            session["username"],
            session["role"],
            ACTIVITY_AI_CHAT,
            "/api/dashboard/chat",
            activity_meta={"period": chat_period, "question_length": len(request.question.strip())},
            request_id=_get_request_id(http_request.headers) if http_request is not None else None,
            client_ip=_get_client_ip(http_request) if http_request is not None else None,
        )
    return chat_about_news(
        question=request.question,
        company_name="ALL",
        period=chat_period,
    )
