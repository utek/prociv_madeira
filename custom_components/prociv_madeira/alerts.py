"""Alert fetching and parsing for ProCiv Madeira (IPMA weather warnings)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

import aiohttp

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Mapping

# IPMA open-data weather warnings (up to 3 days ahead, times in UTC).
URL = "https://api.ipma.pt/open-data/forecast/warnings/warnings_www.json"
FETCH_TIMEOUT = 30  # seconds

# All known Madeira regions: code -> full name (English)
REGIONS: dict[str, str] = {
    "CN": "North Coast",
    "CS": "South Coast",
    "PS": "Porto Santo",
    "RM": "Mountainous Regions",
}

# Region code -> translation key of the region's sensor
REGION_KEYS: dict[str, str] = {
    "CN": "north_coast",
    "CS": "south_coast",
    "PS": "porto_santo",
    "RM": "mountainous_regions",
}

# IPMA warning area -> region code (kept so unique IDs stay stable)
IPMA_AREAS: dict[str, str] = {
    "MCN": "CN",
    "MCS": "CS",
    "MRM": "RM",
    "MPS": "PS",
}

# IPMA hazard names -> English
PROBLEM_TYPE_TRANSLATIONS: dict[str, str] = {
    "Agitação Marítima": "Rough Seas",
    "Nevoeiro": "Fog",
    "Tempo Quente": "Heat",
    "Tempo Frio": "Cold",
    "Precipitação": "Precipitation",
    "Neve": "Snow",
    "Trovoada": "Thunderstorm",
    "Vento": "Wind",
}

# Severity ordering — higher number is more severe
ALERT_SEVERITY: dict[str, int] = {
    "green": 0,
    "yellow": 1,
    "orange": 2,
    "red": 3,
}

# Canonical display color for each alert level (usable as CSS background-color)
ALERT_TYPE_COLOR: dict[str, str] = {
    "green": "#00b050",
    "yellow": "#ffd712",
    "orange": "#ffa500",
    "red": "#ff0000",
}


class IpmaError(Exception):
    """The IPMA warnings feed could not be used."""


class IpmaConnectionError(IpmaError):
    """The IPMA warnings feed could not be reached."""


class IpmaDataError(IpmaError):
    """The IPMA warnings feed does not have the expected shape."""


@dataclass(frozen=True)
class IpmaWarnings:
    """The Madeira warnings of one IPMA feed."""

    # Region code -> non-green warnings; empty for regions in `invalid`.
    alerts: dict[str, list[dict[str, Any]]]
    # Region code -> why IPMA's data for that region can't be used.
    invalid: dict[str, str]


def _parse_time(raw: object) -> datetime:
    """Parse an IPMA timestamp; timestamps without an offset are UTC."""
    if not isinstance(raw, str):
        raise IpmaDataError(f"invalid time {raw!r}")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as err:
        raise IpmaDataError(f"invalid time {raw!r}") from err
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_row(region_code: str, row: dict[str, Any]) -> dict[str, Any] | None:
    """
    Return the warning of one Madeira feed row.

    Returns None for green rows and warnings that are never in effect, and
    raises IpmaDataError when the row can't be read.
    """
    alert_type = row.get("awarenessLevelID")
    if not isinstance(alert_type, str) or alert_type not in ALERT_SEVERITY:
        raise IpmaDataError(f"unknown warning level {alert_type!r}")
    if alert_type == "green":
        return None

    problem_type = row.get("awarenessTypeName")
    if not isinstance(problem_type, str | None):
        raise IpmaDataError(f"invalid hazard {problem_type!r}")
    text = row.get("text")
    if not isinstance(text, str | None):
        raise IpmaDataError(f"invalid description {text!r}")
    start = _parse_time(row.get("startTime"))
    end = _parse_time(row.get("endTime"))
    if end < start:
        raise IpmaDataError(
            f"ends at {end.isoformat()}, before its start at {start.isoformat()}"
        )
    if end == start:
        return None

    return {
        "region_code": region_code,
        "region": REGIONS[region_code],
        "alert_type": alert_type,
        "color": ALERT_TYPE_COLOR[alert_type],
        "problem_type": PROBLEM_TYPE_TRANSLATIONS.get(problem_type, problem_type),
        "description": text or None,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


def parse_warnings(payload: object) -> IpmaWarnings:
    """
    Return the non-green warnings per region code (CN, CS, PS, RM).

    A region with a row that can't be read gets no warnings and is listed in
    `invalid` instead, so a broken warning never looks like all clear. IPMA
    publishes a green row for every area and hazard, so an area missing from
    the feed is invalid too. Raises IpmaDataError when no region can be used.
    Each region's alerts are sorted by start, end, then severity (worst first).
    """
    if not isinstance(payload, list):
        msg = f"Expected a list of warnings, got {type(payload).__name__}"
        raise IpmaDataError(msg)

    alerts: dict[str, list[dict[str, Any]]] = {code: [] for code in REGIONS}
    invalid: dict[str, str] = {}
    seen: set[str] = set()
    for row in payload:
        if not isinstance(row, dict):
            continue
        area = row.get("idAreaAviso")
        if not isinstance(area, str) or area not in IPMA_AREAS:
            continue
        region_code = IPMA_AREAS[area]
        seen.add(region_code)
        if region_code in invalid:
            continue
        try:
            alert = _parse_row(region_code, row)
        except IpmaDataError as err:
            invalid[region_code] = f"{area}: {err}"
            alerts[region_code] = []
            continue
        if alert is not None:
            alerts[region_code].append(alert)

    for area, region_code in IPMA_AREAS.items():
        if region_code not in seen:
            invalid[region_code] = f"{area}: no rows in the IPMA feed"
    if invalid.keys() == REGIONS.keys():
        raise IpmaDataError("; ".join(invalid[code] for code in REGIONS))

    for region_alerts in alerts.values():
        region_alerts.sort(
            key=lambda a: (
                a["start_date"],
                a["end_date"],
                -ALERT_SEVERITY[a["alert_type"]],
                a["problem_type"] or "",
            )
        )
    return IpmaWarnings(alerts=alerts, invalid=invalid)


async def fetch_alerts(session: aiohttp.ClientSession) -> IpmaWarnings:
    """
    Fetch the IPMA warnings feed and return parse_warnings() of it.

    Raises IpmaConnectionError when the feed can't be reached and IpmaDataError
    when it doesn't contain usable warnings.
    """
    timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT)
    try:
        async with session.get(URL, timeout=timeout) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)
    # aiohttp's timeout errors are also ClientErrors, so this comes first.
    except TimeoutError as err:
        msg = f"Timed out after {FETCH_TIMEOUT} seconds"
        raise IpmaConnectionError(msg) from err
    except aiohttp.ClientResponseError as err:
        msg = f"HTTP {err.status} {err.message}".rstrip()
        raise IpmaConnectionError(msg) from err
    except aiohttp.ClientError as err:
        raise IpmaConnectionError(str(err) or type(err).__name__) from err
    except ValueError as err:
        raise IpmaDataError(f"Not valid JSON: {err}") from err
    return parse_warnings(payload)


def split_alerts(
    alerts: list[dict[str, Any]], now: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split alerts into (in effect at *now*, not started yet); drop expired ones."""
    active: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    for alert in alerts:
        if now < datetime.fromisoformat(alert["start_date"]):
            upcoming.append(alert)
        elif now < datetime.fromisoformat(alert["end_date"]):
            active.append(alert)
    return active, upcoming


def highest_alert_type(alerts: Iterable[dict[str, Any]]) -> str:
    """Return the most severe alert level, or green when there are no alerts."""
    return max(
        (alert["alert_type"] for alert in alerts),
        key=ALERT_SEVERITY.__getitem__,
        default="green",
    )


def next_transition(
    alerts: Mapping[str, list[dict[str, Any]]], now: datetime
) -> datetime | None:
    """Return the first alert start or end after *now*, when a state can change."""
    times = (
        datetime.fromisoformat(alert[key])
        for region_alerts in alerts.values()
        for alert in region_alerts
        for key in ("start_date", "end_date")
    )
    return min((time for time in times if time > now), default=None)
