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
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.frontend import remove_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.loader import async_get_loaded_integration

from .const import CONF_SCAN_INTERVAL
from .const import DEFAULT_SCAN_INTERVAL
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

    Serves the bundled Lovelace card; the config entry adds it to the frontend.
    """
    await hass.http.async_register_static_paths(
        [StaticPathConfig(_CARD_URL, str(_CARD_PATH), cache_headers=False)]
    )
    return True


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProcivMadeiraConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    # Before the first refresh, so dashboards get the card during setup retries.
    _async_add_card(hass)

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = ProcivMadeiraDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        config_entry=entry,
        update_interval=timedelta(minutes=scan_interval),
    )
    entry.runtime_data = ProcivMadeiraData(coordinator=coordinator)

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    # Option changes reload the entry through OptionsFlowWithReload.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
    """Stop loading the card when the integration is deleted."""
    url = _card_url(hass)
    if url in hass.data[DATA_EXTRA_MODULE_URL].urls:
        remove_extra_js_url(hass, url)


async def async_migrate_entry(
    hass: HomeAssistant,
    entry: ProcivMadeiraConfigEntry,
) -> bool:
    """Migrate an entry created by an older version of the integration."""
    # Home Assistant doesn't call this for entries of a newer major version.
    if entry.minor_version < 2:
        # 0.1.x added the card as a dashboard resource and had a URL option.
        await _async_remove_legacy_card_resource(hass)
        options = {key: value for key, value in entry.options.items() if key != "url"}
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)
    return True


# ---------------------------------------------------------------------------
# Bundled Lovelace card
# ---------------------------------------------------------------------------


def _card_url(hass: HomeAssistant) -> str:
    """Return the card URL, versioned so browsers load the new card on upgrade."""
    version = async_get_loaded_integration(hass, DOMAIN).version
    return f"{_CARD_URL}?v={version}"


@callback
def _async_add_card(hass: HomeAssistant) -> None:
    """Load the card on every frontend page, for storage and YAML dashboards."""
    url = _card_url(hass)
    # Adding notifies every connected frontend, so skip reloads and retries.
    if url not in hass.data[DATA_EXTRA_MODULE_URL].urls:
        add_extra_js_url(hass, url)


async def _async_remove_legacy_card_resource(hass: HomeAssistant) -> None:
    """Delete the dashboard resource that 0.1.x created for the card.

    The cleanup is best effort: a failure is logged and never blocks setup.
    """
    try:
        lovelace = hass.data.get(LOVELACE_DATA)
        if lovelace is None or lovelace.resource_mode != "storage":
            return
        resources = lovelace.resources
        # Loads the collection; async_items() is empty until it has been loaded.
        await resources.async_get_info()
        legacy = [
            item
            for item in resources.async_items()
            if item.get("url", "").split("?")[0] == _CARD_URL
        ]
    except Exception:  # noqa: BLE001
        LOGGER.warning(
            "Could not look for the old dashboard resource of the card", exc_info=True
        )
        return

    for item in legacy:
        try:
            await resources.async_delete_item(item["id"])
        except Exception:  # noqa: BLE001
            LOGGER.warning(
                "Could not remove the old dashboard resource %s",
                item["url"],
                exc_info=True,
            )
        else:
            LOGGER.info("Removed the old dashboard resource %s", item["url"])
