"""Tests for alerts.py — parsing, color classification, and translation."""

from __future__ import annotations

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

# HA stubs are installed by conftest.py before this module is collected.
from custom_components.prociv_madeira.alerts import REGIONS
from custom_components.prociv_madeira.alerts import _classify_by_hue
from custom_components.prociv_madeira.alerts import _color_to_alert_type
from custom_components.prociv_madeira.alerts import _parse_date_range
from custom_components.prociv_madeira.alerts import _translate_description
from custom_components.prociv_madeira.alerts import _translate_problem_type
from custom_components.prociv_madeira.alerts import fetch_alerts

# ---------------------------------------------------------------------------
# _color_to_alert_type
# ---------------------------------------------------------------------------


class TestColorToAlertType:
    """Tests for _color_to_alert_type."""

    @pytest.mark.parametrize(
        ("style", "expected"),
        [
            ("background-color: #00b050;", "green"),
            ("background-color: #ffd712;", "yellow"),
            ("background-color: #ffff00;", "yellow"),
            ("background-color: #ffa500;", "orange"),
            ("background-color: #ff8c00;", "orange"),
            ("background-color: #ed7d31;", "orange"),
            ("background-color: #ff0000;", "red"),
            ("background-color: #cc0000;", "red"),
            ("background-color: #c00000;", "red"),
        ],
    )
    def test_known_colors(self, style: str, expected: str) -> None:
        assert _color_to_alert_type(style) == expected

    def test_no_background_color(self) -> None:
        assert _color_to_alert_type("color: red;") is None

    def test_empty_style(self) -> None:
        assert _color_to_alert_type("") is None

    def test_unknown_color_falls_back_to_hue(self) -> None:
        result = _color_to_alert_type("background-color: #b00000;")
        assert result == "red"


# ---------------------------------------------------------------------------
# _classify_by_hue
# ---------------------------------------------------------------------------


class TestClassifyByHue:
    """Tests for _classify_by_hue."""

    @pytest.mark.parametrize(
        ("hex_color", "expected"),
        [
            ("#ff0000", "red"),
            ("#cc0000", "red"),
            ("#ff4500", "red"),
            ("#ff8c00", "orange"),
            ("#ffa500", "orange"),
            ("#ffd700", "yellow"),
            ("#ffff00", "yellow"),
            ("#00ff00", "green"),
            ("#808080", "green"),
            ("#ffffff", "green"),
        ],
    )
    def test_hue_classification(self, hex_color: str, expected: str) -> None:
        assert _classify_by_hue(hex_color) == expected

    def test_short_hex(self) -> None:
        assert _classify_by_hue("#f00") == "red"

    def test_invalid_hex_returns_green(self) -> None:
        assert _classify_by_hue("not-a-color") == "green"


# ---------------------------------------------------------------------------
# _parse_date_range
# ---------------------------------------------------------------------------


class TestParseDateRange:
    """Tests for _parse_date_range."""

    def test_valid_range(self) -> None:
        text = "Em vigor de, 2025-01-15 06:00:00 até 2025-01-16 00:00:00"
        start, end = _parse_date_range(text)
        assert start is not None
        assert end is not None
        assert start.year == 2025
        assert start.month == 1
        assert start.day == 15
        assert end.day == 16

    def test_t_separator(self) -> None:
        text = "Em vigor de, 2025-01-15T06:00:00 até 2025-01-16T00:00:00"
        start, end = _parse_date_range(text)
        assert start is not None
        assert end is not None

    def test_without_seconds(self) -> None:
        text = "Em vigor de, 2025-01-15 06:00 até 2025-01-16 00:00"
        start, end = _parse_date_range(text)
        assert start is not None
        assert end is not None

    def test_no_match(self) -> None:
        start, end = _parse_date_range("No date range here")
        assert start is None
        assert end is None

    def test_empty_string(self) -> None:
        start, end = _parse_date_range("")
        assert start is None
        assert end is None


# ---------------------------------------------------------------------------
# _translate_problem_type
# ---------------------------------------------------------------------------


class TestTranslateProblemType:
    """Tests for _translate_problem_type."""

    @pytest.mark.parametrize(
        ("pt", "en"),
        [
            ("Agitação Marítima", "Rough Seas"),
            ("Chuva", "Rain"),
            ("Vento", "Wind"),
            ("Trovoada", "Thunderstorm"),
        ],
    )
    def test_known_types(self, pt: str, en: str) -> None:
        assert _translate_problem_type(pt) == en

    def test_unknown_type_returns_original(self) -> None:
        assert _translate_problem_type("Desconhecido") == "Desconhecido"

    def test_none_returns_none(self) -> None:
        assert _translate_problem_type(None) is None


# ---------------------------------------------------------------------------
# _translate_description
# ---------------------------------------------------------------------------


class TestTranslateDescription:
    """Tests for _translate_description."""

    def test_basic_translation(self) -> None:
        result = _translate_description("Rajadas até 90 km/h")
        assert "Gusts" in result
        assert "up to" in result

    def test_none_returns_none(self) -> None:
        assert _translate_description(None) is None

    def test_empty_returns_empty(self) -> None:
        assert _translate_description("") == ""


# ---------------------------------------------------------------------------
# fetch_alerts (async, with mocked aiohttp session)
# ---------------------------------------------------------------------------

SAMPLE_HTML = """\
<html><body>
<div class="alerts-wrapper">
  <a class="popover-block alert-CN" data-content="Ondas de noroeste com até 4 metros">
    <div class="alert-container" style="background-color: #ffd712;">
      <span class="warning-title">Agitação Marítima</span>
      <small>Em vigor de, 2025-01-15 06:00:00 até 2025-01-16 00:00:00</small>
    </div>
  </a>
  <a class="popover-block alert-CS" data-content="Rajadas até 90 km/h">
    <div class="alert-container" style="background-color: #ff0000;">
      <span class="warning-title">Vento</span>
      <small>Em vigor de, 2025-01-15 09:00:00 até 2025-01-15 21:00:00</small>
    </div>
  </a>
  <a class="popover-block alert-PS" data-content="">
    <div class="alert-container" style="background-color: #00b050;">
      <span class="warning-title"></span>
      <small></small>
    </div>
  </a>
</div>
</body></html>
"""


def _mock_session(html: str) -> MagicMock:
    """Create a mock aiohttp session that returns the given HTML."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.text = AsyncMock(return_value=html)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=mock_ctx)
    return session


class TestFetchAlerts:
    """Tests for fetch_alerts with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_parses_alerts(self) -> None:
        session = _mock_session(SAMPLE_HTML)
        result = await fetch_alerts(session, "https://example.com")

        assert len(result["CN"]) == 1
        assert result["CN"][0]["alert_type"] == "yellow"
        assert result["CN"][0]["problem_type"] == "Rough Seas"

        assert len(result["CS"]) == 1
        assert result["CS"][0]["alert_type"] == "red"
        assert result["CS"][0]["problem_type"] == "Wind"

        assert len(result["PS"]) == 1
        assert result["PS"][0]["alert_type"] == "green"

        assert result["RM"] == []

    @pytest.mark.asyncio
    async def test_all_regions_present(self) -> None:
        session = _mock_session(SAMPLE_HTML)
        result = await fetch_alerts(session, "https://example.com")
        for code in REGIONS:
            assert code in result

    @pytest.mark.asyncio
    async def test_empty_alerts_wrapper(self) -> None:
        html = '<html><body><div class="alerts-wrapper"></div></body></html>'
        session = _mock_session(html)
        result = await fetch_alerts(session, "https://example.com")
        for alerts in result.values():
            assert alerts == []

    @pytest.mark.asyncio
    async def test_no_alerts_wrapper(self) -> None:
        html = "<html><body><p>No alerts today.</p></body></html>"
        session = _mock_session(html)
        result = await fetch_alerts(session, "https://example.com")
        for alerts in result.values():
            assert alerts == []

    @pytest.mark.asyncio
    async def test_date_parsing_in_alerts(self) -> None:
        session = _mock_session(SAMPLE_HTML)
        result = await fetch_alerts(session, "https://example.com")
        cn_alert = result["CN"][0]
        assert cn_alert["start_date"] is not None
        assert cn_alert["end_date"] is not None
        assert "2025-01-15" in cn_alert["start_date"]

    @pytest.mark.asyncio
    async def test_description_translation(self) -> None:
        session = _mock_session(SAMPLE_HTML)
        result = await fetch_alerts(session, "https://example.com")
        cn_alert = result["CN"][0]
        assert cn_alert["description"] is not None

    @pytest.mark.asyncio
    async def test_network_error_propagates(self) -> None:
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=Exception("Connection error")
        )
        mock_response.text = AsyncMock(return_value="")

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock()
        session.get = MagicMock(return_value=mock_ctx)

        with pytest.raises(Exception, match="Connection error"):
            await fetch_alerts(session, "https://example.com")
