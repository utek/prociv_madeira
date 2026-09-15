"""DataUpdateCoordinator for prociv_madeira."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .alerts import REGIONS
from .alerts import IpmaConnectionError
from .alerts import IpmaDataError
from .alerts import IpmaWarnings
from .alerts import fetch_alerts
from .alerts import next_transition
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE

    from .data import ProcivMadeiraConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class ProcivMadeiraDataUpdateCoordinator(TimestampDataUpdateCoordinator[IpmaWarnings]):
    """Class to manage fetching weather warnings from IPMA."""

    config_entry: ProcivMadeiraConfigEntry
    _unsub_transition: CALLBACK_TYPE | None = None
    _stopped = False

    async def _async_update_data(self) -> IpmaWarnings:
        """Fetch live warnings from the IPMA feed."""
        session = async_get_clientsession(self.hass)
        try:
            result = await fetch_alerts(session)
        except IpmaConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err
        except IpmaDataError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_data",
                translation_placeholders={"error": str(err)},
            ) from err
        self._log_invalid_regions(result)
        # self.data is only assigned after this returns, so schedule from result.
        self._schedule_transition(result)
        return result

    def _log_invalid_regions(self, result: IpmaWarnings) -> None:
        """Log when a region's data becomes unusable and when it recovers."""
        previous = self.data.invalid if self.data else {}
        for code, reason in result.invalid.items():
            if code not in previous:
                self.logger.warning(
                    "IPMA data for %s can't be used, so its sensor is unavailable: %s",
                    REGIONS[code],
                    reason,
                )
        for code in previous:
            if code not in result.invalid:
                self.logger.info("IPMA data for %s can be used again", REGIONS[code])

    @callback
    def _schedule_transition(self, data: IpmaWarnings) -> None:
        """Update entity states when the next warning starts or ends."""
        self._cancel_transition()
        # A fetch that was already running can finish after shutdown.
        if self._stopped:
            return
        when = next_transition(data.alerts, dt_util.utcnow())
        if when is not None:
            self._unsub_transition = async_track_point_in_utc_time(
                self.hass, self._handle_transition, when
            )

    @callback
    def _handle_transition(self, _now: datetime) -> None:
        """Push the new states and wait for the following start or end."""
        self._unsub_transition = None
        self.async_update_listeners()
        self._schedule_transition(self.data)

    @callback
    def _cancel_transition(self) -> None:
        if self._unsub_transition is not None:
            self._unsub_transition()
            self._unsub_transition = None

    async def async_shutdown(self) -> None:
        """Cancel the pending state update, then shut down."""
        self._stopped = True
        self._cancel_transition()
        await super().async_shutdown()
