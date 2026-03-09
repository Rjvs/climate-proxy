"""Diagnostics support for climate_proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_SENSOR_ENTITY_ID

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import ClimateProxyConfigEntry

# No sensitive data in a local integration, but keep pattern for extensibility
TO_REDACT: set[str] = set()


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ClimateProxyConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    state_manager = entry.runtime_data.state_manager
    integration = entry.runtime_data.integration
    discovered = entry.runtime_data.discovered_entities

    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    # Proxy device info
    proxy_devices = dr.async_entries_for_config_entry(device_reg, entry.entry_id)
    device_info = []
    for device in proxy_devices:
        entities = er.async_entries_for_device(entity_reg, device.id)
        device_info.append(
            {
                "id": device.id,
                "name": device.name,
                "manufacturer": device.manufacturer,
                "model": device.model,
                "entity_count": len(entities),
                "entities": [
                    {
                        "entity_id": ent.entity_id,
                        "platform": ent.platform,
                        "disabled": ent.disabled,
                    }
                    for ent in entities
                ],
            }
        )

    # Climate proxy entity state snapshot
    climate_proxy = state_manager.climate_proxy_entity
    climate_info: dict[str, Any] = {}
    if climate_proxy is not None:
        climate_info = {
            "underlying_entity_id": climate_proxy._underlying_entity_id,  # noqa: SLF001
            "desired_hvac_mode": str(climate_proxy._desired_hvac_mode),  # noqa: SLF001
            "desired_target_temperature": climate_proxy._desired_target_temperature,  # noqa: SLF001
            "current_offset": climate_proxy._current_offset,  # noqa: SLF001
            "underlying_was_unavailable": climate_proxy.underlying_was_unavailable,
        }

    # Discovered entities summary
    discovered_summary = {
        platform.value: [e.entity_id for e in entries]
        for platform, entries in discovered.items()
    }

    # Pending state queue
    pending_state = {k: str(v) for k, v in state_manager.pending_state.items()}

    # Config entry details
    entry_info = {
        "entry_id": entry.entry_id,
        "version": entry.version,
        "domain": entry.domain,
        "title": entry.title,
        "state": str(entry.state),
        "unique_id": entry.unique_id,
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": {
            "temperature_sensors": [
                {"entity_id": s[CONF_SENSOR_ENTITY_ID], "weight": s.get("weight", 1.0)}
                for s in entry.options.get("temperature_sensors", [])
            ],
            "humidity_sensors": [
                {"entity_id": s[CONF_SENSOR_ENTITY_ID], "weight": s.get("weight", 1.0)}
                for s in entry.options.get("humidity_sensors", [])
            ],
        },
    }

    integration_info = {
        "name": integration.name,
        "version": integration.version,
        "domain": integration.domain,
    }

    return {
        "entry": entry_info,
        "integration": integration_info,
        "devices": device_info,
        "climate_proxy": climate_info,
        "discovered_entities": discovered_summary,
        "pending_state": pending_state,
        "debounce_active": state_manager._correcting,  # noqa: SLF001
    }
