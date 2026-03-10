"""Climate platform for climate_proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import DOMAIN, INTEGRATION_NAME
from ..state_manager.entity_discovery import get_device_info_for_entity, get_underlying_device_id
from .proxy_entity import ClimateProxyClimateEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from ..data import ClimateProxyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ClimateProxyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate proxy entity from a config entry."""
    state_manager = config_entry.runtime_data.state_manager
    climate_entity_id = config_entry.data["climate_entity_id"]

    manufacturer, model, hw_version, sw_version = get_device_info_for_entity(hass, climate_entity_id)
    underlying_device_id = get_underlying_device_id(hass, climate_entity_id)

    device_info = DeviceInfo(
        identifiers={(DOMAIN, config_entry.entry_id)},
        name=config_entry.data["proxy_name"],
        manufacturer=INTEGRATION_NAME,
        model=f"Proxy for {manufacturer or 'Unknown'} {model or 'device'}",
        hw_version=hw_version,
        sw_version=sw_version,
    )
    if underlying_device_id:
        # Link proxy device to the underlying device in the HA device registry
        device_reg = dr.async_get(hass)
        underlying_device = device_reg.async_get(underlying_device_id)
        if underlying_device:
            # Use the first identifier from the underlying device as via_device
            if underlying_device.identifiers:
                via_id = next(iter(underlying_device.identifiers))
                device_info["via_device"] = via_id

    proxy_entity = ClimateProxyClimateEntity(
        hass=hass,
        config_entry=config_entry,
        state_manager=state_manager,
        device_info=device_info,
    )

    # Register with state manager
    state_manager.climate_proxy_entity = proxy_entity

    async_add_entities([proxy_entity])
