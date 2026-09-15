"""Adds config flow for ProCiv Madeira."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .alerts import IpmaConnectionError
from .alerts import IpmaDataError
from .alerts import fetch_alerts
from .const import CONF_SCAN_INTERVAL
from .const import DEFAULT_SCAN_INTERVAL
from .const import DOMAIN
from .const import LOGGER
from .const import MAX_SCAN_INTERVAL
from .const import MIN_SCAN_INTERVAL

_INTERVAL_SCHEMA = vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL))


def _options_schema(scan_interval: int) -> vol.Schema:
    return vol.Schema(
        {vol.Required(CONF_SCAN_INTERVAL, default=scan_interval): _INTERVAL_SCHEMA}
    )


class ProcivMadeiraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for ProCiv Madeira (single instance, see manifest.json)."""

    VERSION = 1
    # 2: the card is no longer a dashboard resource and the URL option is gone.
    MINOR_VERSION = 2

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user; check that IPMA can be read."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            try:
                await fetch_alerts(async_get_clientsession(self.hass))
            except IpmaConnectionError as err:
                errors["base"] = "cannot_connect"
                placeholders["error"] = str(err)
            except IpmaDataError as err:
                errors["base"] = "invalid_data"
                placeholders["error"] = str(err)
            except Exception:
                LOGGER.exception("Unexpected error while checking the IPMA feed")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title="ProCiv Madeira",
                    data={},
                    options={CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _options_schema(DEFAULT_SCAN_INTERVAL), user_input
            ),
            errors=errors,
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return ProcivMadeiraOptionsFlowHandler()


class ProcivMadeiraOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Options flow for ProCiv Madeira; changed options reload the entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(current_interval)
        )
