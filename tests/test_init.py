"""Integration lifecycle tests for climate_proxy."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.climate_proxy.const import (
    CONF_CLIMATE_ENTITY_ID,
    CONF_HUMIDITY_SENSORS,
    CONF_PROXY_NAME,
    CONF_TEMPERATURE_SENSORS,
    DOMAIN,
)

from .conftest import create_mock_climate_state


def _make_entry(hass: HomeAssistant):
    """Create and return a MockConfigEntry for climate_proxy."""
    return _mock_entry(
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
