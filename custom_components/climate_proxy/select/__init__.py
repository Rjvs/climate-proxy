"""Select platform for climate_proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN, PARALLEL_UPDATES as PARALLEL_UPDATES
from .proxy_entity import ClimateProxySelectEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from ..data import ClimateProxyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ClimateProxyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select proxy platform from a config entry."""
    discovered = config_entry.runtime_data.discovered_entities.get(Platform.SELECT, [])
    device_info = DeviceInfo(identifiers={(DOMAIN, config_entry.entry_id)})
    state_manager = config_entry.runtime_data.state_manager

    entities: list[ClimateProxySelectEntity] = []
    for entry in discovered:
        entity = ClimateProxySelectEntity(config_entry, entry, state_manager, device_info)
        state_manager.select_proxy_entities[entry.entity_id] = entity
        entities.append(entity)

    async_add_entities(entities)
