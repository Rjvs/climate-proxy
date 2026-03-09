"""Unit tests for sensor/proxy_entity.py — ClimateProxySensorEntity."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State

from custom_components.climate_proxy.sensor.proxy_entity import ClimateProxySensorEntity


def _make_entity() -> ClimateProxySensorEntity:
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "sensor.temperature"
    underlying_entry.name = "Temperature"
    underlying_entry.original_name = "Temperature"

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
    return entity


@pytest.mark.unit
class TestClimateProxySensorEntity:
    def test_unique_id(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "sensor.temperature" in entity.unique_id

    def test_mirrors_numeric_value(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(
            return_value=State(
                "sensor.temperature",
                "21.5",
                {"unit_of_measurement": "°C", "device_class": "temperature"},
            )
        )
        entity._refresh_from_underlying()
        assert entity._attr_native_value == pytest.approx(21.5)
        assert entity._attr_native_unit_of_measurement == "°C"
        assert entity._attr_device_class == "temperature"

    def test_mirrors_non_numeric_value(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(
            return_value=State("sensor.status", "on", {})
        )
        entity.underlying_entity_id = "sensor.status"
        entity._refresh_from_underlying()
        assert entity._attr_native_value == "on"

    def test_unavailable_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(
            return_value=State("sensor.temperature", STATE_UNAVAILABLE)
        )
        entity._refresh_from_underlying()
        assert entity.available is False

    def test_unavailable_when_underlying_unknown(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(
            return_value=State("sensor.temperature", STATE_UNKNOWN)
        )
        entity._refresh_from_underlying()
        assert entity.available is False

    def test_unavailable_when_underlying_missing(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=None)
        entity._refresh_from_underlying()
        assert entity.available is False

    def test_available_when_underlying_valid(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(
            return_value=State("sensor.temperature", "21.5", {})
        )
        entity._refresh_from_underlying()
        assert entity.available is True

    def test_extra_state_attributes_excludes_standard_keys(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(
            return_value=State(
                "sensor.temperature",
                "21.5",
                {
                    "unit_of_measurement": "°C",
                    "device_class": "temperature",
                    "state_class": "measurement",
                    "friendly_name": "Temperature",
                    "custom_attr": "custom_value",
                },
            )
        )
        attrs = entity.extra_state_attributes
        assert "unit_of_measurement" not in attrs
        assert "device_class" not in attrs
        assert "friendly_name" not in attrs
        assert attrs["custom_attr"] == "custom_value"

    def test_extra_state_attributes_none_when_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(
            return_value=State("sensor.temperature", STATE_UNAVAILABLE)
        )
        assert entity.extra_state_attributes is None
