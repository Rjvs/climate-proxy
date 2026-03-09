"""Sensor platform for climate_proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import (
    CONF_HUMIDITY_SENSORS,
    CONF_TEMPERATURE_SENSORS,
    DOMAIN,
    LOGGER,
)
from .proxy_entity import ClimateProxySensorEntity
from .weighted_avg import WeightedAvgHumiditySensor, WeightedAvgTemperatureSensor

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from ..data import ClimateProxyConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ClimateProxyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform for a climate_proxy config entry.

    Creates:
    - One ClimateProxySensorEntity for every sensor discovered on the underlying device.
    - A WeightedAvgTemperatureSensor if temperature sensors are configured in options.
    - A WeightedAvgHumiditySensor if humidity sensors are configured in options.

    All entities are grouped under the same virtual device as the proxy climate entity.
    """
    state_manager = entry.runtime_data.state_manager

    # Prefer the device_info already stored on the climate proxy entity so that
    # the full device metadata (name, manufacturer, model, …) is preserved.
    # Fall back to a minimal DeviceInfo built from the domain + entry_id if the
    # climate entity has not been set up yet (which should not happen in practice
    # because the climate platform is registered before the sensor platform).
    if (
        state_manager.climate_proxy_entity is not None
        and state_manager.climate_proxy_entity.device_info is not None
    ):
        device_info: DeviceInfo = state_manager.climate_proxy_entity.device_info
    else:
        device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    entities: list = []

    # ------------------------------------------------------------------
    # Pass-through proxy sensors for every discovered sensor entity
    # ------------------------------------------------------------------
    discovered_sensors = entry.runtime_data.discovered_entities.get(Platform.SENSOR, [])
    for underlying_entry in discovered_sensors:
        entities.append(
            ClimateProxySensorEntity(
                config_entry=entry,
                underlying_entry=underlying_entry,
                state_manager=state_manager,
                device_info=device_info,
            )
        )

    LOGGER.debug(
        "climate_proxy %s: creating %d pass-through sensor entities",
        entry.entry_id,
        len(discovered_sensors),
    )

    # ------------------------------------------------------------------
    # Weighted average sensors (only when sensors are configured in options)
    # ------------------------------------------------------------------
    temp_sensor_configs = entry.options.get(CONF_TEMPERATURE_SENSORS)
    if temp_sensor_configs:
        weighted_temp = WeightedAvgTemperatureSensor(
            config_entry=entry,
            state_manager=state_manager,
            device_info=device_info,
        )
        entities.append(weighted_temp)
        state_manager.weighted_avg_entities.append(weighted_temp)
        LOGGER.debug(
            "climate_proxy %s: creating WeightedAvgTemperatureSensor (%d sources)",
            entry.entry_id,
            len(temp_sensor_configs),
        )

    humidity_sensor_configs = entry.options.get(CONF_HUMIDITY_SENSORS)
    if humidity_sensor_configs:
        weighted_humidity = WeightedAvgHumiditySensor(
            config_entry=entry,
            state_manager=state_manager,
            device_info=device_info,
        )
        entities.append(weighted_humidity)
        state_manager.weighted_avg_entities.append(weighted_humidity)
        LOGGER.debug(
            "climate_proxy %s: creating WeightedAvgHumiditySensor (%d sources)",
            entry.entry_id,
            len(humidity_sensor_configs),
        )

    async_add_entities(entities)
