"""Unit tests for capabilities.py."""

from __future__ import annotations

import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.core import State

from custom_components.climate_proxy.climate.capabilities import (
    detect_supported_features,
    extract_fan_modes,
    extract_hvac_modes,
    extract_min_max_temp,
    extract_preset_modes,
    extract_swing_modes,
    extract_temp_step,
)


def _state(attrs: dict) -> State:
    return State("climate.test", HVACMode.OFF, attributes=attrs)


@pytest.mark.unit
class TestDetectSupportedFeatures:

    def test_full_featured_device(self) -> None:
        state = _state({
            "hvac_modes": [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL],
            "temperature": 21.0,
            "fan_modes": ["auto", "low"],
            "preset_modes": ["eco", "comfort"],
            "swing_modes": ["on", "off"],
            "target_humidity": 50,
            "aux_heat": False,
        })
        features = detect_supported_features(state)
        assert features & ClimateEntityFeature.TURN_ON
        assert features & ClimateEntityFeature.TURN_OFF
        assert features & ClimateEntityFeature.TARGET_TEMPERATURE
        assert features & ClimateEntityFeature.FAN_MODE
        assert features & ClimateEntityFeature.PRESET_MODE
        assert features & ClimateEntityFeature.SWING_MODE
        assert features & ClimateEntityFeature.TARGET_HUMIDITY
        assert features & ClimateEntityFeature.AUX_HEAT

    def test_off_only_device(self) -> None:
        state = _state({"hvac_modes": [HVACMode.OFF]})
        features = detect_supported_features(state)
        assert not (features & ClimateEntityFeature.TURN_ON)
        assert features & ClimateEntityFeature.TURN_OFF

    def test_range_temperature(self) -> None:
        state = _state({
            "hvac_modes": [HVACMode.HEAT_COOL],
            "target_temp_low": 18.0,
            "target_temp_high": 24.0,
        })
        features = detect_supported_features(state)
        assert features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

    def test_no_capabilities(self) -> None:
        state = _state({"hvac_modes": []})
        features = detect_supported_features(state)
        assert features == ClimateEntityFeature(0)


@pytest.mark.unit
class TestExtractors:

    def test_extract_hvac_modes(self) -> None:
        state = _state({"hvac_modes": ["off", "heat", "cool", "invalid_mode"]})
        modes = extract_hvac_modes(state)
        assert HVACMode.OFF in modes
        assert HVACMode.HEAT in modes
        assert HVACMode.COOL in modes
        # Invalid modes are silently skipped
        assert len(modes) == 3

    def test_extract_hvac_modes_empty(self) -> None:
        state = _state({"hvac_modes": []})
        modes = extract_hvac_modes(state)
        assert modes == [HVACMode.OFF]

    def test_extract_fan_modes(self) -> None:
        state = _state({"fan_modes": ["auto", "low", "high"]})
        assert extract_fan_modes(state) == ["auto", "low", "high"]

    def test_extract_fan_modes_absent(self) -> None:
        state = _state({})
        assert extract_fan_modes(state) is None

    def test_extract_preset_modes(self) -> None:
        state = _state({"preset_modes": ["eco", "away"]})
        assert extract_preset_modes(state) == ["eco", "away"]

    def test_extract_swing_modes(self) -> None:
        state = _state({"swing_modes": ["on", "off"]})
        assert extract_swing_modes(state) == ["on", "off"]

    def test_extract_min_max_temp_defaults(self) -> None:
        state = _state({})
        min_t, max_t = extract_min_max_temp(state)
        assert min_t == 7.0
        assert max_t == 35.0

    def test_extract_min_max_temp_custom(self) -> None:
        state = _state({"min_temp": 10.0, "max_temp": 30.0})
        assert extract_min_max_temp(state) == (10.0, 30.0)

    def test_extract_temp_step_default(self) -> None:
        state = _state({})
        assert extract_temp_step(state) == 0.5

    def test_extract_temp_step_custom(self) -> None:
        state = _state({"target_temp_step": 1.0})
        assert extract_temp_step(state) == 1.0
