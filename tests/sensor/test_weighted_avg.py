"""Unit tests for sensor/weighted_avg.py — WeightedAvgTemperatureSensor and WeightedAvgHumiditySensor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.climate_proxy.const import CONF_SENSOR_ENTITY_ID, CONF_SENSOR_WEIGHT
from custom_components.climate_proxy.sensor.weighted_avg import WeightedAvgHumiditySensor, WeightedAvgTemperatureSensor


def _make_temp_sensor() -> WeightedAvgTemperatureSensor:
    """Build a WeightedAvgTemperatureSensor with dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.options = {}

    state_manager = MagicMock()
    device_info = MagicMock()

    entity = WeightedAvgTemperatureSensor(
        config_entry=config_entry,
        state_manager=state_manager,
        device_info=device_info,
    )
    entity.hass = MagicMock()
    return entity


def _make_humidity_sensor() -> WeightedAvgHumiditySensor:
    """Build a WeightedAvgHumiditySensor with dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.options = {}

    state_manager = MagicMock()
    device_info = MagicMock()

    entity = WeightedAvgHumiditySensor(
        config_entry=config_entry,
        state_manager=state_manager,
        device_info=device_info,
    )
    entity.hass = MagicMock()
    return entity


@pytest.mark.unit
class TestWeightedAvgTemperatureSensor:
    def test_unique_id_contains_entry_and_suffix(self) -> None:
        sensor = _make_temp_sensor()
        assert "test_entry" in sensor._attr_unique_id
        assert "weighted_avg_temperature" in sensor._attr_unique_id

    def test_uses_translation_key(self) -> None:
        sensor = _make_temp_sensor()
        assert sensor._attr_translation_key == "weighted_avg_temperature"

    def test_native_value_returns_none_when_no_sensors_configured(self) -> None:
        sensor = _make_temp_sensor()
        sensor._config_entry.options = {}
        assert sensor.native_value is None

    def test_native_value_single_sensor(self) -> None:
        sensor = _make_temp_sensor()
        sensor._config_entry.options = {
            "temperature_sensors": [{CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0}]
        }
        state = MagicMock()
        state.state = "21.5"
        sensor.hass.states.get = MagicMock(return_value=state)

        result = sensor.native_value
        assert result == pytest.approx(21.5)

    def test_native_value_two_equal_weight_sensors(self) -> None:
        sensor = _make_temp_sensor()
        sensor._config_entry.options = {
            "temperature_sensors": [
                {CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0},
                {CONF_SENSOR_ENTITY_ID: "sensor.b", CONF_SENSOR_WEIGHT: 1.0},
            ]
        }

        def get_state(entity_id: str) -> MagicMock:
            s = MagicMock()
            s.state = "19.0" if entity_id == "sensor.a" else "23.0"
            return s

        sensor.hass.states.get = get_state
        result = sensor.native_value
        assert result == pytest.approx(21.0)

    def test_native_value_rounds_to_two_decimal_places(self) -> None:
        sensor = _make_temp_sensor()
        sensor._config_entry.options = {
            "temperature_sensors": [
                {CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0},
                {CONF_SENSOR_ENTITY_ID: "sensor.b", CONF_SENSOR_WEIGHT: 1.0},
                {CONF_SENSOR_ENTITY_ID: "sensor.c", CONF_SENSOR_WEIGHT: 1.0},
            ]
        }

        def get_state(entity_id: str) -> MagicMock:
            s = MagicMock()
            # 20 + 20 + 21 = 61 / 3 = 20.333...
            s.state = "20.0" if entity_id != "sensor.c" else "21.0"
            return s

        sensor.hass.states.get = get_state
        result = sensor.native_value
        assert result is not None
        # Should be rounded to 2 decimal places
        assert result == round(result, 2)

    def test_native_value_returns_none_when_all_unavailable(self) -> None:
        sensor = _make_temp_sensor()
        sensor._config_entry.options = {
            "temperature_sensors": [{CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0}]
        }
        state = MagicMock()
        state.state = "unavailable"
        sensor.hass.states.get = MagicMock(return_value=state)
        assert sensor.native_value is None


@pytest.mark.unit
class TestWeightedAvgHumiditySensor:
    def test_unique_id_contains_entry_and_suffix(self) -> None:
        sensor = _make_humidity_sensor()
        assert "test_entry" in sensor._attr_unique_id
        assert "weighted_avg_humidity" in sensor._attr_unique_id

    def test_uses_translation_key(self) -> None:
        sensor = _make_humidity_sensor()
        assert sensor._attr_translation_key == "weighted_avg_humidity"

    def test_native_value_returns_none_when_no_sensors(self) -> None:
        sensor = _make_humidity_sensor()
        sensor._config_entry.options = {}
        assert sensor.native_value is None

    def test_native_value_single_sensor(self) -> None:
        sensor = _make_humidity_sensor()
        sensor._config_entry.options = {
            "humidity_sensors": [{CONF_SENSOR_ENTITY_ID: "sensor.hum", CONF_SENSOR_WEIGHT: 1.0}]
        }
        state = MagicMock()
        state.state = "55.0"
        sensor.hass.states.get = MagicMock(return_value=state)
        result = sensor.native_value
        assert result == pytest.approx(55.0)
