"""Shared test fixtures for climate_proxy tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, State

from custom_components.climate_proxy.const import (
    CONF_CLIMATE_ENTITY_ID,
    CONF_HUMIDITY_SENSORS,
    CONF_PROXY_NAME,
    CONF_SENSOR_ENTITY_ID,
    CONF_SENSOR_WEIGHT,
    CONF_TEMPERATURE_SENSORS,
    DOMAIN,
)


def create_mock_climate_state(
    entity_id: str = "climate.test_thermostat",
    hvac_mode: str = HVACMode.HEAT,
    hvac_modes: list[str] | None = None,
    target_temperature: float = 21.0,
    current_temperature: float = 19.0,
    current_humidity: int | None = None,
    target_humidity: float | None = None,
    fan_modes: list[str] | None = None,
    preset_modes: list[str] | None = None,
    swing_modes: list[str] | None = None,
    min_temp: float = 7.0,
    max_temp: float = 35.0,
    temp_step: float = 0.5,
) -> State:
    """Build a mock HA State for a climate entity."""
    if hvac_modes is None:
        hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL]

    attrs: dict[str, Any] = {
        "hvac_modes": hvac_modes,
        "temperature": target_temperature,
        "current_temperature": current_temperature,
        "min_temp": min_temp,
        "max_temp": max_temp,
        "target_temp_step": temp_step,
    }
    if current_humidity is not None:
        attrs["current_humidity"] = current_humidity
    if target_humidity is not None:
        attrs["humidity"] = target_humidity
        attrs["target_humidity"] = target_humidity
    if fan_modes is not None:
        attrs["fan_modes"] = fan_modes
        attrs["fan_mode"] = fan_modes[0]
    if preset_modes is not None:
        attrs["preset_modes"] = preset_modes
        attrs["preset_mode"] = preset_modes[0]
    if swing_modes is not None:
        attrs["swing_modes"] = swing_modes
        attrs["swing_mode"] = swing_modes[0]

    return State(entity_id, hvac_mode, attributes=attrs)


def create_mock_sensor_state(
    entity_id: str,
    value: float,
    device_class: str = "temperature",
    unit: str = "°C",
) -> State:
    """Build a mock HA State for a sensor entity."""
    return State(
        entity_id,
        str(value),
        attributes={"device_class": device_class, "unit_of_measurement": unit},
    )


@pytest.fixture
def mock_climate_state() -> State:
    """Standard mock climate entity state."""
    return create_mock_climate_state()


@pytest.fixture
def mock_temp_sensor_states() -> list[State]:
    """Two temperature sensor states."""
    return [
        create_mock_sensor_state("sensor.bedroom_temp", 18.0),
        create_mock_sensor_state("sensor.hallway_temp", 20.0),
    ]


@pytest.fixture
def mock_config_entry_data() -> dict[str, Any]:
    """Minimal config entry data dict."""
    return {
        CONF_PROXY_NAME: "Test Proxy",
        CONF_CLIMATE_ENTITY_ID: "climate.test_thermostat",
    }


@pytest.fixture
def mock_config_entry_options() -> dict[str, Any]:
    """Config entry options with two temperature sensors (equal weights)."""
    return {
        CONF_TEMPERATURE_SENSORS: [
            {CONF_SENSOR_ENTITY_ID: "sensor.bedroom_temp", CONF_SENSOR_WEIGHT: 1.0},
            {CONF_SENSOR_ENTITY_ID: "sensor.hallway_temp", CONF_SENSOR_WEIGHT: 1.0},
        ],
        CONF_HUMIDITY_SENSORS: [],
    }
