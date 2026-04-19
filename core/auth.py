"""Shared auth helpers for admin and viewer access."""

from __future__ import annotations

from fastapi import Request

EXEMPT_AUTH_PATHS = {
    "/",
    "/dashboard",
    "/viewer",
    "/viewer/logout",
    "/health",
    "/health/live",
    "/health/ready",
}
VIEWER_ALLOWED_POST_PATHS = {"/api/dashboard/chat"}
VIEWER_ALLOWED_GET_PREFIXES = {"/api/dashboard/", "/static/"}


def path_requires_auth(path: str) -> bool:
    if path in EXEMPT_AUTH_PATHS:
        return False
    if path.startswith("/static/"):
        return False
    return True


def request_has_valid_auth(headers: dict, expected_token: str | None) -> bool:
    if not expected_token:
        return False

    api_key = headers.get("x-api-key")
    if api_key == expected_token:
        return True

    legacy_token = headers.get("x-run-token")
    if legacy_token == expected_token:
        return True

    authorization = headers.get("authorization", "")
    if authorization == f"Bearer {expected_token}":
        return True

    return False


def request_has_valid_viewer_auth(request: Request, expected_token: str | None) -> bool:
    if not expected_token:
        return False

    viewer_header = request.headers.get("x-viewer-token")
    if viewer_header == expected_token:
        return True

    viewer_cookie = request.cookies.get("liscihub_viewer_token")
    if viewer_cookie == expected_token:
        return True

    return False


def viewer_request_is_allowed(method: str, path: str) -> bool:
    if not path_requires_auth(path):
        return True
    if method == "GET" and any(path.startswith(prefix) for prefix in VIEWER_ALLOWED_GET_PREFIXES):
        return True
    if method == "POST" and path in VIEWER_ALLOWED_POST_PATHS:
        return True
    return False
