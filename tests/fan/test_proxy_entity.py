"""Unit tests for fan/proxy_entity.py — ClimateProxyFanEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.climate_proxy.const import RESTORE_KEY_IS_ON, RESTORE_KEY_PERCENTAGE, RESTORE_KEY_PRESET_MODE
from custom_components.climate_proxy.fan.proxy_entity import ClimateProxyFanEntity, ClimateProxyFanRestoreData
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import State


def _make_entity() -> ClimateProxyFanEntity:
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "fan.test_fan"
    underlying_entry.name = "Test Fan"
    underlying_entry.original_name = "Test Fan"

    state_manager = MagicMock()
    device_info = MagicMock()

    return ClimateProxyFanEntity(
        config_entry=config_entry,
        underlying_entry=underlying_entry,
        state_manager=state_manager,
        device_info=device_info,
    )


@pytest.mark.unit
class TestClimateProxyFanRestoreData:
    def test_round_trip_full(self) -> None:
        data = ClimateProxyFanRestoreData(is_on=True, percentage=75, preset_mode="high")
        restored = ClimateProxyFanRestoreData.from_dict(data.as_dict())
        assert restored._is_on is True
        assert restored._percentage == 75
        assert restored._preset_mode == "high"

    def test_round_trip_defaults(self) -> None:
        data = ClimateProxyFanRestoreData(is_on=False, percentage=None, preset_mode=None)
        restored = ClimateProxyFanRestoreData.from_dict(data.as_dict())
        assert restored._is_on is False
        assert restored._percentage is None
        assert restored._preset_mode is None


@pytest.mark.unit
class TestClimateProxyFanEntity:
    def test_initial_state_is_off(self) -> None:
        entity = _make_entity()
        assert entity.is_on is False

    def test_always_available(self) -> None:
        entity = _make_entity()
        assert entity.available is True

    def test_unique_id(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "fan.test_fan" in entity.unique_id

    async def test_turn_on_uses_fan_domain(self) -> None:
        """Verify turn_on calls the 'fan' domain, not 'homeassistant'."""
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "off"))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()

        entity.hass.services.async_call.assert_called_once()
        call_args = entity.hass.services.async_call.call_args
        assert call_args[0][0] == "fan"
        assert call_args[0][1] == "turn_on"

    async def test_turn_off_uses_fan_domain(self) -> None:
        """Critical: turn_off must call fan.turn_off, not homeassistant.turn_off."""
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "on"))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_off()

        entity.hass.services.async_call.assert_called_once()
        call_args = entity.hass.services.async_call.call_args
        assert call_args[0][0] == "fan", "turn_off must use 'fan' domain, not 'homeassistant'"
        assert call_args[0][1] == "turn_off"

    async def test_turn_on_updates_desired_state(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "off"))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on(percentage=50)

        assert entity._desired_is_on is True
        assert entity._desired_percentage == 50

    async def test_turn_off_updates_desired_state(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "on"))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_off()

        assert entity._desired_is_on is False

    async def test_set_percentage_updates_desired(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "on"))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_set_percentage(75)

        assert entity._desired_percentage == 75
        assert entity._desired_is_on is True

    async def test_set_preset_mode_updates_desired(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "on"))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_set_preset_mode("auto")

        assert entity._desired_preset_mode == "auto"
        assert entity._desired_is_on is True

    def test_get_corrections_turn_on(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        state = State("fan.test_fan", "off")
        corrections = entity.get_corrections(state)
        assert "turn_on" in corrections

    def test_get_corrections_turn_off(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = False
        state = State("fan.test_fan", "on")
        corrections = entity.get_corrections(state)
        assert "turn_off" in corrections

    def test_get_corrections_percentage_change(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity._desired_percentage = 75
        state = State("fan.test_fan", "on", {"percentage": 50})
        corrections = entity.get_corrections(state)
        assert "set_percentage" in corrections
        assert corrections["set_percentage"]["percentage"] == 75

    def test_get_corrections_preset_mode_change(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity._desired_preset_mode = "auto"
        state = State("fan.test_fan", "on", {"preset_mode": "high"})
        corrections = entity.get_corrections(state)
        assert "set_preset_mode" in corrections

    def test_get_corrections_no_changes_needed(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity._desired_percentage = 50
        state = State("fan.test_fan", "on", {"percentage": 50})
        assert entity.get_corrections(state) == {}

    async def test_dropped_when_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", STATE_UNAVAILABLE))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()

        entity.hass.services.async_call.assert_not_called()

    def test_extra_restore_state_data(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity._desired_percentage = 60
        entity._desired_preset_mode = "eco"
        restore_data = entity.extra_restore_state_data.as_dict()
        assert restore_data[RESTORE_KEY_IS_ON] is True
        assert restore_data[RESTORE_KEY_PERCENTAGE] == 60
        assert restore_data[RESTORE_KEY_PRESET_MODE] == "eco"

    def test_on_underlying_state_changed_is_callback(self) -> None:
        """E1: _on_underlying_state_changed must be decorated with @callback."""
        entity = _make_entity()
        assert getattr(entity._on_underlying_state_changed, "_hass_callback", False) is True

    async def test_push_uses_target_not_entity_id_in_service_data(self) -> None:
        """E5: service calls must use target= kwarg, not entity_id in service_data."""
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "off"))
        entity.hass.services.async_call = AsyncMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_turn_on()

        call_args = entity.hass.services.async_call.call_args
        service_data = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("service_data", {})
        assert "entity_id" not in service_data
        target = call_args[1].get("target")
        assert target is not None
        assert target["entity_id"] == "fan.test_fan"
