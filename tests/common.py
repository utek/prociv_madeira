"""Test data and helpers shared by the ProCiv Madeira tests."""

from __future__ import annotations

from typing import Any

MADEIRA_AREAS = ["MCN", "MCS", "MRM", "MPS"]
HAZARDS = [
    "Agitação Marítima",
    "Neve",
    "Nevoeiro",
    "Precipitação",
    "Tempo Frio",
    "Tempo Quente",
    "Trovoada",
    "Vento",
]
HEAT_TEXT = "Persistência de valores elevados da temperatura máxima."
WINDOW_START = "2026-09-14T10:50:00"
WINDOW_END = "2026-09-17T10:00:00"
HEAT_END = "2026-09-15T18:00:00"


def ipma_row(
    area: str,
    hazard: str,
    level: str,
    start: str = WINDOW_START,
    end: str = WINDOW_END,
    text: str = "",
) -> dict[str, str]:
    """Return one row of the IPMA warnings feed."""
    return {
        "text": text,
        "awarenessTypeName": hazard,
        "idAreaAviso": area,
        "startTime": start,
        "awarenessLevelID": level,
        "endTime": end,
    }


def ipma_baseline() -> list[dict[str, str]]:
    """Return the green rows IPMA publishes for every Madeira area and hazard."""
    return [
        ipma_row(area, hazard, "green") for area in MADEIRA_AREAS for hazard in HAZARDS
    ]


def ipma_feed() -> list[dict[str, str]]:
    """Return the Madeira rows of the IPMA feed as published on 2026-09-14."""
    return [
        *ipma_baseline(),
        ipma_row("MRM", "Tempo Quente", "orange", WINDOW_START, HEAT_END, HEAT_TEXT),
        ipma_row("MCN", "Tempo Quente", "yellow", WINDOW_START, HEAT_END, HEAT_TEXT),
        ipma_row("MPS", "Tempo Quente", "yellow", WINDOW_START, HEAT_END, HEAT_TEXT),
        ipma_row("MCS", "Tempo Quente", "orange", WINDOW_START, HEAT_END, HEAT_TEXT),
        # A broken row for a mainland area must not affect Madeira.
        ipma_row("LSB", "Vento", "red", "garbage", "garbage"),
    ]


class FakeLovelaceResources:
    """In-memory stand-in for Lovelace's resource storage collection.

    Like the real collection, its items are only visible once it is loaded.
    """

    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        """Store *items* as resources that have not been loaded yet."""
        self.loaded = False
        self.stored: list[dict[str, Any]] = list(items or [])

    async def async_get_info(self) -> dict[str, int]:
        """Load the collection and return its size."""
        self.loaded = True
        return {"resources": len(self.stored)}

    def async_items(self) -> list[dict[str, Any]]:
        """Return the resources, or none while the collection is not loaded."""
        return list(self.stored) if self.loaded else []

    async def async_delete_item(self, item_id: str) -> None:
        """Remove a resource."""
        self.stored = [item for item in self.stored if item["id"] != item_id]
