"""Subscription helpers for climate_proxy StateManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..const import CONF_HUMIDITY_SENSORS, CONF_SENSOR_ENTITY_ID, CONF_TEMPERATURE_SENSORS

if TYPE_CHECKING:
    from ..data import ClimateProxyConfigEntry


def get_temperature_sensor_ids(config_entry: ClimateProxyConfigEntry) -> list[str]:
    """Return list of temperature sensor entity IDs from config entry options."""
    sensors = config_entry.options.get(CONF_TEMPERATURE_SENSORS, [])
    return [s[CONF_SENSOR_ENTITY_ID] for s in sensors]


def get_humidity_sensor_ids(config_entry: ClimateProxyConfigEntry) -> list[str]:
    """Return list of humidity sensor entity IDs from config entry options."""
    sensors = config_entry.options.get(CONF_HUMIDITY_SENSORS, [])
    return [s[CONF_SENSOR_ENTITY_ID] for s in sensors]


def get_all_sensor_ids(config_entry: ClimateProxyConfigEntry) -> list[str]:
    """Return combined list of all temperature and humidity sensor entity IDs."""
    return get_temperature_sensor_ids(config_entry) + get_humidity_sensor_ids(config_entry)
