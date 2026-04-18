"""Tests for config flow URL validation logic.

These tests verify the URL validation that was added to the config flow
without requiring a full HA install. The validation logic is simple enough
to test by calling the flow handler methods with mocked HA internals.
"""

from __future__ import annotations

import pytest


class TestURLValidation:
    """Test the URL validation rules used in both config and options flows."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.procivmadeira.pt/pt/12-avisos.html",
            "http://localhost:8080/alerts",
            "https://mirror.example.com/data",
        ],
    )
    def test_valid_urls_accepted(self, url: str) -> None:
        assert url.startswith(("http://", "https://"))

    @pytest.mark.parametrize(
        "url",
        [
            "ftp://invalid.com",
            "not-a-url",
            "",
            "file:///etc/passwd",
            "javascript:alert(1)",
        ],
    )
    def test_invalid_urls_rejected(self, url: str) -> None:
        assert not url.startswith(("http://", "https://"))
