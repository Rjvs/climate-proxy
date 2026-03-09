"""Unit tests for sensor/weighted_avg.py — WeightedAvgTemperatureSensor and WeightedAvgHumiditySensor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.climate_proxy.sensor.weighted_avg import (
    WeightedAvgHumiditySensor,
    WeightedAvgTemperatureSensor,
)
from custom_components.climate_proxy.const import (
    CONF_HUMIDITY_SENSORS,
    CONF_SENSOR_ENTITY_ID,
    CONF_SENSOR_WEIGHT,
    CONF_TEMPERATURE_SENSORS,
)


def _make_temp_sensor(sensor_configs: list[dict]) -> WeightedAvgTemperatureSensor:
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.options = {CONF_TEMPERATURE_SENSORS: sensor_configs}

    state_manager = MagicMock()
    device_info = MagicMock()

    entity = WeightedAvgTemperatureSensor(
        config_entry=config_entry,
        state_manager=state_manager,
        device_info=device_info,
    )
    entity.hass = MagicMock()
    return entity


def _make_humidity_sensor(sensor_configs: list[dict]) -> WeightedAvgHumiditySensor:
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.options = {CONF_HUMIDITY_SENSORS: sensor_configs}

    state_manager = MagicMock()
    device_info = MagicMock()

    entity = WeightedAvgHumiditySensor(
        config_entry=config_entry,
        state_manager=state_manager,
        device_info=device_info,
    )
    entity.hass = MagicMock()
    return entity


def _mock_hass_state(entity: WeightedAvgTemperatureSensor | WeightedAvgHumiditySensor, states: dict[str, str]) -> None:
    def get_state(entity_id: str):
        value = states.get(entity_id)
        if value is None:
            return None
        mock_state = MagicMock()
        mock_state.state = value
        return mock_state

    entity.hass.states.get = get_state


@pytest.mark.unit
class TestWeightedAvgTemperatureSensor:
    def test_returns_none_when_no_sensors_configured(self) -> None:
        entity = _make_temp_sensor([])
        assert entity.native_value is None

    def test_single_sensor_value(self) -> None:
        configs = [{CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0}]
        entity = _make_temp_sensor(configs)
        _mock_hass_state(entity, {"sensor.a": "20.0"})
        assert entity.native_value == pytest.approx(20.0)

    def test_weighted_average_two_sensors(self) -> None:
        configs = [
            {CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 2.0},
            {CONF_SENSOR_ENTITY_ID: "sensor.b", CONF_SENSOR_WEIGHT: 1.0},
        ]
        entity = _make_temp_sensor(configs)
        # (18*2 + 24*1) / 3 = 20.0
        _mock_hass_state(entity, {"sensor.a": "18.0", "sensor.b": "24.0"})
        assert entity.native_value == pytest.approx(20.0)

    def test_rounds_to_two_decimal_places(self) -> None:
        configs = [
            {CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0},
            {CONF_SENSOR_ENTITY_ID: "sensor.b", CONF_SENSOR_WEIGHT: 1.0},
        ]
        entity = _make_temp_sensor(configs)
        _mock_hass_state(entity, {"sensor.a": "20.1", "sensor.b": "20.2"})
        result = entity.native_value
        assert result is not None
        # Should be rounded to 2dp
        assert result == round(result, 2)

    def test_returns_none_when_all_unavailable(self) -> None:
        configs = [{CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0}]
        entity = _make_temp_sensor(configs)
        _mock_hass_state(entity, {"sensor.a": "unavailable"})
        assert entity.native_value is None

    def test_unique_id_includes_entry_id(self) -> None:
        entity = _make_temp_sensor([])
        assert "test_entry" in entity.unique_id
        assert "weighted_avg_temperature" in entity.unique_id


@pytest.mark.unit
class TestWeightedAvgHumiditySensor:
    def test_returns_none_when_no_sensors_configured(self) -> None:
        entity = _make_humidity_sensor([])
        assert entity.native_value is None

    def test_single_sensor_value(self) -> None:
        configs = [{CONF_SENSOR_ENTITY_ID: "sensor.h", CONF_SENSOR_WEIGHT: 1.0}]
        entity = _make_humidity_sensor(configs)
        _mock_hass_state(entity, {"sensor.h": "60.0"})
        assert entity.native_value == pytest.approx(60.0)

    def test_weighted_average(self) -> None:
        configs = [
            {CONF_SENSOR_ENTITY_ID: "sensor.h1", CONF_SENSOR_WEIGHT: 1.0},
            {CONF_SENSOR_ENTITY_ID: "sensor.h2", CONF_SENSOR_WEIGHT: 1.0},
        ]
        entity = _make_humidity_sensor(configs)
        _mock_hass_state(entity, {"sensor.h1": "60.0", "sensor.h2": "80.0"})
        assert entity.native_value == pytest.approx(70.0)

    def test_unique_id(self) -> None:
        entity = _make_humidity_sensor([])
        assert "weighted_avg_humidity" in entity.unique_id


@pytest.mark.unit
class TestWeightedAvgSensorTranslationKey:
    """E4: Verify sensors use _attr_translation_key, not hardcoded _attr_name."""

    def test_temperature_sensor_uses_translation_key(self) -> None:
        entity = _make_temp_sensor([])
        assert entity._attr_translation_key == "weighted_avg_temperature"

    def test_temperature_sensor_has_no_hardcoded_name(self) -> None:
        entity = _make_temp_sensor([])
        assert entity._attr_name is None

    def test_humidity_sensor_uses_translation_key(self) -> None:
        entity = _make_humidity_sensor([])
        assert entity._attr_translation_key == "weighted_avg_humidity"

    def test_humidity_sensor_has_no_hardcoded_name(self) -> None:
        entity = _make_humidity_sensor([])
        assert entity._attr_name is None
