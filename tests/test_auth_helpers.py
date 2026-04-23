from __future__ import annotations

import unittest

from fastapi import Request

from core.auth import (
    path_requires_auth,
    request_has_valid_auth,
    request_has_valid_viewer_auth,
    viewer_credentials_are_valid,
    viewer_request_is_allowed,
)


def build_request(
    path: str,
    headers: list[tuple[bytes, bytes]] | None = None,
    query_string: bytes = b"",
) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": headers or [],
        "query_string": query_string,
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
        "server": ("testserver", 80),
    }
    return Request(scope)


class AuthHelperTests(unittest.TestCase):
    def test_path_requires_auth_keeps_dashboard_public(self) -> None:
        self.assertFalse(path_requires_auth("/"))
        self.assertFalse(path_requires_auth("/dashboard"))
        self.assertFalse(path_requires_auth("/viewer"))
        self.assertFalse(path_requires_auth("/static/dashboard.js"))
        self.assertTrue(path_requires_auth("/status"))
        self.assertTrue(path_requires_auth("/api/dashboard/news"))

    def test_admin_auth_supports_api_key_bearer_and_legacy_header(self) -> None:
        expected = "admin-token"
        self.assertTrue(request_has_valid_auth({"x-api-key": expected}, expected))
        self.assertTrue(request_has_valid_auth({"authorization": f"Bearer {expected}"}, expected))
        self.assertTrue(request_has_valid_auth({"x-run-token": expected}, expected))
        self.assertFalse(request_has_valid_auth({"x-api-key": "wrong"}, expected))

    def test_viewer_auth_supports_header_and_cookie(self) -> None:
        expected = "viewer-token"
        header_request = build_request("/api/dashboard/news", headers=[(b"x-viewer-token", expected.encode())])
        cookie_request = build_request(
            "/api/dashboard/news",
            headers=[(b"cookie", f"liscihub_viewer_token={expected}".encode())],
        )
        self.assertTrue(request_has_valid_viewer_auth(header_request, expected))
        self.assertTrue(request_has_valid_viewer_auth(cookie_request, expected))

    def test_viewer_credentials_accept_sha256_password_hash(self) -> None:
        self.assertTrue(
            viewer_credentials_are_valid(
                "guest",
                "viewer-password",
                "guest",
                "sha256:5b601f1dddff95687115700d6ab159cd20331cb51090c2fd0479d518460300a6",
            )
        )
        self.assertFalse(
            viewer_credentials_are_valid(
                "guest",
                "wrong-password",
                "guest",
                "sha256:5b601f1dddff95687115700d6ab159cd20331cb51090c2fd0479d518460300a6",
            )
        )
        self.assertFalse(
            viewer_credentials_are_valid(
                "other-user",
                "viewer-password",
                "guest",
                "sha256:5b601f1dddff95687115700d6ab159cd20331cb51090c2fd0479d518460300a6",
            )
        )

    def test_viewer_credentials_accept_direct_password_value(self) -> None:
        self.assertTrue(
            viewer_credentials_are_valid(
                "guest",
                "viewer-password",
                "guest",
                "viewer-password",
            )
        )
        self.assertFalse(
            viewer_credentials_are_valid(
                "guest",
                "wrong-password",
                "guest",
                "viewer-password",
            )
        )

    def test_viewer_policy_is_read_mostly(self) -> None:
        self.assertTrue(viewer_request_is_allowed("GET", "/api/dashboard/news"))
        self.assertTrue(viewer_request_is_allowed("POST", "/api/dashboard/chat"))
        self.assertFalse(viewer_request_is_allowed("POST", "/run"))
        self.assertFalse(viewer_request_is_allowed("GET", "/status"))


if __name__ == "__main__":
    unittest.main()
