"""Sensor platform for prociv_madeira."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from .alerts import ALERT_TYPE_COLOR
from .alerts import REGIONS
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
    async_add_entities(
        [
            *[
                ProcivMadeiraSensor(coordinator=coordinator, region_code=code)
                for code in REGIONS
            ],
            ProcivMadeiraLastFetchSensor(coordinator=coordinator),
        ]
    )


# Icon per alert level – GREEN gets a check icon, not an alert icon.
_ALERT_ICONS: dict[str, str] = {
    "GREEN": "mdi:check-circle",
    "YELLOW": "mdi:alert-circle",
    "ORANGE": "mdi:alert",
    "RED": "mdi:alert-octagon",
}


class ProcivMadeiraSensor(ProcivMadeiraEntity, SensorEntity):
    """ProCiv Madeira alert sensor for a single region."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["GREEN", "YELLOW", "ORANGE", "RED"]
    _attr_translation_key = "alert"
    _attr_state_color = True

    def __init__(
        self,
        coordinator: ProcivMadeiraDataUpdateCoordinator,
        region_code: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._region_code = region_code
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{region_code}"
        self._attr_name = REGIONS[region_code]

    @property
    def native_value(self) -> str:
        """Return the alert type as the sensor state (GREEN when no active alert)."""
        data = self.coordinator.data or {}
        return data.get(self._region_code, {}).get("alert_type", "GREEN")

    @property
    def icon(self) -> str:
        """Return an icon that reflects the current alert level."""
        return _ALERT_ICONS.get(self.native_value, "mdi:alert")

    @property
    def entity_color(self) -> str | None:
        """
        Return an HA UI color string matching the alert level.

        Supported on HA 2024.1+; silently unused on older versions.
        """
        return {
            "GREEN": "success",
            "YELLOW": "yellow",
            "ORANGE": "orange",
            "RED": "red",
        }.get(self.native_value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional alert attributes."""
        data = self.coordinator.data or {}
        alert = data.get(self._region_code, {})
        state = self.native_value
        return {
            "region_code": self._region_code,
            "region": alert.get("region"),
            "color": ALERT_TYPE_COLOR.get(state, ALERT_TYPE_COLOR["GREEN"]),
            "alert_type": state,
            "icon": _ALERT_ICONS.get(state, "mdi:alert"),
            "problem_type": alert.get("problem_type"),
            "description": alert.get("description"),
            "start_date": alert.get("start_date"),
            "end_date": alert.get("end_date"),
        }


class ProcivMadeiraLastFetchSensor(ProcivMadeiraEntity, SensorEntity):
    """
    Sensor that records the timestamp of each successful data fetch.

    Each state change appears in the Logbook, which is surfaced as the
    integration's Activity panel in Settings → Devices & Services.
    """

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Last Fetch"
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator: ProcivMadeiraDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_last_fetch"

    @property
    def native_value(self) -> datetime | None:
        """Return the UTC time of the last successful fetch."""
        return self.coordinator.last_fetch
