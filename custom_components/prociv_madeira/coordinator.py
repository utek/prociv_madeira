"""DataUpdateCoordinator for prociv_madeira."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .alerts import fetch_alerts

if TYPE_CHECKING:
    from .data import ProcivMadeiraConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class ProcivMadeiraDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from procivmadeira.pt."""

    config_entry: ProcivMadeiraConfigEntry
    last_fetch: datetime | None = None

    async def _async_update_data(self) -> Any:
        """Fetch live alert data from procivmadeira.pt."""
        try:
            result = await self.hass.async_add_executor_job(fetch_alerts)
            self.last_fetch = dt_util.utcnow()
            return result
        except Exception as exception:
            raise UpdateFailed(exception) from exception
