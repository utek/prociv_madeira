"""Binary sensor platform for prociv_madeira."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.util import dt as dt_util

from .alerts import split_alerts
from .entity import ProcivMadeiraEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import ProcivMadeiraDataUpdateCoordinator
    from .data import ProcivMadeiraConfigEntry

# Read-only platform backed by the coordinator.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: ProcivMadeiraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([ProcivMadeiraAnyAlertBinarySensor(coordinator=coordinator)])


class ProcivMadeiraAnyAlertBinarySensor(ProcivMadeiraEntity, BinarySensorEntity):
    """Binary sensor that is ON when any region has a warning in effect."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "any_active_alert"

    def __init__(self, coordinator: ProcivMadeiraDataUpdateCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_any_alert"

    @property
    def available(self) -> bool:
        """Return False when a region without usable data could have a warning."""
        return super().available and (self.is_on or not self.coordinator.data.invalid)

    @property
    def is_on(self) -> bool:
        """Return True if any region has a warning in effect right now."""
        now = dt_util.utcnow()
        return any(
            split_alerts(alerts, now)[0]
            for alerts in self.coordinator.data.alerts.values()
        )
