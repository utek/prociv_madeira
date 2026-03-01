"""Binary sensor platform for prociv_madeira."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity

from .entity import ProcivMadeiraEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import ProcivMadeiraDataUpdateCoordinator
    from .data import ProcivMadeiraConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: ProcivMadeiraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([ProcivMadeiraAnyAlertBinarySensor(coordinator=coordinator)])


class ProcivMadeiraAnyAlertBinarySensor(ProcivMadeiraEntity, BinarySensorEntity):
    """Binary sensor that is ON when any region has a non-green alert."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Any Active Alert"

    def __init__(self, coordinator: ProcivMadeiraDataUpdateCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_any_alert"
        self.entity_id = "binary_sensor.prociv_madeira_any_active_alert"

    @property
    def is_on(self) -> bool:
        """Return True if any region has a non-green alert."""
        data = self.coordinator.data or {}
        return any(
            alert.get("alert_type", "GREEN") != "GREEN"
            for alerts in data.values()
            for alert in alerts
        )

    @property
    def icon(self) -> str:
        """Return an icon reflecting whether any alert is active."""
        return "mdi:alert" if self.is_on else "mdi:check-circle"
