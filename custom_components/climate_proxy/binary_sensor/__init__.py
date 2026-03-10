"""Binary sensor platform for climate_proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN, PARALLEL_UPDATES as PARALLEL_UPDATES
from .proxy_entity import ClimateProxyBinarySensorEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from ..data import ClimateProxyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ClimateProxyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor proxy entities."""
    discovered = entry.runtime_data.discovered_entities.get(Platform.BINARY_SENSOR, [])
    device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
    state_manager = entry.runtime_data.state_manager

    entities = [
        ClimateProxyBinarySensorEntity(entry, underlying_entry, state_manager, device_info)
        for underlying_entry in discovered
    ]
    async_add_entities(entities)
