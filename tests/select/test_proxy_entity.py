"""Unit tests for select/proxy_entity.py — ClimateProxySelectEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.climate_proxy.select.proxy_entity import ClimateProxySelectEntity, ClimateProxySelectRestoreData
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import State


def _make_entity() -> ClimateProxySelectEntity:
    """Build a ClimateProxySelectEntity with all dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "select.test_select"
    underlying_entry.name = "Test Select"
    underlying_entry.original_name = "Test Select"

    state_manager = MagicMock()
    device_info = MagicMock()

    entity = ClimateProxySelectEntity(
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
class TestClimateProxySelectRestoreData:
    def test_round_trip_with_option(self) -> None:
        data = ClimateProxySelectRestoreData(option="eco")
        restored = ClimateProxySelectRestoreData.from_dict(data.as_dict())
        assert restored._option == "eco"

    def test_round_trip_with_none(self) -> None:
        data = ClimateProxySelectRestoreData(option=None)
        restored = ClimateProxySelectRestoreData.from_dict(data.as_dict())
        assert restored._option is None

    def test_from_dict_missing_key_returns_none(self) -> None:
        restored = ClimateProxySelectRestoreData.from_dict({})
        assert restored._option is None


@pytest.mark.unit
class TestClimateProxySelectEntity:
    def test_initial_desired_option_is_none(self) -> None:
        entity = _make_entity()
        assert entity.current_option is None

    def test_always_available(self) -> None:
        entity = _make_entity()
        assert entity.available is True

    def test_unique_id_includes_entry_and_entity(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "select.test_select" in entity.unique_id

    def test_get_corrections_returns_empty_when_no_desired_option(self) -> None:
        entity = _make_entity()
        state = State("select.test_select", "heat", {"options": ["heat", "cool"]})
        assert entity.get_corrections(state) == {}

    def test_get_corrections_returns_service_call_when_different(self) -> None:
        entity = _make_entity()
        entity._desired_option = "eco"
        state = State("select.test_select", "comfort", {"options": ["comfort", "eco"]})
        corrections = entity.get_corrections(state)
        assert "select_option" in corrections
        assert corrections["select_option"]["option"] == "eco"

    def test_get_corrections_returns_empty_when_already_correct(self) -> None:
        entity = _make_entity()
        entity._desired_option = "eco"
        state = State("select.test_select", "eco", {"options": ["comfort", "eco"]})
        assert entity.get_corrections(state) == {}

    def test_get_corrections_updates_options_list(self) -> None:
        entity = _make_entity()
        entity._desired_option = "eco"
        options = ["comfort", "eco", "away"]
        state = State("select.test_select", "comfort", {"options": options})
        entity.get_corrections(state)
        assert entity._attr_options == options

    async def test_select_option_updates_desired_state(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("select.test_select", "comfort", {}))

        await entity.async_select_option("eco")

        assert entity._desired_option == "eco"
        entity.async_write_ha_state.assert_called()

    async def test_select_option_pushes_service_when_available(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("select.test_select", "comfort", {}))

        await entity.async_select_option("eco")

        entity.hass.services.async_call.assert_called_once()
        call_args = entity.hass.services.async_call.call_args
        assert call_args[0][0] == "select"
        assert call_args[0][1] == "select_option"

    async def test_drops_command_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("select.test_select", STATE_UNAVAILABLE, {}))

        await entity.async_select_option("eco")

        entity.hass.services.async_call.assert_not_called()
        # Desired state is still stored even if push is dropped
        assert entity._desired_option == "eco"

    def test_extra_restore_state_data_reflects_desired(self) -> None:
        entity = _make_entity()
        entity._desired_option = "away"
        restore_data = entity.extra_restore_state_data
        assert restore_data.as_dict()["current_option"] == "away"
