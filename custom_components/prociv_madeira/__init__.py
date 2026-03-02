"""
Custom integration to integrate ProCiv Madeira alerts with Home Assistant.

For more details about this integration, please refer to
https://github.com/utek/prociv_madeira
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import homeassistant.helpers.config_validation as cv
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.const import Platform
from homeassistant.loader import async_get_loaded_integration

from .const import CONF_SCAN_INTERVAL
from .const import CONF_URL
from .const import DEFAULT_SCAN_INTERVAL
from .const import DEFAULT_URL
from .const import DOMAIN
from .const import LOGGER
from .coordinator import ProcivMadeiraDataUpdateCoordinator
from .data import ProcivMadeiraData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import ProcivMadeiraConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_CARD_URL = f"/{DOMAIN}/prociv-madeira-weather-card.js"
_CARD_PATH = Path(__file__).parent / "www" / "prociv-madeira-weather-card.js"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the ProCiv Madeira component.

    Registers the bundled Lovelace card as a static HTTP resource and adds it
    to the Lovelace resources list so it appears automatically in dashboards.
    """
    # Serve the card JS from the component's www/ directory.
    await hass.http.async_register_static_paths(
        [StaticPathConfig(_CARD_URL, str(_CARD_PATH), cache_headers=False)]
    )

    # Register the Lovelace resource.  Lovelace storage is not available until
    # HA has fully started, so defer to EVENT_HOMEASSISTANT_STARTED during
    # startup.  When the integration is installed/reloaded at runtime (HA
    # already running), register immediately.
    if hass.is_running:
        await _async_register_lovelace_resource(hass, _CARD_URL)
    else:

        async def _on_ha_started(_event: object) -> None:
            await _async_register_lovelace_resource(hass, _CARD_URL)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_ha_started)

    return True


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProcivMadeiraConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = ProcivMadeiraDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(minutes=scan_interval),
    )
    coordinator.url = entry.options.get(CONF_URL, DEFAULT_URL)
    entry.runtime_data = ProcivMadeiraData(
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ProcivMadeiraConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant,
    entry: ProcivMadeiraConfigEntry,
) -> None:
    """Remove the Lovelace resource when the integration is deleted."""
    await _async_remove_lovelace_resource(hass, _CARD_URL)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ProcivMadeiraConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


# ---------------------------------------------------------------------------
# Lovelace resource helpers
# ---------------------------------------------------------------------------


async def _async_register_lovelace_resource(hass: HomeAssistant, url: str) -> None:
    """Register *url* as a Lovelace module resource (idempotent)."""
    # hass.data["lovelace"] is a LovelaceData dataclass — use attribute access.
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        LOGGER.debug("Lovelace not loaded; skipping resource registration for %s", url)
        return
    resources = getattr(lovelace, "resources", None)
    if resources is None:
        LOGGER.debug("Lovelace resources not available; skipping %s", url)
        return
    # ResourceYAMLCollection (yaml-mode dashboards) has no async_create_item.
    if not hasattr(resources, "async_create_item"):
        LOGGER.debug("Lovelace is in YAML mode; add the resource manually for %s", url)
        return
    try:
        await resources.async_load()
        for item in resources.async_items():
            if item.get("url") == url:
                LOGGER.debug("Lovelace resource already registered: %s", url)
                return
        await resources.async_create_item({"res_type": "module", "url": url})
        LOGGER.info("Registered Lovelace resource: %s", url)
    except Exception as err:  # noqa: BLE001
        LOGGER.warning("Could not register Lovelace resource %s: %s", url, err)


async def _async_remove_lovelace_resource(hass: HomeAssistant, url: str) -> None:
    """Remove the Lovelace resource registration for *url*."""
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        return
    resources = getattr(lovelace, "resources", None)
    if resources is None or not hasattr(resources, "async_delete_item"):
        return
    try:
        await resources.async_load()
        for item in resources.async_items():
            if item.get("url") == url:
                await resources.async_delete_item(item["id"])
                LOGGER.info("Removed Lovelace resource: %s", url)
                return
    except Exception as err:  # noqa: BLE001
        LOGGER.warning("Could not remove Lovelace resource %s: %s", url, err)
