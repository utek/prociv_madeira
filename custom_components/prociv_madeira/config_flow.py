"""Adds config flow for ProCiv Madeira."""

from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


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
            return self.async_create_entry(title="ProCiv Madeira", data={})

        return self.async_show_form(step_id="user")
