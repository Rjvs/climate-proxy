"""Unit tests for number/proxy_entity.py — ClimateProxyNumberEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State

from custom_components.climate_proxy.number.proxy_entity import (
    ClimateProxyNumberEntity,
    ClimateProxyNumberRestoreData,
)
from custom_components.climate_proxy.const import NUMBER_TOLERANCE, RESTORE_KEY_NATIVE_VALUE


def _make_entity() -> ClimateProxyNumberEntity:
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "number.test_number"
    underlying_entry.name = "Test Number"
    underlying_entry.original_name = "Test Number"

    state_manager = MagicMock()
    device_info = MagicMock()

    return ClimateProxyNumberEntity(
        config_entry=config_entry,
        underlying_entry=underlying_entry,
        state_manager=state_manager,
        device_info=device_info,
    )


@pytest.mark.unit
class TestClimateProxyNumberRestoreData:
    def test_round_trip_with_value(self) -> None:
        data = ClimateProxyNumberRestoreData(value=42.5)
        restored = ClimateProxyNumberRestoreData.from_dict(data.as_dict())
        assert restored._value == pytest.approx(42.5)

    def test_round_trip_none(self) -> None:
        data = ClimateProxyNumberRestoreData(value=None)
        restored = ClimateProxyNumberRestoreData.from_dict(data.as_dict())
        assert restored._value is None


@pytest.mark.unit
class TestClimateProxyNumberEntity:
    def test_initial_value_is_none(self) -> None:
        entity = _make_entity()
        assert entity.native_value is None

    def test_always_available(self) -> None:
        entity = _make_entity()
        assert entity.available is True

    def test_unique_id(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "number.test_number" in entity.unique_id

    def test_get_corrections_when_value_differs_beyond_tolerance(self) -> None:
        entity = _make_entity()
        entity._desired_value = 50.0
        state = State("number.test_number", "45.0")
        corrections = entity.get_corrections(state)
        assert "set_value" in corrections
        assert corrections["set_value"]["value"] == 50.0

    def test_get_corrections_within_tolerance_no_correction(self) -> None:
        entity = _make_entity()
        entity._desired_value = 50.0
        # Within NUMBER_TOLERANCE (0.01)
        state = State("number.test_number", "50.005")
        assert entity.get_corrections(state) == {}

    def test_get_corrections_when_no_desired_value(self) -> None:
        entity = _make_entity()
        entity._desired_value = None
        state = State("number.test_number", "50.0")
        assert entity.get_corrections(state) == {}

    def test_get_corrections_when_unavailable(self) -> None:
        entity = _make_entity()
        entity._desired_value = 50.0
        state = State("number.test_number", STATE_UNAVAILABLE)
        assert entity.get_corrections(state) == {}

    def test_get_corrections_when_unknown(self) -> None:
        entity = _make_entity()
        entity._desired_value = 50.0
        state = State("number.test_number", STATE_UNKNOWN)
        assert entity.get_corrections(state) == {}

    def test_mirror_capabilities_from_state(self) -> None:
        entity = _make_entity()
        state = State(
            "number.test_number",
            "50.0",
            {"min": 0, "max": 100, "step": 5.0, "unit_of_measurement": "%"},
        )
        entity._mirror_capabilities(state)
        assert entity._attr_native_min_value == 0.0
        assert entity._attr_native_max_value == 100.0
        assert entity._attr_native_step == 5.0
        assert entity._attr_native_unit_of_measurement == "%"

    async def test_set_native_value_updates_desired(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("number.test_number", "45.0")
        )
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_set_native_value(75.0)

        assert entity._desired_value == 75.0
        entity.async_write_ha_state.assert_called_once()
        entity.hass.services.async_call.assert_called_once()

    async def test_dropped_when_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("number.test_number", STATE_UNAVAILABLE)
        )
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_set_native_value(75.0)

        entity.hass.services.async_call.assert_not_called()

    def test_extra_restore_state_data_reflects_desired(self) -> None:
        entity = _make_entity()
        entity._desired_value = 33.0
        restore_data = entity.extra_restore_state_data
        assert restore_data.as_dict()[RESTORE_KEY_NATIVE_VALUE] == 33.0
