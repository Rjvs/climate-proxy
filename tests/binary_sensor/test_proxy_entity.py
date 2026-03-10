"""Unit tests for binary_sensor/proxy_entity.py — ClimateProxyBinarySensorEntity."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.climate_proxy.binary_sensor.proxy_entity import ClimateProxyBinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State


def _make_entity(device_class: str | None = None) -> ClimateProxyBinarySensorEntity:
    """Build a ClimateProxyBinarySensorEntity with all dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "binary_sensor.test"
    underlying_entry.name = "Test Binary Sensor"
    underlying_entry.original_name = "Test Binary Sensor"
    underlying_entry.device_class = device_class

    state_manager = MagicMock()
    state_manager.binary_sensor_proxy_entities = []
    device_info = MagicMock()

    entity = ClimateProxyBinarySensorEntity(
        config_entry=config_entry,
        underlying_entry=underlying_entry,
        state_manager=state_manager,
        device_info=device_info,
    )
    entity.hass = MagicMock()
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.mark.unit
class TestClimateProxyBinarySensorEntity:
    def test_unique_id_contains_entry_and_entity(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity._attr_unique_id
        assert "binary_sensor.test" in entity._attr_unique_id

    def test_device_class_set_from_registry_entry(self) -> None:
        entity = _make_entity(device_class="motion")
        assert entity._attr_device_class == BinarySensorDeviceClass.MOTION

    def test_is_on_true_when_underlying_on(self) -> None:
        entity = _make_entity()
        state = State("binary_sensor.test", STATE_ON, {})
        entity.hass.states.get = MagicMock(return_value=state)
        assert entity.is_on is True

    def test_is_on_false_when_underlying_off(self) -> None:
        entity = _make_entity()
        state = State("binary_sensor.test", STATE_OFF, {})
        entity.hass.states.get = MagicMock(return_value=state)
        assert entity.is_on is False

    def test_is_on_none_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        state = State("binary_sensor.test", STATE_UNAVAILABLE, {})
        entity.hass.states.get = MagicMock(return_value=state)
        assert entity.is_on is None

    def test_is_on_none_when_underlying_unknown(self) -> None:
        entity = _make_entity()
        state = State("binary_sensor.test", STATE_UNKNOWN, {})
        entity.hass.states.get = MagicMock(return_value=state)
        assert entity.is_on is None

    def test_available_when_underlying_on(self) -> None:
        entity = _make_entity()
        state = State("binary_sensor.test", STATE_ON, {})
        entity.hass.states.get = MagicMock(return_value=state)
        assert entity.available is True

    def test_not_available_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        state = State("binary_sensor.test", STATE_UNAVAILABLE, {})
        entity.hass.states.get = MagicMock(return_value=state)
        assert entity.available is False

    def test_not_available_when_state_is_none(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=None)
        assert entity.available is False

    def test_extra_state_attributes_mirrors_non_standard_attrs(self) -> None:
        entity = _make_entity()
        state = State(
            "binary_sensor.test",
            STATE_ON,
            {"device_class": "motion", "custom_key": "custom_val", "friendly_name": "Test"},
        )
        entity.hass.states.get = MagicMock(return_value=state)
        attrs = entity.extra_state_attributes
        assert attrs is not None
        assert "custom_key" in attrs
        assert "device_class" not in attrs
        assert "friendly_name" not in attrs

    def test_extra_state_attributes_none_when_unavailable(self) -> None:
        entity = _make_entity()
        state = State("binary_sensor.test", STATE_UNAVAILABLE, {})
        entity.hass.states.get = MagicMock(return_value=state)
        assert entity.extra_state_attributes is None

    def test_refresh_device_class_from_state_attributes(self) -> None:
        entity = _make_entity()
        state = State("binary_sensor.test", STATE_ON, {"device_class": "door"})
        entity._refresh_device_class(state)
        assert entity._attr_device_class == BinarySensorDeviceClass.DOOR

    def test_refresh_device_class_unknown_value_stored_as_is(self) -> None:
        entity = _make_entity()
        state = State("binary_sensor.test", STATE_ON, {"device_class": "not_a_class"})
        entity._refresh_device_class(state)
        assert entity._attr_device_class == "not_a_class"
