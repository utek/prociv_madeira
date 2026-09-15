"""Tests for alerts.py — IPMA warnings parsing and active/upcoming logic."""

from __future__ import annotations

import logging
from datetime import UTC
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import aiohttp
import pytest

from custom_components.prociv_madeira import alerts

from .common import HEAT_TEXT
from .common import ipma_baseline
from .common import ipma_feed
from .common import ipma_row

NO_ALERTS = {"CN": [], "CS": [], "PS": [], "RM": []}


def _alert(level: str, start: str, end: str) -> dict[str, str]:
    return {
        "alert_type": level,
        "start_date": f"{start}+00:00",
        "end_date": f"{end}+00:00",
    }


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _levels(result: alerts.IpmaWarnings) -> dict[str, list[str]]:
    return {
        code: [a["alert_type"] for a in items] for code, items in result.alerts.items()
    }


# ---------------------------------------------------------------------------
# parse_warnings
# ---------------------------------------------------------------------------


class TestParseWarnings:
    """Tests for parse_warnings."""

    def test_green_baseline_rows_are_dropped(self) -> None:
        result = alerts.parse_warnings(ipma_feed())
        assert _levels(result) == {
            "CN": ["yellow"],
            "CS": ["orange"],
            "PS": ["yellow"],
            "RM": ["orange"],
        }
        assert result.invalid == {}

    def test_alert_fields(self) -> None:
        assert alerts.parse_warnings(ipma_feed()).alerts["CS"] == [
            {
                "region_code": "CS",
                "region": "South Coast",
                "alert_type": "orange",
                "color": "#ffa500",
                "problem_type": "Heat",
                "description": HEAT_TEXT,
                "start_date": "2026-09-14T10:50:00+00:00",
                "end_date": "2026-09-15T18:00:00+00:00",
            }
        ]

    @pytest.mark.parametrize(
        ("hazard", "english"),
        [
            ("Agitação Marítima", "Rough Seas"),
            ("Nevoeiro", "Fog"),
            ("Tempo Quente", "Heat"),
            ("Tempo Frio", "Cold"),
            ("Precipitação", "Precipitation"),
            ("Neve", "Snow"),
            ("Trovoada", "Thunderstorm"),
            ("Vento", "Wind"),
        ],
    )
    def test_hazard_names_are_translated(self, hazard: str, english: str) -> None:
        rows = [*ipma_baseline(), ipma_row("MCN", hazard, "yellow")]
        assert alerts.parse_warnings(rows).alerts["CN"][0]["problem_type"] == english

    def test_unknown_hazard_name_passes_through(self) -> None:
        rows = [*ipma_baseline(), ipma_row("MCN", "Poeiras", "yellow")]
        assert alerts.parse_warnings(rows).alerts["CN"][0]["problem_type"] == "Poeiras"

    def test_empty_text_gives_no_description(self) -> None:
        rows = [*ipma_baseline(), ipma_row("MCN", "Vento", "yellow")]
        assert alerts.parse_warnings(rows).alerts["CN"][0]["description"] is None

    @pytest.mark.parametrize("payload", [{}, None, "[]"])
    def test_non_list_payload_raises(self, payload: object) -> None:
        with pytest.raises(alerts.IpmaDataError):
            alerts.parse_warnings(payload)

    def test_area_with_only_green_rows_has_no_alerts(self) -> None:
        result = alerts.parse_warnings(ipma_baseline())
        assert result.alerts == NO_ALERTS
        assert result.invalid == {}

    def test_rows_outside_madeira_are_ignored(self) -> None:
        rows = [*ipma_baseline(), ipma_row("LSB", "Vento", "red", "garbage", "garbage")]
        assert alerts.parse_warnings(rows).alerts == NO_ALERTS

    @pytest.mark.parametrize("row", ["junk", None, {"idAreaAviso": ["MCN"]}])
    def test_rows_that_are_not_madeira_warnings_are_ignored(self, row: object) -> None:
        result = alerts.parse_warnings([*ipma_baseline(), row])
        assert result.alerts == NO_ALERTS
        assert result.invalid == {}

    @pytest.mark.parametrize(
        "changes",
        [
            {"startTime": "garbage"},
            {"startTime": None},
            {"endTime": 1789999999},
            {"awarenessLevelID": "Red"},
            {"awarenessLevelID": "purple"},
            {"awarenessLevelID": ["red"]},
            {"awarenessTypeName": ["Vento"]},
            {"text": {"pt": "Rajadas"}},
            {"startTime": "2026-09-15T00:00:00", "endTime": "2026-09-14T00:00:00"},
        ],
        ids=[
            "bad-time",
            "missing-time",
            "number-time",
            "capitalised-level",
            "unknown-level",
            "list-level",
            "list-hazard",
            "dict-text",
            "ends-before-start",
        ],
    )
    def test_broken_row_makes_only_its_region_invalid(
        self, changes: dict[str, Any], caplog: pytest.LogCaptureFixture
    ) -> None:
        broken = {**ipma_row("MCS", "Vento", "red"), **changes}
        with caplog.at_level(logging.DEBUG):
            result = alerts.parse_warnings([*ipma_feed(), broken])

        assert list(result.invalid) == ["CS"]
        assert result.invalid["CS"].startswith("MCS: ")
        assert _levels(result) == {
            "CN": ["yellow"],
            "CS": [],
            "PS": ["yellow"],
            "RM": ["orange"],
        }
        # The coordinator reports invalid regions once, not every poll.
        assert caplog.records == []

    def test_green_row_with_a_broken_time_is_harmless(self) -> None:
        rows = [*ipma_baseline(), ipma_row("MCN", "Vento", "green", "garbage")]
        assert alerts.parse_warnings(rows).invalid == {}

    def test_missing_madeira_area_makes_its_region_invalid(self) -> None:
        rows = [row for row in ipma_feed() if row["idAreaAviso"] != "MPS"]
        result = alerts.parse_warnings(rows)
        assert list(result.invalid) == ["PS"]
        assert result.invalid["PS"].startswith("MPS: ")
        assert result.alerts["PS"] == []
        assert result.alerts["CS"] != []

    def test_renamed_level_field_is_not_all_clear(self) -> None:
        rows = [
            {
                ("level" if key == "awarenessLevelID" else key): value
                for key, value in row.items()
            }
            for row in ipma_feed()
        ]
        with pytest.raises(alerts.IpmaDataError, match="MCN: .*MCS: .*MPS: .*MRM: "):
            alerts.parse_warnings(rows)

    def test_feed_without_madeira_raises(self) -> None:
        with pytest.raises(alerts.IpmaDataError):
            alerts.parse_warnings([ipma_row("LSB", "Vento", "red")])

    @pytest.mark.parametrize(
        "start",
        ["2026-09-14T11:50:00+01:00", "2026-09-14T10:50:00Z"],
    )
    def test_times_with_offset_are_converted_to_utc(self, start: str) -> None:
        rows = [*ipma_baseline(), ipma_row("MCN", "Vento", "yellow", start)]
        result = alerts.parse_warnings(rows)
        assert result.alerts["CN"][0]["start_date"] == "2026-09-14T10:50:00+00:00"

    def test_warning_that_is_never_in_effect_is_skipped(self) -> None:
        row = ipma_row(
            "MCN", "Vento", "red", "2026-09-14T12:00:00", "2026-09-14T12:00:00"
        )
        result = alerts.parse_warnings([*ipma_baseline(), row])
        assert result.alerts["CN"] == []
        assert result.invalid == {}

    def test_alerts_sorted_by_start_then_severity(self) -> None:
        start, later, end = (
            "2026-09-14T10:00:00",
            "2026-09-14T12:00:00",
            "2026-09-14T18:00:00",
        )
        rows = [
            *ipma_baseline(),
            ipma_row("MCN", "Vento", "yellow", later, end),
            ipma_row("MCN", "Nevoeiro", "orange", start, end),
            ipma_row("MCN", "Trovoada", "red", start, end),
        ]
        names = [a["problem_type"] for a in alerts.parse_warnings(rows).alerts["CN"]]
        assert names == ["Thunderstorm", "Fog", "Wind"]


# ---------------------------------------------------------------------------
# split_alerts / highest_alert_type / next_transition
# ---------------------------------------------------------------------------


class TestSplitAlerts:
    """Tests for split_alerts."""

    @pytest.mark.parametrize(
        ("now", "expected"),
        [
            ("2026-09-14T09:59:59", "upcoming"),
            ("2026-09-14T10:00:00", "active"),
            ("2026-09-14T11:59:59", "active"),
            ("2026-09-14T12:00:00", "expired"),
            ("2026-09-14T13:00:00", "expired"),
        ],
    )
    def test_warning_is_active_from_start_until_end(
        self, now: str, expected: str
    ) -> None:
        warning = _alert("red", "2026-09-14T10:00:00", "2026-09-14T12:00:00")
        active, upcoming = alerts.split_alerts([warning], _utc(now))
        found = {"active": active, "upcoming": upcoming}
        if expected == "expired":
            assert found == {"active": [], "upcoming": []}
        else:
            assert found[expected] == [warning]
            assert sum(len(items) for items in found.values()) == 1

    def test_back_to_back_warnings_hand_over_without_overlap(self) -> None:
        yellow = _alert("yellow", "2026-09-14T06:00:00", "2026-09-14T12:00:00")
        orange = _alert("orange", "2026-09-14T12:00:00", "2026-09-14T18:00:00")
        active, upcoming = alerts.split_alerts(
            [yellow, orange], _utc("2026-09-14T12:00:00")
        )
        assert active == [orange]
        assert upcoming == []


class TestHighestAlertType:
    """Tests for highest_alert_type."""

    def test_no_alerts_is_green(self) -> None:
        assert alerts.highest_alert_type([]) == "green"

    def test_most_severe_wins(self) -> None:
        items = [
            {"alert_type": "yellow"},
            {"alert_type": "red"},
            {"alert_type": "orange"},
        ]
        assert alerts.highest_alert_type(items) == "red"


TRANSITION_DATA = {
    "CN": [_alert("yellow", "2026-09-14T10:00:00", "2026-09-14T12:00:00")],
    "CS": [_alert("red", "2026-09-14T11:00:00", "2026-09-14T15:00:00")],
    "PS": [],
    "RM": [],
}


class TestNextTransition:
    """Tests for next_transition."""

    @pytest.mark.parametrize(
        ("now", "expected"),
        [
            ("2026-09-14T09:00:00", "2026-09-14T10:00:00"),
            ("2026-09-14T10:30:00", "2026-09-14T11:00:00"),
            ("2026-09-14T11:00:00", "2026-09-14T12:00:00"),
            ("2026-09-14T15:00:00", None),
        ],
    )
    def test_earliest_boundary_after_now(self, now: str, expected: str | None) -> None:
        result = alerts.next_transition(TRANSITION_DATA, _utc(now))
        assert result == (_utc(expected) if expected else None)

    def test_no_alerts_has_no_transition(self) -> None:
        assert alerts.next_transition(NO_ALERTS, _utc("2026-09-14T09:00:00")) is None


# ---------------------------------------------------------------------------
# fetch_alerts (with a mocked aiohttp session)
# ---------------------------------------------------------------------------


def _mock_session(body: object) -> tuple[MagicMock, AsyncMock]:
    """Create a mock aiohttp session whose response JSON is *body*."""
    response = AsyncMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=body)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=ctx)
    return session, response


class TestFetchAlerts:
    """Tests for fetch_alerts with mocked HTTP responses."""

    async def test_fetches_ipma_feed(self) -> None:
        session, response = _mock_session(ipma_feed())
        result = await alerts.fetch_alerts(session)
        assert session.get.call_args.args[0] == (
            "https://api.ipma.pt/open-data/forecast/warnings/warnings_www.json"
        )
        response.json.assert_awaited_once_with(content_type=None)
        assert result.alerts["CS"][0]["alert_type"] == "orange"

    async def test_http_error_names_the_status(self) -> None:
        session, response = _mock_session(ipma_feed())
        response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            MagicMock(), (), status=503, message="Service Unavailable"
        )
        with pytest.raises(
            alerts.IpmaConnectionError, match=r"^HTTP 503 Service Unavailable$"
        ):
            await alerts.fetch_alerts(session)

    @pytest.mark.parametrize(
        ("error", "message"),
        [
            (aiohttp.ClientError("offline"), "^offline$"),
            (aiohttp.ClientConnectionError(), "^ClientConnectionError$"),
            (TimeoutError(), "^Timed out after 30 seconds$"),
            (aiohttp.ServerTimeoutError(), "^Timed out after 30 seconds$"),
        ],
        ids=["client-error", "no-message", "timeout", "aiohttp-timeout"],
    )
    async def test_connection_errors_have_a_reason(
        self, error: Exception, message: str
    ) -> None:
        session, _ = _mock_session(ipma_feed())
        session.get.return_value.__aenter__.side_effect = error
        with pytest.raises(alerts.IpmaConnectionError, match=message):
            await alerts.fetch_alerts(session)

    async def test_invalid_json_raises_data_error(self) -> None:
        session, response = _mock_session(None)
        response.json.side_effect = ValueError("Expecting value")
        with pytest.raises(alerts.IpmaDataError, match="Expecting value"):
            await alerts.fetch_alerts(session)

    async def test_non_list_body_raises(self) -> None:
        session, _ = _mock_session({"error": "maintenance"})
        with pytest.raises(alerts.IpmaDataError):
            await alerts.fetch_alerts(session)
