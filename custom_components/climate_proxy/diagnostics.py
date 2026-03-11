"""Diagnostics support for climate_proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_CLIMATE_ENTITY_ID, CONF_SENSOR_ENTITY_ID

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

    # Underlying entity actual state snapshot
    underlying_entity_id = entry.data.get(CONF_CLIMATE_ENTITY_ID)
    underlying_state = hass.states.get(underlying_entity_id) if underlying_entity_id else None
    actual_state: dict[str, Any] = {}
    if underlying_state is not None:
        actual_state = {
            "hvac_mode": underlying_state.state,
            "temperature": underlying_state.attributes.get("temperature"),
            "current_temperature": underlying_state.attributes.get("current_temperature"),
            "fan_mode": underlying_state.attributes.get("fan_mode"),
            "preset_mode": underlying_state.attributes.get("preset_mode"),
        }

    # Climate proxy entity desired state snapshot
    climate_proxy = state_manager.climate_proxy_entity
    climate_info: dict[str, Any] = {}
    in_compliance: bool | None = None
    if climate_proxy is not None:
        climate_info = {
            "underlying_entity_id": climate_proxy.underlying_entity_id,
            "desired_hvac_mode": str(climate_proxy.desired_hvac_mode),
            "desired_target_temperature": climate_proxy.desired_target_temperature,
            "current_offset": climate_proxy.current_offset,
            "underlying_was_unavailable": climate_proxy.underlying_was_unavailable,
        }
        if underlying_state is not None:
            corrections = climate_proxy.get_climate_corrections(underlying_state)
            in_compliance = corrections == {}
        else:
            in_compliance = False

    # Per-sensor snapshot
    sensor_snapshot = []
    for s in entry.options.get("temperature_sensors", []):
        sid = s[CONF_SENSOR_ENTITY_ID]
        sstate = hass.states.get(sid)
        sensor_snapshot.append(
            {
                "entity_id": sid,
                "weight": s.get("weight", 1.0),
                "available": sstate is not None and sstate.state not in ("unavailable", "unknown"),
                "value": sstate.state if sstate is not None else None,
            }
        )

    # Discovered entities summary
    discovered_summary = {platform.value: [e.entity_id for e in entries] for platform, entries in discovered.items()}

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
        "actual_state": actual_state,
        "climate_proxy": climate_info,
        "in_compliance": in_compliance,
        "sensor_snapshot": sensor_snapshot,
        "last_correction_time": str(state_manager.last_correction_time) if state_manager.last_correction_time else None,
        "discovered_entities": discovered_summary,
        "pending_state": pending_state,
        "debounce_active": state_manager.debounce_active,
    }
