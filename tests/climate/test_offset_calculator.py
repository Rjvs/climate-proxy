"""Unit tests for offset_calculator.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.climate_proxy.climate.offset_calculator import (
    calculate_device_setpoint,
    calculate_setpoint_range,
    calculate_weighted_average,
)
from custom_components.climate_proxy.const import CONF_SENSOR_ENTITY_ID, CONF_SENSOR_WEIGHT


@pytest.mark.unit
class TestCalculateWeightedAverage:
    """Tests for calculate_weighted_average()."""

    def _make_hass(self, states: dict[str, str]) -> MagicMock:
        """Build a minimal mock hass.states."""
        hass = MagicMock()

        def get_state(entity_id: str):
            value = states.get(entity_id)
            if value is None:
                return None
            mock_state = MagicMock()
            mock_state.state = value
            return mock_state

        hass.states.get = get_state
        return hass

    def test_single_sensor_equal_weight(self) -> None:
        hass = self._make_hass({"sensor.a": "20.0"})
        configs = [{CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0}]
        result = calculate_weighted_average(configs, hass)
        assert result == pytest.approx(20.0)

    def test_two_sensors_equal_weights(self) -> None:
        hass = self._make_hass({"sensor.a": "18.0", "sensor.b": "22.0"})
        configs = [
            {CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0},
            {CONF_SENSOR_ENTITY_ID: "sensor.b", CONF_SENSOR_WEIGHT: 1.0},
        ]
        result = calculate_weighted_average(configs, hass)
        assert result == pytest.approx(20.0)

    def test_two_sensors_unequal_weights(self) -> None:
        """Bedroom (weight=2) at 18°C, hallway (weight=1) at 24°C → expected (18*2+24*1)/3 = 20°C."""
        hass = self._make_hass({"sensor.a": "18.0", "sensor.b": "24.0"})
        configs = [
            {CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 2.0},
            {CONF_SENSOR_ENTITY_ID: "sensor.b", CONF_SENSOR_WEIGHT: 1.0},
        ]
        result = calculate_weighted_average(configs, hass)
        assert result == pytest.approx(20.0)

    def test_unavailable_sensor_skipped(self) -> None:
        """An unavailable sensor is skipped; average from remaining sensors."""
        hass = self._make_hass({"sensor.a": "unavailable", "sensor.b": "20.0"})
        configs = [
            {CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0},
            {CONF_SENSOR_ENTITY_ID: "sensor.b", CONF_SENSOR_WEIGHT: 1.0},
        ]
        result = calculate_weighted_average(configs, hass)
        assert result == pytest.approx(20.0)

    def test_all_sensors_unavailable_returns_none(self) -> None:
        hass = self._make_hass({"sensor.a": "unavailable"})
        configs = [{CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0}]
        result = calculate_weighted_average(configs, hass)
        assert result is None

    def test_missing_sensor_returns_none(self) -> None:
        hass = self._make_hass({})
        configs = [{CONF_SENSOR_ENTITY_ID: "sensor.missing", CONF_SENSOR_WEIGHT: 1.0}]
        result = calculate_weighted_average(configs, hass)
        assert result is None

    def test_non_numeric_sensor_skipped(self) -> None:
        hass = self._make_hass({"sensor.a": "unknown", "sensor.b": "21.0"})
        configs = [
            {CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 1.0},
            {CONF_SENSOR_ENTITY_ID: "sensor.b", CONF_SENSOR_WEIGHT: 1.0},
        ]
        result = calculate_weighted_average(configs, hass)
        assert result == pytest.approx(21.0)

    def test_empty_configs_returns_none(self) -> None:
        hass = self._make_hass({})
        result = calculate_weighted_average([], hass)
        assert result is None

    def test_all_sensors_entity_not_found_returns_none(self) -> None:
        """When all sensor entity_ids return None from states.get, result is None."""
        hass = MagicMock()
        hass.states.get = MagicMock(return_value=None)
        configs = [
            {CONF_SENSOR_ENTITY_ID: "sensor.missing_a", CONF_SENSOR_WEIGHT: 1.0},
            {CONF_SENSOR_ENTITY_ID: "sensor.missing_b", CONF_SENSOR_WEIGHT: 1.0},
        ]
        result = calculate_weighted_average(configs, hass)
        assert result is None

    def test_zero_weight_sensor_excluded(self) -> None:
        """A sensor with weight=0.0 contributes nothing; result comes from non-zero sensor only."""
        hass = self._make_hass({"sensor.a": "0.0", "sensor.b": "20.0"})
        configs = [
            {CONF_SENSOR_ENTITY_ID: "sensor.a", CONF_SENSOR_WEIGHT: 0.0},
            {CONF_SENSOR_ENTITY_ID: "sensor.b", CONF_SENSOR_WEIGHT: 1.0},
        ]
        result = calculate_weighted_average(configs, hass)
        assert result == pytest.approx(20.0)


@pytest.mark.unit
class TestCalculateDeviceSetpoint:
    """Tests for calculate_device_setpoint()."""

    def test_no_offset_needed(self) -> None:
        """When device sensor == external sensor, setpoint equals proxy target."""
        result = calculate_device_setpoint(
            proxy_target=21.0,
            device_internal_temp=21.0,
            external_temp=21.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        assert result == pytest.approx(21.0)

    def test_positive_offset(self) -> None:
        """Device reads warmer than external sensor — increase setpoint sent to device."""
        # Device reads 23°C, external reads 20°C, offset=3
        # User wants external to reach 22°C → device_setpoint = 22 + 3 = 25
        result = calculate_device_setpoint(
            proxy_target=22.0,
            device_internal_temp=23.0,
            external_temp=20.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        assert result == pytest.approx(25.0)

    def test_negative_offset(self) -> None:
        """Device reads cooler than external sensor — reduce setpoint sent to device."""
        # Device reads 18°C, external reads 20°C, offset=-2
        # User wants external to reach 22°C → device_setpoint = 22 + (-2) = 20
        result = calculate_device_setpoint(
            proxy_target=22.0,
            device_internal_temp=18.0,
            external_temp=20.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        assert result == pytest.approx(20.0)

    def test_clamp_to_max(self) -> None:
        """Offset-adjusted setpoint above max_temp is clamped to max_temp."""
        # Device reads 30°C, external reads 10°C, offset=20
        # User wants external to reach 22°C → raw setpoint = 22 + 20 = 42 → clamped to 35
        result = calculate_device_setpoint(
            proxy_target=22.0,
            device_internal_temp=30.0,
            external_temp=10.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        assert result == pytest.approx(35.0)

    def test_clamp_to_min(self) -> None:
        """Offset-adjusted setpoint below min_temp is clamped to min_temp."""
        # Device reads 5°C, external reads 25°C, offset=-20
        # User wants external to reach 18°C → raw setpoint = 18 + (-20) = -2 → clamped to 7
        result = calculate_device_setpoint(
            proxy_target=18.0,
            device_internal_temp=5.0,
            external_temp=25.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        assert result == pytest.approx(7.0)

    def test_result_within_bounds_not_clamped(self) -> None:
        """When result is within [min, max], it is returned unchanged."""
        result = calculate_device_setpoint(
            proxy_target=20.0,
            device_internal_temp=22.0,
            external_temp=20.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        assert result == pytest.approx(22.0)
        assert 7.0 <= result <= 35.0

    def test_exact_boundary_min_not_clamped(self) -> None:
        """Result exactly equal to min_temp is not altered."""
        result = calculate_device_setpoint(
            proxy_target=7.0,
            device_internal_temp=7.0,
            external_temp=7.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        assert result == pytest.approx(7.0)

    def test_exact_boundary_max_not_clamped(self) -> None:
        """Result exactly equal to max_temp is not altered."""
        result = calculate_device_setpoint(
            proxy_target=35.0,
            device_internal_temp=35.0,
            external_temp=35.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        assert result == pytest.approx(35.0)


@pytest.mark.unit
class TestCalculateSetpointRange:
    """Tests for calculate_setpoint_range()."""

    def test_range_with_offset(self) -> None:
        """Range setpoints are offset-adjusted by the same amount."""
        low, high = calculate_setpoint_range(
            proxy_target_low=18.0,
            proxy_target_high=22.0,
            device_internal_temp=23.0,
            external_temp=20.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        # offset = 23 - 20 = 3
        assert low == pytest.approx(21.0)
        assert high == pytest.approx(25.0)

    def test_range_clamp_high_to_max(self) -> None:
        """High bound is clamped to max_temp when offset pushes it over."""
        low, high = calculate_setpoint_range(
            proxy_target_low=20.0,
            proxy_target_high=28.0,
            device_internal_temp=30.0,
            external_temp=15.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        # offset = 30 - 15 = 15 → low=35 (clamped), high=43 (clamped to 35)
        assert low == pytest.approx(35.0)
        assert high == pytest.approx(35.0)

    def test_range_clamp_low_to_min(self) -> None:
        """Low bound is clamped to min_temp when offset pulls it below."""
        low, high = calculate_setpoint_range(
            proxy_target_low=10.0,
            proxy_target_high=14.0,
            device_internal_temp=5.0,
            external_temp=25.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        # offset = 5 - 25 = -20 → low=-10 (clamped to 7), high=-6 (clamped to 7)
        assert low == pytest.approx(7.0)
        assert high == pytest.approx(7.0)

    def test_range_no_offset_identity(self) -> None:
        """When device internal temp equals external temp, range is unchanged."""
        low, high = calculate_setpoint_range(
            proxy_target_low=18.0,
            proxy_target_high=24.0,
            device_internal_temp=20.0,
            external_temp=20.0,
            min_temp=7.0,
            max_temp=35.0,
        )
        assert low == pytest.approx(18.0)
        assert high == pytest.approx(24.0)
