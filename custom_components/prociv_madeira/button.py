"""Button platform for prociv_madeira."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory

from .coordinator import ProcivMadeiraDataUpdateCoordinator
from .entity import ProcivMadeiraEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import ProcivMadeiraConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: ProcivMadeiraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    async_add_entities([ProcivMadeiraRefreshButton(entry.runtime_data.coordinator)])


class ProcivMadeiraRefreshButton(ProcivMadeiraEntity, ButtonEntity):
    """Button that triggers an immediate data refresh from procivmadeira.pt."""

    _attr_name = "Refresh Data"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ProcivMadeiraDataUpdateCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_refresh"
        self.entity_id = "button.prociv_madeira_refresh_data"

    async def async_press(self) -> None:
        """Force an immediate data fetch, bypassing the normal poll interval."""
        await self.coordinator.async_refresh()
