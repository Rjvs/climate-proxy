"""Unit tests for enforcement.py."""

from __future__ import annotations

import pytest

from custom_components.climate_proxy.climate.enforcement import get_climate_corrections
from custom_components.climate_proxy.const import HUMIDITY_TOLERANCE, TEMPERATURE_TOLERANCE
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


@pytest.mark.unit
class TestToleranceBoundaries:
    """Tests confirming tolerance boundary semantics (strictly greater than, not >=)."""

    def test_temperature_exactly_at_tolerance_no_correction(self) -> None:
        """A deviation exactly equal to TEMPERATURE_TOLERANCE must NOT trigger correction."""
        actual = 21.0 + TEMPERATURE_TOLERANCE  # abs(diff) == TEMPERATURE_TOLERANCE
        state = _state(HVACMode.HEAT, {"temperature": actual})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
        )
        assert "set_temperature" not in result

    def test_temperature_just_above_tolerance_correction(self) -> None:
        """A deviation just above TEMPERATURE_TOLERANCE must trigger correction."""
        actual = 21.0 + TEMPERATURE_TOLERANCE + 0.001
        state = _state(HVACMode.HEAT, {"temperature": actual})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
        )
        assert "set_temperature" in result

    def test_humidity_exactly_at_tolerance_no_correction(self) -> None:
        """A deviation exactly equal to HUMIDITY_TOLERANCE must NOT trigger correction."""
        actual = 50.0 + HUMIDITY_TOLERANCE
        state = _state(HVACMode.HEAT, {"humidity": actual})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_humidity=50.0,
        )
        assert "set_humidity" not in result

    def test_humidity_just_above_tolerance_correction(self) -> None:
        """A deviation just above HUMIDITY_TOLERANCE must trigger correction."""
        actual = 50.0 + HUMIDITY_TOLERANCE + 0.001
        state = _state(HVACMode.HEAT, {"humidity": actual})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_humidity=50.0,
        )
        assert "set_humidity" in result


@pytest.mark.unit
class TestNonNumericAttributes:
    """Tests for robustness against non-numeric device attribute values."""

    def test_non_numeric_actual_temp_forces_correction(self) -> None:
        """Non-numeric temperature attribute must not crash and must trigger correction."""
        state = _state(HVACMode.HEAT, {"temperature": "n/a"})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
        )
        assert "set_temperature" in result

    def test_non_numeric_actual_low_forces_range_correction(self) -> None:
        """Non-numeric target_temp_low must trigger range correction without crashing."""
        state = _state(HVACMode.HEAT_COOL, {"target_temp_low": "error", "target_temp_high": 24.0})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT_COOL,
            desired_target_temperature_low=18.0,
            desired_target_temperature_high=24.0,
        )
        assert "set_temperature" in result

    def test_non_numeric_actual_humidity_forces_correction(self) -> None:
        """Non-numeric humidity attribute must trigger correction without crashing."""
        state = _state(HVACMode.HEAT, {"humidity": "unavailable"})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_humidity=50.0,
        )
        assert "set_humidity" in result


@pytest.mark.unit
class TestNoneUnderlyingAttributes:
    """Tests for corrections when underlying entity lacks an attribute entirely."""

    def test_preset_correction_when_actual_preset_is_none(self) -> None:
        """No preset_mode key in attrs should trigger correction."""
        state = _state(HVACMode.HEAT, {})
        result = _corrections(underlying_state=state, desired_preset_mode="eco")
        assert "set_preset_mode" in result

    def test_fan_correction_when_actual_fan_is_none(self) -> None:
        """No fan_mode key in attrs should trigger correction."""
        state = _state(HVACMode.HEAT, {})
        result = _corrections(underlying_state=state, desired_fan_mode="auto")
        assert "set_fan_mode" in result

    def test_swing_correction_when_actual_swing_is_none(self) -> None:
        """No swing_mode key in attrs should trigger correction."""
        state = _state(HVACMode.HEAT, {})
        result = _corrections(underlying_state=state, desired_swing_mode="on")
        assert "set_swing_mode" in result


@pytest.mark.unit
class TestAllCorrectionsSimultaneously:
    def test_all_seven_corrections_at_once(self) -> None:
        """When all desired values deviate from underlying, all 7 service keys are returned."""
        state = _state(
            HVACMode.COOL,
            {
                "temperature": 19.0,
                "humidity": 30.0,
                "fan_mode": "low",
                "preset_mode": "none",
                "swing_mode": "off",
                "swing_horizontal_mode": "off",
            },
        )
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT,
            desired_target_temperature=21.0,
            desired_target_humidity=50.0,
            desired_fan_mode="high",
            desired_preset_mode="eco",
            desired_swing_mode="on",
            desired_swing_horizontal_mode="left_right",
        )
        assert "set_hvac_mode" in result
        assert "set_temperature" in result
        assert "set_humidity" in result
        assert "set_fan_mode" in result
        assert "set_preset_mode" in result
        assert "set_swing_mode" in result
        assert "set_swing_horizontal_mode" in result


@pytest.mark.unit
class TestEffectiveRangeCorrection:
    def test_eff_low_and_high_provided_uses_effective_range(self) -> None:
        """When effective range values differ from desired, they are used for corrections."""
        state = _state(HVACMode.HEAT_COOL, {"target_temp_low": 18.0, "target_temp_high": 24.0})
        result = _corrections(
            underlying_state=state,
            desired_hvac_mode=HVACMode.HEAT_COOL,
            desired_target_temperature_low=18.0,
            desired_target_temperature_high=24.0,
            effective_target_low=20.0,   # offset-adjusted
            effective_target_high=26.0,  # offset-adjusted
        )
        assert "set_temperature" in result
        assert result["set_temperature"]["target_temp_low"] == 20.0
        assert result["set_temperature"]["target_temp_high"] == 26.0
