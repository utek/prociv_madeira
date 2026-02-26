"""Sensor platform for prociv_madeira."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity

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
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator
    alerts = coordinator.data or []
    async_add_entities(
        ProcivMadeiraSensor(
            coordinator=coordinator,
            alert_index=idx,
        )
        for idx, _ in enumerate(alerts)
    )


class ProcivMadeiraSensor(ProcivMadeiraEntity, SensorEntity):
    """ProCiv Madeira alert sensor."""

    def __init__(
        self,
        coordinator: ProcivMadeiraDataUpdateCoordinator,
        alert_index: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._alert_index = alert_index
        alert = coordinator.data[alert_index]
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{alert_index}"
        )
        self._attr_name = f"{alert['region']} - {alert['problem_type']}"
        self._attr_icon = "mdi:alert"

    @property
    def native_value(self) -> str | None:
        """Return the alert type as the sensor state."""
        alerts = self.coordinator.data or []
        if self._alert_index < len(alerts):
            return alerts[self._alert_index].get("alert_type")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional alert attributes."""
        alerts = self.coordinator.data or []
        if self._alert_index < len(alerts):
            alert = alerts[self._alert_index]
            return {
                "region": alert.get("region"),
                "problem_type": alert.get("problem_type"),
                "description": alert.get("description"),
                "start_date": alert.get("start_date"),
                "end_date": alert.get("end_date"),
            }
        return {}
