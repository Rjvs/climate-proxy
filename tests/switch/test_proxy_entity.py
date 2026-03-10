"""Unit tests for switch/proxy_entity.py — ClimateProxySwitchEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.climate_proxy.switch.proxy_entity import ClimateProxySwitchEntity, ClimateProxySwitchRestoreData
from homeassistant.core import State


def _make_entity() -> ClimateProxySwitchEntity:
    """Build a ClimateProxySwitchEntity with all dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "switch.test_switch"
    underlying_entry.name = "Test Switch"
    underlying_entry.original_name = "Test Switch"

    state_manager = MagicMock()
    device_info = MagicMock()

    return ClimateProxySwitchEntity(
        config_entry=config_entry,
        underlying_entry=underlying_entry,
        state_manager=state_manager,
        device_info=device_info,
    )


@pytest.mark.unit
class TestClimateProxySwitchRestoreData:
    def test_as_dict_round_trip(self) -> None:
        data = ClimateProxySwitchRestoreData(is_on=True)
        restored = ClimateProxySwitchRestoreData.from_dict(data.as_dict())
        assert restored._is_on is True

    def test_as_dict_round_trip_off(self) -> None:
        data = ClimateProxySwitchRestoreData(is_on=False)
        restored = ClimateProxySwitchRestoreData.from_dict(data.as_dict())
        assert restored._is_on is False

    def test_from_dict_missing_key_defaults_false(self) -> None:
        restored = ClimateProxySwitchRestoreData.from_dict({})
        assert restored._is_on is False


@pytest.mark.unit
class TestClimateProxySwitchEntity:
    def test_initial_desired_state_is_off(self) -> None:
        entity = _make_entity()
        assert entity.is_on is False

    def test_is_always_available(self) -> None:
        entity = _make_entity()
        assert entity.available is True

    def test_unique_id_includes_entry_and_entity(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "switch.test_switch" in entity.unique_id

    def test_get_corrections_turn_on_when_desired_on_but_actually_off(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        state = State("switch.test_switch", "off")
        corrections = entity.get_corrections(state)
        assert "turn_on" in corrections

    def test_get_corrections_turn_off_when_desired_off_but_actually_on(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = False
        state = State("switch.test_switch", "on")
        corrections = entity.get_corrections(state)
        assert "turn_off" in corrections

    def test_get_corrections_no_correction_when_already_on(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        state = State("switch.test_switch", "on")
        assert entity.get_corrections(state) == {}

    def test_get_corrections_no_correction_when_already_off(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = False
        state = State("switch.test_switch", "off")
        assert entity.get_corrections(state) == {}

    async def test_turn_on_updates_desired_state(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("switch.test_switch", "off"))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()

        assert entity._desired_is_on is True
        entity.async_write_ha_state.assert_called_once()

    async def test_turn_off_updates_desired_state(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("switch.test_switch", "on"))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_off()

        assert entity._desired_is_on is False
        entity.async_write_ha_state.assert_called_once()

    async def test_push_uses_switch_domain(self) -> None:
        """push_or_queue calls the 'switch' domain, not 'homeassistant'."""
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("switch.test_switch", "off"))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()

        entity.hass.services.async_call.assert_called_once()
        call_args = entity.hass.services.async_call.call_args
        assert call_args[0][0] == "switch"

    async def test_dropped_command_when_unavailable_no_queue(self) -> None:
        """When underlying is unavailable, no state_manager.queue_pending_state call."""
        from homeassistant.const import STATE_UNAVAILABLE

        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("switch.test_switch", STATE_UNAVAILABLE))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()

        entity.hass.services.async_call.assert_not_called()
        entity._state_manager.queue_pending_state.assert_not_called()

    def test_extra_restore_state_data_reflects_desired(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        restore_data = entity.extra_restore_state_data
        assert restore_data.as_dict()["is_on"] is True
