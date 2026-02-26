"""Custom types for prociv_madeira."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .coordinator import ProcivMadeiraDataUpdateCoordinator


type ProcivMadeiraConfigEntry = ConfigEntry[ProcivMadeiraData]


@dataclass
class ProcivMadeiraData:
    """Data for the ProCiv Madeira integration."""

    coordinator: ProcivMadeiraDataUpdateCoordinator
    integration: Integration
