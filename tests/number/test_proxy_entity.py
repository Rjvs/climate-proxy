"""Unit tests for number/proxy_entity.py — ClimateProxyNumberEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.climate_proxy.number.proxy_entity import ClimateProxyNumberEntity, ClimateProxyNumberRestoreData
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State


def _make_entity() -> ClimateProxyNumberEntity:
    """Build a ClimateProxyNumberEntity with all dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "number.test_number"
    underlying_entry.name = "Test Number"
    underlying_entry.original_name = "Test Number"

    state_manager = MagicMock()
    device_info = MagicMock()

    entity = ClimateProxyNumberEntity(
        config_entry=config_entry,
        underlying_entry=underlying_entry,
        state_manager=state_manager,
        device_info=device_info,
    )
    entity.hass = MagicMock()
    entity.hass.states.get = MagicMock(return_value=None)
    entity.hass.services.async_call = AsyncMock()
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.mark.unit
class TestClimateProxyNumberRestoreData:
    def test_round_trip_with_value(self) -> None:
        data = ClimateProxyNumberRestoreData(value=21.5)
        restored = ClimateProxyNumberRestoreData.from_dict(data.as_dict())
        assert restored._value == pytest.approx(21.5)

    def test_round_trip_with_none(self) -> None:
        data = ClimateProxyNumberRestoreData(value=None)
        restored = ClimateProxyNumberRestoreData.from_dict(data.as_dict())
        assert restored._value is None

    def test_from_dict_missing_key_returns_none(self) -> None:
        restored = ClimateProxyNumberRestoreData.from_dict({})
        assert restored._value is None


@pytest.mark.unit
class TestClimateProxyNumberEntity:
    def test_initial_desired_value_is_none(self) -> None:
        entity = _make_entity()
        assert entity.native_value is None

    def test_always_available(self) -> None:
        entity = _make_entity()
        assert entity.available is True

    def test_unique_id_includes_entry_and_entity(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "number.test_number" in entity.unique_id

    def test_get_corrections_returns_empty_when_no_desired_value(self) -> None:
        entity = _make_entity()
        state = State("number.test_number", "50.0", {})
        assert entity.get_corrections(state) == {}

    def test_get_corrections_returns_service_when_differs_beyond_tolerance(self) -> None:
        entity = _make_entity()
        entity._desired_value = 22.0
        state = State("number.test_number", "18.0", {})
        corrections = entity.get_corrections(state)
        assert "set_value" in corrections
        assert corrections["set_value"]["value"] == pytest.approx(22.0)

    def test_get_corrections_returns_empty_within_tolerance(self) -> None:
        entity = _make_entity()
        entity._desired_value = 22.0
        # 22.0 vs 22.05 → diff = 0.05 < TEMPERATURE_TOLERANCE(0.1)
        state = State("number.test_number", "22.05", {})
        assert entity.get_corrections(state) == {}

    def test_get_corrections_returns_empty_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        entity._desired_value = 22.0
        state = State("number.test_number", STATE_UNAVAILABLE, {})
        assert entity.get_corrections(state) == {}

    def test_get_corrections_returns_empty_when_underlying_unknown(self) -> None:
        entity = _make_entity()
        entity._desired_value = 22.0
        state = State("number.test_number", STATE_UNKNOWN, {})
        assert entity.get_corrections(state) == {}

    def test_get_corrections_returns_empty_for_non_numeric_state(self) -> None:
        entity = _make_entity()
        entity._desired_value = 22.0
        state = State("number.test_number", "not_a_number", {})
        assert entity.get_corrections(state) == {}

    async def test_set_native_value_updates_desired(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("number.test_number", "50.0", {}))

        await entity.async_set_native_value(75.0)

        assert entity._desired_value == pytest.approx(75.0)
        entity.async_write_ha_state.assert_called()

    async def test_set_native_value_pushes_when_available(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("number.test_number", "50.0", {}))

        await entity.async_set_native_value(75.0)

        entity.hass.services.async_call.assert_called_once()
        call_args = entity.hass.services.async_call.call_args
        assert call_args[0][0] == "number"
        assert call_args[0][1] == "set_value"

    async def test_drops_command_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("number.test_number", STATE_UNAVAILABLE, {}))

        await entity.async_set_native_value(75.0)

        entity.hass.services.async_call.assert_not_called()
        assert entity._desired_value == pytest.approx(75.0)

    def test_mirror_capabilities_sets_min_max_step(self) -> None:
        entity = _make_entity()
        state = State("number.test_number", "50.0", {"min": 0.0, "max": 100.0, "step": 0.5})
        entity._mirror_capabilities(state)
        assert entity._attr_native_min_value == pytest.approx(0.0)
        assert entity._attr_native_max_value == pytest.approx(100.0)
        assert entity._attr_native_step == pytest.approx(0.5)

    def test_mirror_capabilities_sets_unit(self) -> None:
        entity = _make_entity()
        state = State("number.test_number", "50.0", {"unit_of_measurement": "°C"})
        entity._mirror_capabilities(state)
        assert entity._attr_native_unit_of_measurement == "°C"

    def test_extra_restore_state_data_reflects_desired(self) -> None:
        entity = _make_entity()
        entity._desired_value = 42.0
        restore_data = entity.extra_restore_state_data
        assert restore_data.as_dict()["native_value"] == pytest.approx(42.0)
