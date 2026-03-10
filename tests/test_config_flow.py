"""Integration tests for the config flow."""

from __future__ import annotations

import pytest

from custom_components.climate_proxy.const import (
    CONF_CLIMATE_ENTITY_ID,
    CONF_HUMIDITY_SENSORS,
    CONF_PROXY_NAME,
    CONF_SENSOR_ENTITY_ID,
    CONF_SENSOR_WEIGHT,
    CONF_TEMPERATURE_SENSORS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.integration
async def test_config_flow_no_sensors(hass: HomeAssistant) -> None:
    """Complete 3-step flow (no sensors selected) creates a valid config entry."""
    hass.states.async_set("climate.test", "heat", {"hvac_modes": ["off", "heat"]})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROXY_NAME: "My Proxy", CONF_CLIMATE_ENTITY_ID: "climate.test"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "temp_sensors"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"temperature_sensor_ids": []},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "humidity_sensors"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"humidity_sensor_ids": []},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Proxy"
    assert result["data"][CONF_CLIMATE_ENTITY_ID] == "climate.test"
    assert result["options"][CONF_TEMPERATURE_SENSORS] == []
    assert result["options"][CONF_HUMIDITY_SENSORS] == []


@pytest.mark.integration
async def test_config_flow_with_temp_sensors(hass: HomeAssistant) -> None:
    """Full 5-step flow with temperature sensors creates correct options."""
    hass.states.async_set("climate.test", "heat", {"hvac_modes": ["off", "heat"]})
    hass.states.async_set("sensor.bedroom", "18.5", {"device_class": "temperature"})
    hass.states.async_set("sensor.hallway", "20.0", {"device_class": "temperature"})

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROXY_NAME: "Proxy", CONF_CLIMATE_ENTITY_ID: "climate.test"},
    )
    # Select two temperature sensors
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"temperature_sensor_ids": ["sensor.bedroom", "sensor.hallway"]},
    )
    assert result["step_id"] == "temp_weights"

    # Assign weights
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"sensor.bedroom": 2.0, "sensor.hallway": 1.0},
    )
    assert result["step_id"] == "humidity_sensors"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"humidity_sensor_ids": []},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    temp_sensors = result["options"][CONF_TEMPERATURE_SENSORS]
    assert len(temp_sensors) == 2
    bedroom = next(s for s in temp_sensors if s[CONF_SENSOR_ENTITY_ID] == "sensor.bedroom")
    assert bedroom[CONF_SENSOR_WEIGHT] == pytest.approx(2.0)


@pytest.mark.integration
async def test_config_flow_entity_not_found(hass: HomeAssistant) -> None:
    """Selecting a climate entity that doesn't exist shows an error."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROXY_NAME: "Proxy", CONF_CLIMATE_ENTITY_ID: "climate.nonexistent"},
    )
    assert result["type"] == FlowResultType.FORM
    assert "entity_not_found" in result.get("errors", {}).values()


@pytest.mark.integration
async def test_config_flow_duplicate_aborted(hass: HomeAssistant) -> None:
    """Setting up a second proxy for the same underlying entity is aborted."""
    hass.states.async_set("climate.test", "heat", {"hvac_modes": ["off", "heat"]})

    # Complete the flow once
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROXY_NAME: "Proxy 1", CONF_CLIMATE_ENTITY_ID: "climate.test"},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"temperature_sensor_ids": []})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"humidity_sensor_ids": []})
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Try to add the same climate entity again
    result2 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result2 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_PROXY_NAME: "Proxy 2", CONF_CLIMATE_ENTITY_ID: "climate.test"},
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
