from __future__ import annotations

import unittest
from unittest.mock import patch

from app import request_portal_approve, request_portal_submit
from core.request_portal import normalize_industry_sector


class RequestPortalTests(unittest.TestCase):
    def test_normalize_industry_sector_accepts_configured_sectors(self) -> None:
        self.assertEqual(normalize_industry_sector(" banking "), "BANKING")
        self.assertEqual(normalize_industry_sector("TELECOMMUNICATION"), "TELECOMMUNICATION")

    def test_normalize_industry_sector_rejects_unknown_sector(self) -> None:
        with self.assertRaises(ValueError):
            normalize_industry_sector("RETAIL")

    def test_request_submit_passes_selected_industry_sector(self) -> None:
        with patch("app._require_portal_session", return_value={"username": "guest", "role": "guest"}), patch(
            "app.create_company_request",
            return_value="request-1",
        ) as create_company_request:
            response = request_portal_submit(
                request=object(),
                company_name="Example Bank",
                industry_sector="BANKING",
                source_url="https://example.com/news",
            )

        self.assertEqual(response.status_code, 303)
        create_company_request.assert_called_once_with(
            "EXAMPLE BANK",
            "BANKING",
            "https://example.com/news",
            "guest",
            "guest",
        )

    def test_request_approval_passes_admin_corrected_industry_sector(self) -> None:
        with patch("app._require_portal_session", return_value={"username": "admin", "role": "admin"}), patch(
            "app.review_company_request"
        ) as review_company_request:
            response = request_portal_approve(
                request=object(),
                request_id="request-1",
                industry_sector="DEFENSE",
                review_note="Corrected sector",
            )

        self.assertEqual(response.status_code, 303)
        review_company_request.assert_called_once_with(
            "request-1",
            "admin",
            approved=True,
            review_note="Corrected sector",
            industry_sector="DEFENSE",
        )


if __name__ == "__main__":
    unittest.main()
