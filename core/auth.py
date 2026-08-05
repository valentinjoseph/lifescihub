"""Shared auth helpers for admin and viewer access."""

from __future__ import annotations

import base64
import hashlib
import hmac

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
WEB_SESSION_ROLES = {"guest", "viewer", "admin"}


def path_requires_auth(path: str) -> bool:
    if path in EXEMPT_AUTH_PATHS:
        return False
    if path.startswith("/static/"):
        return False
    if path.startswith("/requests"):
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

    viewer_cookie = request.cookies.get("gtm_advisor_viewer_token")
    if viewer_cookie == expected_token:
        return True

    return False


def credentials_are_valid(
    username: str | None,
    password: str | None,
    expected_username: str | None,
    expected_password_value: str | None,
) -> bool:
    if not username or not password or not expected_username or not expected_password_value:
        return False

    if not hmac.compare_digest(username, expected_username):
        return False

    normalized_expected_hash = expected_password_value.removeprefix("sha256:").strip().lower()
    if expected_password_value.startswith("sha256:") or (
        len(normalized_expected_hash) == 64 and all(character in "0123456789abcdef" for character in normalized_expected_hash)
    ):
        submitted_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(submitted_hash, normalized_expected_hash)

    return hmac.compare_digest(password, expected_password_value)


def viewer_credentials_are_valid(
    username: str | None,
    password: str | None,
    expected_username: str | None,
    expected_password_hash: str | None,
) -> bool:
    return credentials_are_valid(username, password, expected_username, expected_password_hash)


def viewer_account_credentials_are_valid(
    username: str | None,
    password: str | None,
    viewer_accounts: dict[str, str] | None,
) -> bool:
    if not username or not password or not viewer_accounts:
        return False
    expected_password_value = viewer_accounts.get(username)
    if not expected_password_value:
        return False
    return credentials_are_valid(username, password, username, expected_password_value)


def build_signed_role_cookie(role: str, username: str, secret: str) -> str:
    payload = f"{role}|{username}"
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{payload}|{signature}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("ascii")


def read_signed_role_cookie(cookie_value: str | None, secret: str) -> dict[str, str] | None:
    if not cookie_value:
        return None
    try:
        raw_token = base64.urlsafe_b64decode(cookie_value.encode("ascii")).decode("utf-8")
        role, username, signature = raw_token.split("|", 2)
    except Exception:
        return None

    if role not in WEB_SESSION_ROLES or not username:
        return None

    payload = f"{role}|{username}"
    expected_signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None
    return {"role": role, "username": username}


def viewer_request_is_allowed(method: str, path: str) -> bool:
    if not path_requires_auth(path):
        return True
    if method == "GET" and any(path.startswith(prefix) for prefix in VIEWER_ALLOWED_GET_PREFIXES):
        return True
    if method == "POST" and path in VIEWER_ALLOWED_POST_PATHS:
        return True
    return False


def web_session_request_is_allowed(method: str, path: str, role: str) -> bool:
    if role == "admin":
        if method == "GET" and path == "/activity":
            return True
        if path.startswith("/api/dashboard/"):
            return True
        return False
    if role == "viewer":
        return viewer_request_is_allowed(method, path)
    if role == "guest":
        if method == "GET" and any(path.startswith(prefix) for prefix in VIEWER_ALLOWED_GET_PREFIXES):
            return True
        return False
    return False
