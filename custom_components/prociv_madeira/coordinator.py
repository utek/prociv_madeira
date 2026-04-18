"""DataUpdateCoordinator for prociv_madeira."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .alerts import fetch_alerts
from .const import LOGGER

if TYPE_CHECKING:
    from .data import ProcivMadeiraConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class ProcivMadeiraDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from procivmadeira.pt."""

    config_entry: ProcivMadeiraConfigEntry
    last_fetch: datetime | None = None
    url: str

    async def _async_update_data(self) -> Any:
        """Fetch live alert data from procivmadeira.pt."""
        try:
            session = async_get_clientsession(self.hass)
            result = await fetch_alerts(session, self.url)
            self.last_fetch = dt_util.utcnow()
            return result
        except Exception as exception:
            LOGGER.warning("Failed to fetch ProCiv Madeira data: %s", exception)
            raise UpdateFailed(exception) from exception
