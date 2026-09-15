"""Sensor platform for prociv_madeira."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util

from .alerts import ALERT_SEVERITY
from .alerts import ALERT_TYPE_COLOR
from .alerts import REGION_KEYS
from .alerts import REGIONS
from .alerts import highest_alert_type
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


class ProcivMadeiraSensor(ProcivMadeiraEntity, SensorEntity):
    """ProCiv Madeira alert sensor for a single region."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["green", "yellow", "orange", "red"]
    # The alert lists change with every bulletin; keep them out of history.
    _unrecorded_attributes = frozenset({"alerts", "upcoming_alerts"})

    def __init__(
        self,
        coordinator: ProcivMadeiraDataUpdateCoordinator,
        region_code: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._region_code = region_code
        self._attr_translation_key = REGION_KEYS[region_code]
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{region_code}"

    @property
    def available(self) -> bool:
        """Return False while IPMA's data for this region can't be used."""
        return (
            super().available and self._region_code not in self.coordinator.data.invalid
        )

    def _split_alerts(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return this region's (in effect now, not started yet) alerts."""
        return split_alerts(
            self.coordinator.data.alerts[self._region_code], dt_util.utcnow()
        )

    @property
    def native_value(self) -> str:
        """Return the most severe alert in effect (green when there is none)."""
        active, _upcoming = self._split_alerts()
        return highest_alert_type(active)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional alert attributes."""
        active, upcoming = self._split_alerts()
        current = max(
            active, key=lambda alert: ALERT_SEVERITY[alert["alert_type"]], default={}
        )
        state = current.get("alert_type", "green")
        return {
            "region_code": self._region_code,
            "region": REGIONS[self._region_code],
            "alert_type": state,
            "color": ALERT_TYPE_COLOR.get(state, ALERT_TYPE_COLOR["green"]),
            "problem_type": current.get("problem_type"),
            "description": current.get("description"),
            "start_date": current.get("start_date"),
            "end_date": current.get("end_date"),
            "alerts": active,
            "upcoming_alerts": upcoming,
        }


class ProcivMadeiraWorstAlertSensor(ProcivMadeiraEntity, SensorEntity):
    """Sensor that reports the highest-severity alert across all regions."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["green", "yellow", "orange", "red"]
    _attr_translation_key = "worst_alert"

    def __init__(self, coordinator: ProcivMadeiraDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_worst_alert"

    @property
    def available(self) -> bool:
        """Return False when a region without usable data could be worse."""
        return super().available and (
            not self.coordinator.data.invalid or self.native_value == "red"
        )

    @property
    def native_value(self) -> str:
        """Return the most severe alert in effect across all regions."""
        now = dt_util.utcnow()
        return highest_alert_type(
            alert
            for alerts in self.coordinator.data.alerts.values()
            for alert in split_alerts(alerts, now)[0]
        )


class ProcivMadeiraLastFetchSensor(ProcivMadeiraEntity, SensorEntity):
    """Sensor with the time of the last successful fetch from IPMA."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_fetch"

    def __init__(self, coordinator: ProcivMadeiraDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_last_fetch"

    @property
    def available(self) -> bool:
        """Stay available while IPMA can't be reached, to show the last success."""
        return self.coordinator.last_update_success_time is not None

    @property
    def native_value(self) -> datetime | None:
        """Return the UTC time of the last successful fetch."""
        return self.coordinator.last_update_success_time
