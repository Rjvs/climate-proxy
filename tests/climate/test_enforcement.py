"""Unit tests for enforcement.py."""

from __future__ import annotations

import pytest

from custom_components.climate_proxy.climate.enforcement import get_climate_corrections
from homeassistant.components.climate import HVACMode
from homeassistant.core import State


def _state(hvac_mode: str, attrs: dict) -> State:
    return State("climate.test", hvac_mode, attributes=attrs)


@pytest.mark.unit
class TestGetClimateCorrections:
    def test_no_corrections_needed(self) -> None:
        """When underlying state matches desired state, no corrections returned."""
        state = _state(HVACMode.HEAT, {"temperature": 21.0})
        corrections = get_climate_corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
            desired_target_temperature_low=None,
            desired_target_temperature_high=None,
            desired_target_humidity=None,
            desired_preset_mode=None,
            desired_fan_mode=None,
            desired_swing_mode=None,
            desired_aux_heat=None,
        )
        assert corrections == {}

    def test_hvac_mode_correction(self) -> None:
        state = _state(HVACMode.COOL, {})
        corrections = get_climate_corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=None,
            desired_target_temperature_low=None,
            desired_target_temperature_high=None,
            desired_target_humidity=None,
            desired_preset_mode=None,
            desired_fan_mode=None,
            desired_swing_mode=None,
            desired_aux_heat=None,
        )
        assert "set_hvac_mode" in corrections
        assert corrections["set_hvac_mode"]["hvac_mode"] == HVACMode.HEAT

    def test_temperature_correction(self) -> None:
        state = _state(HVACMode.HEAT, {"temperature": 19.0})
        corrections = get_climate_corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
            desired_target_temperature_low=None,
            desired_target_temperature_high=None,
            desired_target_humidity=None,
            desired_preset_mode=None,
            desired_fan_mode=None,
            desired_swing_mode=None,
            desired_aux_heat=None,
        )
        assert "set_temperature" in corrections
        assert corrections["set_temperature"]["temperature"] == 21.0

    def test_temperature_within_tolerance_no_correction(self) -> None:
        """A deviation within TEMPERATURE_TOLERANCE should not trigger correction."""
        state = _state(HVACMode.HEAT, {"temperature": 21.05})  # within 0.1°C tolerance
        corrections = get_climate_corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
            desired_target_temperature_low=None,
            desired_target_temperature_high=None,
            desired_target_humidity=None,
            desired_preset_mode=None,
            desired_fan_mode=None,
            desired_swing_mode=None,
            desired_aux_heat=None,
        )
        assert "set_temperature" not in corrections

    def test_effective_temperature_overrides_desired(self) -> None:
        """When effective_target_temperature is provided, it is used for corrections."""
        state = _state(HVACMode.HEAT, {"temperature": 21.0})
        corrections = get_climate_corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=20.0,
            desired_target_temperature_low=None,
            desired_target_temperature_high=None,
            desired_target_humidity=None,
            desired_preset_mode=None,
            desired_fan_mode=None,
            desired_swing_mode=None,
            desired_aux_heat=None,
            effective_target_temperature=23.0,  # offset-adjusted
        )
        assert "set_temperature" in corrections
        assert corrections["set_temperature"]["temperature"] == 23.0

    def test_fan_mode_correction(self) -> None:
        state = _state(HVACMode.HEAT, {"fan_mode": "low"})
        corrections = get_climate_corrections(
            underlying_state=state,
            desired_hvac_mode=None,
            desired_target_temperature=None,
            desired_target_temperature_low=None,
            desired_target_temperature_high=None,
            desired_target_humidity=None,
            desired_preset_mode=None,
            desired_fan_mode="high",
            desired_swing_mode=None,
            desired_aux_heat=None,
        )
        assert "set_fan_mode" in corrections
        assert corrections["set_fan_mode"]["fan_mode"] == "high"

    def test_multiple_corrections_at_once(self) -> None:
        state = _state(HVACMode.COOL, {"temperature": 19.0, "fan_mode": "low"})
        corrections = get_climate_corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
            desired_target_temperature_low=None,
            desired_target_temperature_high=None,
            desired_target_humidity=None,
            desired_preset_mode=None,
            desired_fan_mode="high",
            desired_swing_mode=None,
            desired_aux_heat=None,
        )
        assert "set_hvac_mode" in corrections
        assert "set_temperature" in corrections
        assert "set_fan_mode" in corrections
