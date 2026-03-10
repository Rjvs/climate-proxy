"""Unit tests for sensor/proxy_entity.py — ClimateProxySensorEntity."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.climate_proxy.sensor.proxy_entity import ClimateProxySensorEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State


def _make_entity() -> ClimateProxySensorEntity:
    """Build a ClimateProxySensorEntity with all dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "sensor.test_sensor"
    underlying_entry.name = "Test Sensor"
    underlying_entry.original_name = "Test Sensor"

    state_manager = MagicMock()
    state_manager.sensor_proxy_entities = []
    device_info = MagicMock()

    entity = ClimateProxySensorEntity(
        config_entry=config_entry,
        underlying_entry=underlying_entry,
        state_manager=state_manager,
        device_info=device_info,
    )
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.mark.unit
class TestClimateProxySensorEntity:
    def test_unique_id_contains_entry_and_entity(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity._attr_unique_id
        assert "sensor.test_sensor" in entity._attr_unique_id

    def test_name_from_underlying_entry(self) -> None:
        entity = _make_entity()
        assert entity._attr_name == "Test Sensor"

    def test_available_when_underlying_is_available(self) -> None:
        entity = _make_entity()
        entity._underlying_available = True
        assert entity.available is True

    def test_unavailable_when_underlying_is_unavailable(self) -> None:
        entity = _make_entity()
        entity._underlying_available = False
        assert entity.available is False

    def test_refresh_from_underlying_numeric_value(self) -> None:
        entity = _make_entity()
        state = State(
            "sensor.test_sensor",
            "21.5",
            {"unit_of_measurement": "°C", "device_class": "temperature"},
        )
        entity.hass.states.get = MagicMock(return_value=state)
        entity._refresh_from_underlying()
        assert entity._attr_native_value == pytest.approx(21.5)
        assert entity._attr_native_unit_of_measurement == "°C"
        assert entity._attr_device_class == "temperature"
        assert entity._underlying_available is True

    def test_refresh_from_underlying_string_value(self) -> None:
        entity = _make_entity()
        state = State("sensor.test_sensor", "some_text", {})
        entity.hass.states.get = MagicMock(return_value=state)
        entity._refresh_from_underlying()
        assert entity._attr_native_value == "some_text"

    def test_refresh_from_underlying_unavailable_marks_unavailable(self) -> None:
        entity = _make_entity()
        state = State("sensor.test_sensor", STATE_UNAVAILABLE, {})
        entity.hass.states.get = MagicMock(return_value=state)
        entity._refresh_from_underlying()
        assert entity._underlying_available is False

    def test_refresh_from_underlying_none_marks_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=None)
        entity._refresh_from_underlying()
        assert entity._underlying_available is False

    def test_extra_state_attributes_excludes_standard_keys(self) -> None:
        entity = _make_entity()
        state = State(
            "sensor.test_sensor",
            "21.5",
            {
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "state_class": "measurement",
                "friendly_name": "Test",
                "custom_attr": "value",
            },
        )
        entity.hass.states.get = MagicMock(return_value=state)
        attrs = entity.extra_state_attributes
        assert attrs is not None
        assert "custom_attr" in attrs
        assert "unit_of_measurement" not in attrs
        assert "device_class" not in attrs

    def test_extra_state_attributes_returns_none_when_unavailable(self) -> None:
        entity = _make_entity()
        state = State("sensor.test_sensor", STATE_UNKNOWN, {})
        entity.hass.states.get = MagicMock(return_value=state)
        assert entity.extra_state_attributes is None

    def test_extra_state_attributes_returns_none_when_state_is_none(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=None)
        assert entity.extra_state_attributes is None

    def test_extra_state_attributes_returns_none_when_all_excluded(self) -> None:
        entity = _make_entity()
        state = State(
            "sensor.test_sensor",
            "21.5",
            {"unit_of_measurement": "°C", "device_class": "temperature"},
        )
        entity.hass.states.get = MagicMock(return_value=state)
        assert entity.extra_state_attributes is None
