"""Unit tests for fan/proxy_entity.py — ClimateProxyFanEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.climate_proxy.fan.proxy_entity import ClimateProxyFanEntity, ClimateProxyFanRestoreData
from homeassistant.components.fan import FanEntityFeature
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import State


def _make_entity() -> ClimateProxyFanEntity:
    """Build a ClimateProxyFanEntity with all dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "fan.test_fan"
    underlying_entry.name = "Test Fan"
    underlying_entry.original_name = "Test Fan"

    state_manager = MagicMock()
    device_info = MagicMock()

    entity = ClimateProxyFanEntity(
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
class TestClimateProxyFanRestoreData:
    def test_round_trip(self) -> None:
        data = ClimateProxyFanRestoreData(is_on=True, percentage=75, preset_mode="turbo")
        restored = ClimateProxyFanRestoreData.from_dict(data.as_dict())
        assert restored._is_on is True
        assert restored._percentage == 75
        assert restored._preset_mode == "turbo"

    def test_round_trip_with_none_values(self) -> None:
        data = ClimateProxyFanRestoreData(is_on=False, percentage=None, preset_mode=None)
        restored = ClimateProxyFanRestoreData.from_dict(data.as_dict())
        assert restored._is_on is False
        assert restored._percentage is None
        assert restored._preset_mode is None

    def test_from_dict_missing_keys_uses_defaults(self) -> None:
        restored = ClimateProxyFanRestoreData.from_dict({})
        assert restored._is_on is False
        assert restored._percentage is None
        assert restored._preset_mode is None


@pytest.mark.unit
class TestClimateProxyFanEntity:
    def test_initial_desired_state_is_off(self) -> None:
        entity = _make_entity()
        assert entity.is_on is False
        assert entity.percentage is None
        assert entity.preset_mode is None

    def test_always_available(self) -> None:
        entity = _make_entity()
        assert entity.available is True

    def test_unique_id_includes_entry_and_entity(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "fan.test_fan" in entity.unique_id

    async def test_turn_on_updates_desired_state(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "off", {}))

        await entity.async_turn_on()

        assert entity._desired_is_on is True
        entity.async_write_ha_state.assert_called()

    async def test_turn_on_with_percentage(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "off", {}))

        await entity.async_turn_on(percentage=75)

        assert entity._desired_is_on is True
        assert entity._desired_percentage == 75

    async def test_turn_on_with_preset_mode(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "off", {}))

        await entity.async_turn_on(preset_mode="turbo")

        assert entity._desired_is_on is True
        assert entity._desired_preset_mode == "turbo"

    async def test_turn_on_uses_fan_domain(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "off", {}))

        await entity.async_turn_on()

        entity.hass.services.async_call.assert_called_once()
        call_args = entity.hass.services.async_call.call_args
        assert call_args[0][0] == "fan"
        assert call_args[0][1] == "turn_on"

    async def test_turn_off_updates_desired_state(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "on", {}))

        await entity.async_turn_off()

        assert entity._desired_is_on is False
        entity.async_write_ha_state.assert_called()

    async def test_turn_off_uses_fan_domain(self) -> None:
        """turn_off must use 'fan' domain, not 'homeassistant'."""
        entity = _make_entity()
        entity._desired_is_on = True
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "on", {}))

        await entity.async_turn_off()

        entity.hass.services.async_call.assert_called_once()
        call_args = entity.hass.services.async_call.call_args
        assert call_args[0][0] == "fan"
        assert call_args[0][1] == "turn_off"

    async def test_set_percentage_updates_desired(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "on", {}))

        await entity.async_set_percentage(50)

        assert entity._desired_percentage == 50
        assert entity._desired_is_on is True

    async def test_set_percentage_zero_does_not_force_off(self) -> None:
        """Setting percentage to 0 doesn't flip desired_is_on True."""
        entity = _make_entity()
        entity._desired_is_on = False
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "on", {}))

        await entity.async_set_percentage(0)

        assert entity._desired_percentage == 0

    async def test_set_preset_mode_updates_desired(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", "on", {}))

        await entity.async_set_preset_mode("turbo")

        assert entity._desired_preset_mode == "turbo"
        assert entity._desired_is_on is True

    async def test_drops_command_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("fan.test_fan", STATE_UNAVAILABLE, {}))

        await entity.async_turn_on()

        entity.hass.services.async_call.assert_not_called()
        assert entity._desired_is_on is True  # desired is still updated

    def test_get_corrections_turn_on_when_desired_on_but_off(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        state = State("fan.test_fan", "off", {})
        corrections = entity.get_corrections(state)
        assert "turn_on" in corrections

    def test_get_corrections_turn_off_when_desired_off_but_on(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = False
        state = State("fan.test_fan", "on", {})
        corrections = entity.get_corrections(state)
        assert "turn_off" in corrections

    def test_get_corrections_no_correction_when_states_match(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = False
        state = State("fan.test_fan", "off", {})
        assert entity.get_corrections(state) == {}

    def test_get_corrections_set_percentage_when_differs(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity._desired_percentage = 75
        state = State("fan.test_fan", "on", {"percentage": 50})
        corrections = entity.get_corrections(state)
        assert "set_percentage" in corrections
        assert corrections["set_percentage"]["percentage"] == 75

    def test_get_corrections_set_preset_when_differs(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity._desired_preset_mode = "turbo"
        state = State("fan.test_fan", "on", {"preset_mode": "auto"})
        corrections = entity.get_corrections(state)
        assert "set_preset_mode" in corrections

    def test_get_corrections_no_speed_correction_when_percentage_matches(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity._desired_percentage = 75
        state = State("fan.test_fan", "on", {"percentage": 75})
        corrections = entity.get_corrections(state)
        assert "set_percentage" not in corrections

    def test_mirror_capabilities_detects_speed_support(self) -> None:
        entity = _make_entity()
        state = State("fan.test_fan", "on", {"percentage": 50})
        entity._mirror_capabilities(state)
        assert FanEntityFeature.SET_SPEED in entity._attr_supported_features

    def test_mirror_capabilities_detects_preset_support(self) -> None:
        entity = _make_entity()
        state = State(
            "fan.test_fan",
            "on",
            {"preset_modes": ["auto", "turbo"]},
        )
        entity._mirror_capabilities(state)
        assert FanEntityFeature.PRESET_MODE in entity._attr_supported_features
        assert entity._attr_preset_modes == ["auto", "turbo"]

    def test_extra_restore_state_data_reflects_desired(self) -> None:
        entity = _make_entity()
        entity._desired_is_on = True
        entity._desired_percentage = 60
        entity._desired_preset_mode = "auto"
        restore_data = entity.extra_restore_state_data.as_dict()
        assert restore_data["is_on"] is True
        assert restore_data["percentage"] == 60
        assert restore_data["preset_mode"] == "auto"
