"""Button platform for prociv_madeira."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN
from .entity import ProcivMadeiraEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import ProcivMadeiraDataUpdateCoordinator
    from .data import ProcivMadeiraConfigEntry

# Presses send requests to IPMA; handle one at a time.
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: ProcivMadeiraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    async_add_entities([ProcivMadeiraRefreshButton(entry.runtime_data.coordinator)])


class ProcivMadeiraRefreshButton(ProcivMadeiraEntity, ButtonEntity):
    """Button that fetches the IPMA warnings now."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "refresh"

    def __init__(self, coordinator: ProcivMadeiraDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_refresh"

    async def async_press(self) -> None:
        """
        Request a fetch; the coordinator combines presses close together.

        Raises when the data could not be fetched, so the press shows an error.
        """
        await self.coordinator.async_request_refresh()
        if self.coordinator.last_update_success:
            return
        err = self.coordinator.last_exception
        if isinstance(err, UpdateFailed) and err.translation_key:
            raise HomeAssistantError(
                translation_domain=err.translation_domain,
                translation_key=err.translation_key,
                translation_placeholders=err.translation_placeholders,
            ) from err
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="refresh_failed",
            translation_placeholders={"error": str(err)},
        ) from err
