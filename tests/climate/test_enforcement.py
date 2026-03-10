"""Unit tests for enforcement.py."""

from __future__ import annotations

import pytest

from custom_components.climate_proxy.climate.enforcement import get_climate_corrections
from homeassistant.components.climate import HVACMode
from homeassistant.core import State


def _state(hvac_mode: str, attrs: dict) -> State:
    return State("climate.test", hvac_mode, attributes=attrs)


def _corrections(
    *,
    underlying_state: State,
    desired_hvac_mode: HVACMode | None = None,
    desired_target_temperature: float | None = None,
    desired_target_temperature_low: float | None = None,
    desired_target_temperature_high: float | None = None,
    desired_target_humidity: float | None = None,
    desired_preset_mode: str | None = None,
    desired_fan_mode: str | None = None,
    desired_swing_mode: str | None = None,
    desired_swing_horizontal_mode: str | None = None,
    effective_target_temperature: float | None = None,
    effective_target_low: float | None = None,
    effective_target_high: float | None = None,
) -> dict:
    """Thin wrapper to avoid repeating all None defaults in every test."""
    return get_climate_corrections(
        underlying_state=underlying_state,
        desired_hvac_mode=desired_hvac_mode,
        desired_target_temperature=desired_target_temperature,
        desired_target_temperature_low=desired_target_temperature_low,
        desired_target_temperature_high=desired_target_temperature_high,
        desired_target_humidity=desired_target_humidity,
        desired_preset_mode=desired_preset_mode,
        desired_fan_mode=desired_fan_mode,
        desired_swing_mode=desired_swing_mode,
        desired_swing_horizontal_mode=desired_swing_horizontal_mode,
        effective_target_temperature=effective_target_temperature,
        effective_target_low=effective_target_low,
        effective_target_high=effective_target_high,
    )


@pytest.mark.unit
class TestGetClimateCorrections:
    def test_no_corrections_needed(self) -> None:
        """When underlying state matches desired state, no corrections returned."""
        state = _state(HVACMode.HEAT, {"temperature": 21.0})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
        )
        assert result == {}

    def test_hvac_mode_correction(self) -> None:
        state = _state(HVACMode.COOL, {})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
        )
        assert "set_hvac_mode" in result
        assert result["set_hvac_mode"]["hvac_mode"] == HVACMode.HEAT

    def test_temperature_correction(self) -> None:
        state = _state(HVACMode.HEAT, {"temperature": 19.0})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
        )
        assert "set_temperature" in result
        assert result["set_temperature"]["temperature"] == 21.0

    def test_temperature_within_tolerance_no_correction(self) -> None:
        """A deviation within TEMPERATURE_TOLERANCE should not trigger correction."""
        state = _state(HVACMode.HEAT, {"temperature": 21.05})  # within 0.1°C tolerance
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
        )
        assert "set_temperature" not in result

    def test_effective_temperature_overrides_desired(self) -> None:
        """When effective_target_temperature is provided, it is used for corrections."""
        state = _state(HVACMode.HEAT, {"temperature": 21.0})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=20.0,
            effective_target_temperature=23.0,  # offset-adjusted
        )
        assert "set_temperature" in result
        assert result["set_temperature"]["temperature"] == 23.0

    def test_fan_mode_correction(self) -> None:
        state = _state(HVACMode.HEAT, {"fan_mode": "low"})
        result = _corrections(underlying_state=state, desired_fan_mode="high")
        assert "set_fan_mode" in result
        assert result["set_fan_mode"]["fan_mode"] == "high"

    def test_multiple_corrections_at_once(self) -> None:
        state = _state(HVACMode.COOL, {"temperature": 19.0, "fan_mode": "low"})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
            desired_fan_mode="high",
        )
        assert "set_hvac_mode" in result
        assert "set_temperature" in result
        assert "set_fan_mode" in result

    # ------------------------------------------------------------------
    # B2: OFF mode guard tests
    # ------------------------------------------------------------------

    def test_temperature_not_enforced_when_mode_is_off(self) -> None:
        """When desired HVAC mode is OFF, temperature corrections must be skipped."""
        state = _state(HVACMode.OFF, {"temperature": 15.0})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.OFF,
            desired_target_temperature=22.0,
        )
        assert "set_temperature" not in result
        # Mode correction itself is also not needed (already OFF)
        assert "set_hvac_mode" not in result

    def test_temperature_range_not_enforced_when_mode_is_off(self) -> None:
        """Temperature range corrections must be skipped when desired mode is OFF."""
        state = _state(HVACMode.OFF, {"target_temp_low": 18.0, "target_temp_high": 24.0})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.OFF,
            desired_target_temperature_low=20.0,
            desired_target_temperature_high=26.0,
        )
        assert "set_temperature" not in result

    def test_humidity_not_enforced_when_mode_is_off(self) -> None:
        """Humidity corrections must be skipped when desired mode is OFF."""
        state = _state(HVACMode.OFF, {"humidity": 30})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.OFF,
            desired_target_humidity=50.0,
        )
        assert "set_humidity" not in result

    def test_hvac_mode_correction_still_applied_when_transitioning_to_off(self) -> None:
        """HVAC mode correction (to OFF) is still applied even when desired is OFF."""
        state = _state(HVACMode.HEAT, {"temperature": 22.0})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.OFF,
            desired_target_temperature=22.0,
        )
        assert "set_hvac_mode" in result
        assert result["set_hvac_mode"]["hvac_mode"] == HVACMode.OFF
        assert "set_temperature" not in result

    def test_preset_mode_still_enforced_when_mode_is_off(self) -> None:
        """Non-temperature/humidity corrections are still applied when desired mode is OFF."""
        state = _state(HVACMode.OFF, {"preset_mode": "none"})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.OFF,
            desired_preset_mode="away",
        )
        assert "set_preset_mode" in result
