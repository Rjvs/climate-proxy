"""Entity discovery utilities for climate_proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr, entity_registry as er

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_registry import RegistryEntry


# Platforms we can proxy
PROXYABLE_PLATFORMS: set[str] = {
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
}


def discover_underlying_entities(
    hass: HomeAssistant,
    climate_entity_id: str,
) -> dict[Platform, list[RegistryEntry]]:
    """Find all entities on the underlying device, grouped by platform.

    Find the HA device that owns the given climate entity and return all
    other entities on that device, grouped by platform.

    Args:
        hass: Home Assistant instance.
        climate_entity_id: Entity ID of the underlying climate entity.

    Returns:
        Dict mapping Platform → list of RegistryEntry for each discovered entity.
        The climate entity itself is excluded (it is handled by the climate platform).
        Returns an empty dict if the entity has no associated device.
    """
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    climate_entry = entity_reg.async_get(climate_entity_id)
    if climate_entry is None or climate_entry.device_id is None:
        return {}

    device = device_reg.async_get(climate_entry.device_id)
    if device is None:
        return {}

    result: dict[Platform, list[RegistryEntry]] = {}

    for entry in er.async_entries_for_device(entity_reg, device.id):
        if entry.entity_id == climate_entity_id:
            continue
        domain = entry.domain
        if domain not in PROXYABLE_PLATFORMS:
            continue
        platform = Platform(domain)
        result.setdefault(platform, []).append(entry)

    return result


def get_device_info_for_entity(
    hass: HomeAssistant,
    climate_entity_id: str,
) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Return (manufacturer, model, hw_version, sw_version) from the underlying device.

    Returns (None, None, None, None) if the entity has no device.
    """
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)

    climate_entry = entity_reg.async_get(climate_entity_id)
    if climate_entry is None or climate_entry.device_id is None:
        return None, None, None, None

    device = device_reg.async_get(climate_entry.device_id)
    if device is None:
        return None, None, None, None

    return device.manufacturer, device.model, device.hw_version, device.sw_version


def get_underlying_device_id(
    hass: HomeAssistant,
    climate_entity_id: str,
) -> str | None:
    """Return the HA device_id of the underlying climate entity's device."""
    entity_reg = er.async_get(hass)
    entry = entity_reg.async_get(climate_entity_id)
    if entry is None:
        return None
    return entry.device_id
