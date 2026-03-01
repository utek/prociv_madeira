"""Alert fetching and parsing for ProCiv Madeira."""

from __future__ import annotations

import colorsys
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

MADEIRA_TZ = ZoneInfo("Atlantic/Madeira")

URL = "https://www.procivmadeira.pt/pt/12-avisos.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# All known Madeira regions: code -> full name (English)
REGIONS: dict[str, str] = {
    "CN": "North Coast",
    "CS": "South Coast",
    "PS": "Porto Santo",
    "RM": "Mountainous Regions",
}

# Portuguese problem-type labels as they appear on the website -> English
PROBLEM_TYPE_TRANSLATIONS: dict[str, str] = {
    "Agitação Marítima": "Rough Seas",
    "Chuva": "Rain",
    "Frio": "Cold",
    "Gelo": "Ice",
    "Granizo": "Hail",
    "Nevoeiro": "Fog",
    "Neve": "Snow",
    "Precipitação": "Precipitation",
    "Tempestade": "Storm",
    "Trovoada": "Thunderstorm",
    "Vento": "Wind",
    "Calor": "Heat",
}

# Vocabulary for translating free-form Portuguese description text
_PT_EN: list[tuple[str, str]] = [
    # Directions
    (r"\bnoroeste\b", "northwest"),
    (r"\bnordeste\b", "northeast"),
    (r"\bsudoeste\b", "southwest"),
    (r"\bsudeste\b", "southeast"),
    (r"\bnorte\b", "north"),
    (r"\bsul\b", "south"),
    (r"\beste\b", "east"),
    (r"\boeste\b", "west"),
    # Units / measurements
    (r"\bmetros\b", "metres"),
    (r"\bmetro\b", "metre"),
    (r"\bmilímetros\b", "millimetres"),
    (r"\bmilímetro\b", "millimetre"),
    (r"\bmm\b", "mm"),
    (r"\bkm/h\b", "km/h"),
    # Common phrases
    (r"\bOndas de\b", "Waves from"),
    (r"\bcom\b", "of"),
    (r"\baté\b", "up to"),
    (r"\bRajadas\b", "Gusts"),
    (r"\brajadas\b", "gusts"),
    (r"\bnos extremos leste e oeste\b", "on the eastern and western tips"),
    (r"\bnos pontos mais elevados\b", "at the highest points"),
    (r"\bPrecipitação\b", "Precipitation"),
    (r"\bprecipitação\b", "precipitation"),
    (r"\bintensa\b", "intense"),
    (r"\bforte\b", "heavy"),
    (r"\bfraca\b", "light"),
    (r"\bpor vezes\b", "at times"),
    (r"\bNeve\b", "Snow"),
    (r"\bneve\b", "snow"),
    (r"\bNevoeiro\b", "Fog"),
    (r"\bnevoeiro\b", "fog"),
    (r"\bdenso\b", "dense"),
    (r"\bvisibilidade\b", "visibility"),
    (r"\breduzida\b", "reduced"),
    (r"\btrovoada\b", "thunderstorm"),
    (r"\bTrovoada\b", "Thunderstorm"),
    (r"\bgranizo\b", "hail"),
    (r"\bGranizo\b", "Hail"),
    (r"\bgelo\b", "ice"),
    (r"\bGelo\b", "Ice"),
    (r"\bnegra\b", "black"),
    (r"\bCalor\b", "Heat"),
    (r"\bcalor\b", "heat"),
    (r"\bFrio\b", "Cold"),
    (r"\bfrio\b", "cold"),
    (r"\btemperatura\b", "temperature"),
    (r"\btemperaturas\b", "temperatures"),
    (r"\bmáxima\b", "maximum"),
    (r"\bmínima\b", "minimum"),
    (r"\bacima de\b", "above"),
    (r"\babaixo de\b", "below"),
    (r"\bvento\b", "wind"),
    (r"\bVento\b", "Wind"),
    (r"\bsoprar\b", "blowing"),
    (r"\bsopros\b", "gusts"),
    (r"\bfortes\b", "strong"),
    (r"\bmoderados\b", "moderate"),
    (r"\bfraco\b", "light"),
    (r"\bpersistente\b", "persistent"),
    (r"\bpossível\b", "possible"),
    (r"\bpossíveis\b", "possible"),
    (r"\bexpectável\b", "expected"),
    (r"\bprevista\b", "forecast"),
    (r"\bdurante\b", "during"),
    (r"\ba tarde\b", "the afternoon"),
    (r"\ba manhã\b", "the morning"),
    (r"\ba noite\b", "the night"),
    (r"\bao longo do dia\b", "throughout the day"),
    (r"\bna costa\b", "on the coast"),
    (r"\bno interior\b", "inland"),
    (r"\bno litoral\b", "on the coast"),
    (r"\bnas zonas altas\b", "in the high areas"),
    (r"\bnas zonas baixas\b", "in the low areas"),
    (r"\bisoladas\b", "isolated"),
    (r"\bisolado\b", "isolated"),
    (r"\bocasional\b", "occasional"),
    (r"\bocasionais\b", "occasional"),
]

COLOR_TO_ALERT_TYPE = {
    "#00b050": "GREEN",
    "#ffd712": "YELLOW",
    "#ffff00": "YELLOW",
    "#ffa500": "ORANGE",
    "#ff8c00": "ORANGE",
    "#ed7d31": "ORANGE",
    "#ff0000": "RED",
    "#cc0000": "RED",
    "#c00000": "RED",
}

# Severity ordering — higher number is more severe
ALERT_SEVERITY: dict[str, int] = {
    "GREEN": 0,
    "YELLOW": 1,
    "ORANGE": 2,
    "RED": 3,
}

# Canonical display color for each alert level (usable as CSS background-color)
ALERT_TYPE_COLOR: dict[str, str] = {
    "GREEN": "#00b050",
    "YELLOW": "#ffd712",
    "ORANGE": "#ffa500",
    "RED": "#ff0000",
}


def _translate_problem_type(pt: str | None) -> str | None:
    """Return the English label for a Portuguese problem-type string."""
    if pt is None:
        return None
    return PROBLEM_TYPE_TRANSLATIONS.get(pt, pt)


def _translate_description(pt: str | None) -> str | None:
    """Best-effort word/phrase substitution of a Portuguese description into English."""
    if not pt:
        return pt
    text = pt
    for pattern, replacement in _PT_EN:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _classify_by_hue(hex_color: str) -> str:
    """Map an unrecognised hex color to an alert level via HSV hue.

    Used as a fallback when the website introduces a shade not in
    COLOR_TO_ALERT_TYPE, so arbitrary orange variants still map to ORANGE
    rather than silently collapsing to a severity of 0.
    """
    try:
        h = hex_color.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
        hue, sat, _val = colorsys.rgb_to_hsv(r, g, b)
        if sat < 0.25:  # achromatic / nearly grey → not a warning
            return "GREEN"
        hue_deg = hue * 360
        if hue_deg < 20 or hue_deg >= 340:
            return "RED"
        if hue_deg < 45:
            return "ORANGE"
        if hue_deg < 75:
            return "YELLOW"
        return "GREEN"
    except Exception:  # noqa: BLE001
        return "GREEN"


def _color_to_alert_type(style: str) -> str | None:
    match = re.search(r"background-color\s*:\s*(#[0-9a-fA-F]{3,6})", style)
    if not match:
        return None
    hex_color = match.group(1).lower()
    return COLOR_TO_ALERT_TYPE.get(hex_color) or _classify_by_hue(hex_color)


def _parse_datetime(raw: str) -> datetime | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=MADEIRA_TZ)
        except ValueError:
            continue
    return None


def _parse_date_range(text: str) -> tuple[datetime | None, datetime | None]:
    pattern = (
        r"Em vigor de\s*,?\s*"
        r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)"
        r"\s+até\s+"
        r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?)"
    )
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return _parse_datetime(match.group(1)), _parse_datetime(match.group(2))
    return None, None


def fetch_alerts(url: str = URL) -> dict[str, list[dict]]:
    """
    Return all alerts per region keyed by region code (CN, CS, PS, RM).

    Each value is a list of alert dicts sorted by start_date descending
    (newest first).  Each dict contains:
      - region_code, region: identifiers
      - alert_type: "GREEN", "YELLOW", "ORANGE", or "RED"
      - color: canonical colour for that level
      - problem_type, description, start_date, end_date
    """
    result: dict[str, list[dict]] = {code: [] for code in REGIONS}

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    alerts_wrapper = soup.find(class_="alerts-wrapper")
    if not alerts_wrapper:
        return result

    for anchor in alerts_wrapper.find_all("a", class_="popover-block"):
        # Region code is encoded in the anchor's CSS classes as e.g. "alert-CN"
        region_code = next(
            (
                cls[6:]
                for cls in anchor.get("class", [])
                if cls.startswith("alert-") and cls[6:] in REGIONS
            ),
            None,
        )
        if region_code is None:
            continue

        container = anchor.find(class_="alert-container")
        style = container.get("style", "") if container else ""
        alert_type = _color_to_alert_type(style) or "GREEN"

        warning_tag = anchor.find(class_="warning-title")
        problem_type = warning_tag.get_text(strip=True) if warning_tag else None

        small_tag = anchor.find("small")
        date_text = small_tag.get_text(strip=True) if small_tag else ""
        start_date, end_date = _parse_date_range(date_text)

        result[region_code].append(
            {
                "region_code": region_code,
                "region": REGIONS[region_code],
                "alert_type": alert_type,
                "color": ALERT_TYPE_COLOR.get(alert_type, ALERT_TYPE_COLOR["GREEN"]),
                "problem_type": _translate_problem_type(problem_type),
                "description": _translate_description(
                    anchor.get("data-content") or None
                ),
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            }
        )

    # Sort each region's alerts by start_date descending (newest first).
    # Alerts without a start_date sort to the end.
    for alerts in result.values():
        alerts.sort(key=lambda a: a["start_date"] or "", reverse=True)

    return result
