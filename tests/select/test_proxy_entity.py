"""Unit tests for select/proxy_entity.py — ClimateProxySelectEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.climate_proxy.const import RESTORE_KEY_CURRENT_OPTION
from custom_components.climate_proxy.select.proxy_entity import ClimateProxySelectEntity, ClimateProxySelectRestoreData
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import State


def _make_entity() -> ClimateProxySelectEntity:
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "select.test_select"
    underlying_entry.name = "Test Select"
    underlying_entry.original_name = "Test Select"

    state_manager = MagicMock()
    device_info = MagicMock()

    return ClimateProxySelectEntity(
        config_entry=config_entry,
        underlying_entry=underlying_entry,
        state_manager=state_manager,
        device_info=device_info,
    )


@pytest.mark.unit
class TestClimateProxySelectRestoreData:
    def test_as_dict_round_trip(self) -> None:
        data = ClimateProxySelectRestoreData(option="eco")
        restored = ClimateProxySelectRestoreData.from_dict(data.as_dict())
        assert restored._option == "eco"

    def test_none_option(self) -> None:
        data = ClimateProxySelectRestoreData(option=None)
        restored = ClimateProxySelectRestoreData.from_dict(data.as_dict())
        assert restored._option is None


@pytest.mark.unit
class TestClimateProxySelectEntity:
    def test_initial_state_is_none(self) -> None:
        entity = _make_entity()
        assert entity.current_option is None

    def test_always_available(self) -> None:
        entity = _make_entity()
        assert entity.available is True

    def test_unique_id_includes_entry_and_entity(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "select.test_select" in entity.unique_id

    def test_get_corrections_when_option_differs(self) -> None:
        entity = _make_entity()
        entity._desired_option = "eco"
        state = State("select.test_select", "comfort", {"options": ["eco", "comfort"]})
        corrections = entity.get_corrections(state)
        assert "select_option" in corrections
        assert corrections["select_option"]["option"] == "eco"

    def test_get_corrections_when_option_matches(self) -> None:
        entity = _make_entity()
        entity._desired_option = "eco"
        state = State("select.test_select", "eco", {"options": ["eco", "comfort"]})
        assert entity.get_corrections(state) == {}

    def test_get_corrections_when_no_desired_option(self) -> None:
        entity = _make_entity()
        entity._desired_option = None
        state = State("select.test_select", "eco", {"options": ["eco", "comfort"]})
        assert entity.get_corrections(state) == {}

    def test_get_corrections_mirrors_options_list(self) -> None:
        entity = _make_entity()
        entity._desired_option = "eco"
        state = State("select.test_select", "eco", {"options": ["eco", "comfort", "away"]})
        entity.get_corrections(state)
        assert entity._attr_options == ["eco", "comfort", "away"]

    async def test_select_option_updates_desired_state(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("select.test_select", "comfort", {"options": ["eco", "comfort"]})
        )
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("eco")

        assert entity._desired_option == "eco"
        entity.async_write_ha_state.assert_called_once()

    async def test_dropped_when_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("select.test_select", STATE_UNAVAILABLE))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("eco")

        entity.hass.services.async_call.assert_not_called()

    def test_extra_restore_state_data_reflects_desired(self) -> None:
        entity = _make_entity()
        entity._desired_option = "away"
        restore_data = entity.extra_restore_state_data
        assert restore_data.as_dict()[RESTORE_KEY_CURRENT_OPTION] == "away"

    def test_on_underlying_state_changed_is_callback(self) -> None:
        """E1: _on_underlying_state_changed must be decorated with @callback."""
        entity = _make_entity()
        assert getattr(entity._on_underlying_state_changed, "_hass_callback", False) is True

    async def test_push_uses_target_not_entity_id_in_service_data(self) -> None:
        """E5: service calls must use target= kwarg, not entity_id in service_data."""
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("select.test_select", "comfort", {"options": ["eco", "comfort"]})
        )
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_select_option("eco")

        call_args = entity.hass.services.async_call.call_args
        service_data = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("service_data", {})
        assert "entity_id" not in service_data
        target = call_args[1].get("target")
        assert target is not None
        assert target["entity_id"] == "select.test_select"
