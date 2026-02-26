"""DataUpdateCoordinator for prociv_madeira."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from .data import ProcivMadeiraConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class ProcivMadeiraDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the static alerts file."""

    config_entry: ProcivMadeiraConfigEntry

    async def _async_update_data(self) -> Any:
        """Load alert data from the static JSON file."""
        try:
            alerts_path = Path(__file__).parent / "alerts.json"
            return await self.hass.async_add_executor_job(
                lambda: json.loads(alerts_path.read_text(encoding="utf-8"))
            )
        except Exception as exception:
            raise UpdateFailed(exception) from exception
