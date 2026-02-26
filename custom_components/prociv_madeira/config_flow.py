"""Adds config flow for ProCiv Madeira."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import CONF_SCAN_INTERVAL
from .const import DEFAULT_SCAN_INTERVAL
from .const import DOMAIN
from .const import MAX_SCAN_INTERVAL
from .const import MIN_SCAN_INTERVAL

_INTERVAL_SCHEMA = vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL))


class ProcivMadeiraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for ProCiv Madeira."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            return self.async_create_entry(
                title="ProCiv Madeira",
                data={},
                options={CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): _INTERVAL_SCHEMA,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return ProcivMadeiraOptionsFlowHandler()


class ProcivMadeiraOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for ProCiv Madeira."""

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): _INTERVAL_SCHEMA,
                }
            ),
        )
