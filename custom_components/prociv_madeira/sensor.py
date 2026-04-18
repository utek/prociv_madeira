"""Sensor platform for prociv_madeira."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from .alerts import ALERT_SEVERITY
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
            ProcivMadeiraWorstAlertSensor(coordinator=coordinator),
            ProcivMadeiraLastFetchSensor(coordinator=coordinator),
        ]
    )


# Icon per alert level – green gets a check icon, not an alert icon.
_ALERT_ICONS: dict[str, str] = {
    "green": "mdi:check-circle",
    "yellow": "mdi:alert-circle",
    "orange": "mdi:alert",
    "red": "mdi:alert-octagon",
}


class ProcivMadeiraSensor(ProcivMadeiraEntity, SensorEntity):
    """ProCiv Madeira alert sensor for a single region."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["green", "yellow", "orange", "red"]
    _attr_translation_key = "alert"

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
        """Return the alert type as the sensor state (green when no active alert)."""
        data = self.coordinator.data or {}
        alerts = data.get(self._region_code, [])
        return alerts[0].get("alert_type", "green") if alerts else "green"

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
            "green": "green",
            "yellow": "yellow",
            "orange": "orange",
            "red": "red",
        }.get(self.native_value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional alert attributes."""
        data = self.coordinator.data or {}
        alerts = data.get(self._region_code, [])
        current = alerts[0] if alerts else {}
        state = self.native_value
        return {
            "region_code": self._region_code,
            "region": REGIONS[self._region_code],
            "alert_type": state,
            "color": ALERT_TYPE_COLOR.get(state, ALERT_TYPE_COLOR["green"]),
            "problem_type": current.get("problem_type"),
            "description": current.get("description"),
            "start_date": current.get("start_date"),
            "end_date": current.get("end_date"),
            "alerts": alerts,
        }


class ProcivMadeiraWorstAlertSensor(ProcivMadeiraEntity, SensorEntity):
    """Sensor that reports the highest-severity alert across all regions."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["green", "yellow", "orange", "red"]
    _attr_name = "Worst Alert"
    _attr_translation_key = "alert"

    def __init__(self, coordinator: ProcivMadeiraDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_worst_alert"

    @property
    def native_value(self) -> str:
        """Return the most severe alert type across all regions."""
        data = self.coordinator.data or {}
        return max(
            (
                alert.get("alert_type", "green")
                for alerts in data.values()
                for alert in alerts
            ),
            key=lambda t: ALERT_SEVERITY.get(t, 0),
            default="green",
        )

    @property
    def icon(self) -> str:
        """Return an icon reflecting the worst alert level."""
        return _ALERT_ICONS.get(self.native_value, "mdi:alert")

    @property
    def entity_color(self) -> str | None:
        """Return an HA UI color string matching the worst alert level."""
        return {
            "green": "green",
            "yellow": "yellow",
            "orange": "orange",
            "red": "red",
        }.get(self.native_value)


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
