"""
Climate Proxy — Home Assistant custom integration.

Creates a virtual climate device that wraps a real physical thermostat.
All sensors are proxied without alteration; all controls are intercepted
and enforced so that the real device always matches the user's settings.

IoT class: local_push (event-driven, no external API).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.loader import async_get_loaded_integration
import homeassistant.helpers.config_validation as cv

from .const import CONF_CLIMATE_ENTITY_ID, DOMAIN, LOGGER
from .data import ClimateProxyData
from .state_manager import ClimateProxyStateManager
from .state_manager.entity_discovery import discover_underlying_entities

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import ClimateProxyConfigEntry

# All possible proxy platforms; active set is determined per-entry at setup time
_ALL_PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.FAN,
]

# Integration is configured via config entries only — no YAML
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ClimateProxyConfigEntry,
) -> bool:
    """
    Set up climate_proxy from a config entry.

    Steps:
    1. Discover all entities on the underlying device (grouped by platform).
    2. Determine which platforms to activate.
    3. Create StateManager and store runtime data.
    4. Forward setup to active platforms.
    5. Subscribe StateManager to state_changed events.
    6. Register reload listener.
    """
    climate_entity_id = entry.data[CONF_CLIMATE_ENTITY_ID]

    # Discover other entities on the underlying device
    discovered_entities = discover_underlying_entities(hass, climate_entity_id)
    LOGGER.debug(
        "Discovered entities for %s: %s",
        climate_entity_id,
        {k.value: [e.entity_id for e in v] for k, v in discovered_entities.items()},
    )

    # Always activate CLIMATE + SENSOR (for weighted-avg sensors)
    active_platforms: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]
    for platform in [
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.SELECT,
        Platform.NUMBER,
        Platform.BUTTON,
        Platform.FAN,
    ]:
        if platform in discovered_entities:
            active_platforms.append(platform)

    state_manager = ClimateProxyStateManager(hass, entry)

    entry.runtime_data = ClimateProxyData(
        state_manager=state_manager,
        integration=async_get_loaded_integration(hass, entry.domain),
        discovered_entities=discovered_entities,
    )

    await hass.config_entries.async_forward_entry_setups(entry, active_platforms)

    # Subscribe to events after entities are created
    await state_manager.async_setup()

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ClimateProxyConfigEntry,
) -> bool:
    """Unload a config entry — tear down subscriptions and platform entities."""
    await entry.runtime_data.state_manager.async_teardown()

    # Determine which platforms were activated
    discovered = entry.runtime_data.discovered_entities
    active_platforms: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]
    for platform in [
        Platform.BINARY_SENSOR,
        Platform.SWITCH,
        Platform.SELECT,
        Platform.NUMBER,
        Platform.BUTTON,
        Platform.FAN,
    ]:
        if platform in discovered:
            active_platforms.append(platform)

    return await hass.config_entries.async_unload_platforms(entry, active_platforms)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ClimateProxyConfigEntry,
) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
