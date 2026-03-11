"""Integration lifecycle tests for climate_proxy."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.climate_proxy.const import (
    CONF_CLIMATE_ENTITY_ID,
    CONF_HUMIDITY_SENSORS,
    CONF_PROXY_NAME,
    CONF_TEMPERATURE_SENSORS,
    DOMAIN,
)
from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


def _mock_entry(**kwargs):
    """Build a MockConfigEntry without importing from a test-only module."""
    try:
        from pytest_homeassistant_custom_component.common import MockConfigEntry
    except ImportError:
        from homeassistant.helpers.device_registry import DeviceInfo  # noqa: F401

        raise

    return MockConfigEntry(**kwargs)


@pytest.mark.integration
async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """async_setup_entry completes without error for a minimal config."""
    hass.states.async_set(
        "climate.test_thermostat",
        HVACMode.HEAT,
        {"hvac_modes": ["off", "heat"], "temperature": 21.0, "current_temperature": 19.0},
    )

    entry = _mock_entry(
        domain=DOMAIN,
        data={
            CONF_PROXY_NAME: "Test Proxy",
            CONF_CLIMATE_ENTITY_ID: "climate.test_thermostat",
        },
        options={
            CONF_TEMPERATURE_SENSORS: [],
            CONF_HUMIDITY_SENSORS: [],
        },
    )
    entry.add_to_hass(hass)

    # discover_underlying_entities returns empty (no companion entities)
    with patch(
        "custom_components.climate_proxy.discover_underlying_entities",
        return_value={},
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.integration
async def test_unload_entry(hass: HomeAssistant) -> None:
    """async_unload_entry tears down cleanly and leaves LOADED state as NOT_LOADED."""
    hass.states.async_set(
        "climate.test_thermostat",
        HVACMode.HEAT,
        {"hvac_modes": ["off", "heat"], "temperature": 21.0, "current_temperature": 19.0},
    )

    entry = _mock_entry(
        domain=DOMAIN,
        data={
            CONF_PROXY_NAME: "Test Proxy",
            CONF_CLIMATE_ENTITY_ID: "climate.test_thermostat",
        },
        options={
            CONF_TEMPERATURE_SENSORS: [],
            CONF_HUMIDITY_SENSORS: [],
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.climate_proxy.discover_underlying_entities",
        return_value={},
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.async_unload(entry.entry_id)
    assert result is True
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.integration
async def test_setup_activates_fan_platform_when_underlying_has_fan(hass: HomeAssistant) -> None:
    """When the underlying device has a fan entity, the FAN platform is activated."""
    from homeassistant.const import Platform

    hass.states.async_set(
        "climate.test_thermostat",
        "heat",
        {"hvac_modes": ["off", "heat"], "temperature": 21.0, "current_temperature": 19.0},
    )

    entry = _mock_entry(
        domain=DOMAIN,
        data={
            CONF_PROXY_NAME: "Test Proxy",
            CONF_CLIMATE_ENTITY_ID: "climate.test_thermostat",
        },
        options={
            CONF_TEMPERATURE_SENSORS: [],
            CONF_HUMIDITY_SENSORS: [],
        },
    )
    entry.add_to_hass(hass)

    mock_fan_entity = MagicMock()
    mock_fan_entity.entity_id = "fan.test_fan"

    with patch(
        "custom_components.climate_proxy.discover_underlying_entities",
        return_value={Platform.FAN: [mock_fan_entity]},
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True
    assert Platform.FAN in entry.runtime_data.active_platforms


@pytest.mark.integration
async def test_setup_activates_only_climate_and_sensor_when_no_companions(hass: HomeAssistant) -> None:
    """When no companion entities are discovered, only CLIMATE and SENSOR platforms are active."""
    from homeassistant.const import Platform

    hass.states.async_set(
        "climate.test_thermostat",
        "heat",
        {"hvac_modes": ["off", "heat"], "temperature": 21.0, "current_temperature": 19.0},
    )

    entry = _mock_entry(
        domain=DOMAIN,
        data={
            CONF_PROXY_NAME: "Test Proxy",
            CONF_CLIMATE_ENTITY_ID: "climate.test_thermostat",
        },
        options={
            CONF_TEMPERATURE_SENSORS: [],
            CONF_HUMIDITY_SENSORS: [],
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.climate_proxy.discover_underlying_entities",
        return_value={},
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True
    assert entry.runtime_data.active_platforms == [Platform.CLIMATE, Platform.SENSOR]


@pytest.mark.integration
async def test_setup_when_underlying_unavailable(hass: HomeAssistant) -> None:
    """Setup succeeds and entry loads even when the underlying entity is unavailable."""
    from homeassistant.const import STATE_UNAVAILABLE

    hass.states.async_set("climate.test_thermostat", STATE_UNAVAILABLE, {})

    entry = _mock_entry(
        domain=DOMAIN,
        data={
            CONF_PROXY_NAME: "Test Proxy",
            CONF_CLIMATE_ENTITY_ID: "climate.test_thermostat",
        },
        options={
            CONF_TEMPERATURE_SENSORS: [],
            CONF_HUMIDITY_SENSORS: [],
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.climate_proxy.discover_underlying_entities",
        return_value={},
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.integration
async def test_setup_entry_runtime_data_populated(hass: HomeAssistant) -> None:
    """After setup, entry.runtime_data has state_manager and discovered_entities."""
    hass.states.async_set(
        "climate.test_thermostat",
        HVACMode.HEAT,
        {"hvac_modes": ["off", "heat"], "temperature": 21.0, "current_temperature": 19.0},
    )

    entry = _mock_entry(
        domain=DOMAIN,
        data={
            CONF_PROXY_NAME: "Test Proxy",
            CONF_CLIMATE_ENTITY_ID: "climate.test_thermostat",
        },
        options={
            CONF_TEMPERATURE_SENSORS: [],
            CONF_HUMIDITY_SENSORS: [],
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.climate_proxy.discover_underlying_entities",
        return_value={},
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert hasattr(entry, "runtime_data")
    assert entry.runtime_data.state_manager is not None
    assert entry.runtime_data.discovered_entities == {}
