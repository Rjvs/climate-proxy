"""Unit tests for climate/proxy_entity.py — ClimateProxyClimateEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import State

from custom_components.climate_proxy.climate.proxy_entity import (
    ClimateProxyClimateEntity,
    ClimateProxyRestoreData,
)
from custom_components.climate_proxy.const import (
    RESTORE_KEY_AUX_HEAT,
    RESTORE_KEY_CURRENT_OFFSET,
    RESTORE_KEY_FAN_MODE,
    RESTORE_KEY_HVAC_MODE,
    RESTORE_KEY_LAST_ACTIVE_HVAC_MODE,
    RESTORE_KEY_PRESET_MODE,
    RESTORE_KEY_SWING_HORIZONTAL_MODE,
    RESTORE_KEY_SWING_MODE,
    RESTORE_KEY_TARGET_HUMIDITY,
    RESTORE_KEY_TARGET_TEMP,
    RESTORE_KEY_TARGET_TEMP_HIGH,
    RESTORE_KEY_TARGET_TEMP_LOW,
)


def _make_entity() -> ClimateProxyClimateEntity:
    """Build a ClimateProxyClimateEntity with all dependencies mocked."""
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.services.async_call = AsyncMock()
    hass.async_create_task = MagicMock()

    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"climate_entity_id": "climate.thermostat"}
    config_entry.options = {}

    state_manager = MagicMock()
    device_info = MagicMock()

    entity = ClimateProxyClimateEntity(
        hass=hass,
        config_entry=config_entry,
        state_manager=state_manager,
        device_info=device_info,
    )
    entity.hass = hass
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.mark.unit
class TestClimateProxyRestoreData:
    def test_round_trip_full_state(self) -> None:
        data = {
            RESTORE_KEY_HVAC_MODE: "heat",
            RESTORE_KEY_LAST_ACTIVE_HVAC_MODE: "heat",
            RESTORE_KEY_TARGET_TEMP: 21.0,
            RESTORE_KEY_TARGET_TEMP_LOW: 18.0,
            RESTORE_KEY_TARGET_TEMP_HIGH: 24.0,
            RESTORE_KEY_TARGET_HUMIDITY: 50.0,
            RESTORE_KEY_PRESET_MODE: "eco",
            RESTORE_KEY_FAN_MODE: "auto",
            RESTORE_KEY_SWING_MODE: "on",
            RESTORE_KEY_SWING_HORIZONTAL_MODE: "left_right",
            RESTORE_KEY_AUX_HEAT: False,
            RESTORE_KEY_CURRENT_OFFSET: 1.5,
        }
        restore = ClimateProxyRestoreData(data)
        assert restore.as_dict() == data

    def test_from_dict_round_trip(self) -> None:
        data = {RESTORE_KEY_HVAC_MODE: "cool", RESTORE_KEY_TARGET_TEMP: 22.0}
        restored = ClimateProxyRestoreData.from_dict(data)
        assert restored.as_dict() == data


@pytest.mark.unit
class TestClimateProxyClimateEntityInit:
    def test_initial_hvac_mode_is_off(self) -> None:
        entity = _make_entity()
        assert entity.hvac_mode == HVACMode.OFF

    def test_always_available(self) -> None:
        entity = _make_entity()
        assert entity.available is True

    def test_unique_id_includes_entry_id(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id

    def test_initial_desired_state_is_none(self) -> None:
        entity = _make_entity()
        assert entity.target_temperature is None
        assert entity.fan_mode is None
        assert entity.preset_mode is None
        assert entity.swing_mode is None
        assert entity.swing_horizontal_mode is None
        assert entity.is_aux_heat is None


@pytest.mark.unit
class TestRestoreDesiredState:
    def test_restores_hvac_mode(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({RESTORE_KEY_HVAC_MODE: "cool"})
        assert entity._desired_hvac_mode == HVACMode.COOL

    def test_restores_last_active_mode(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({RESTORE_KEY_LAST_ACTIVE_HVAC_MODE: "heat"})
        assert entity._last_active_hvac_mode == HVACMode.HEAT

    def test_invalid_hvac_mode_ignored(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({RESTORE_KEY_HVAC_MODE: "invalid_mode"})
        assert entity._desired_hvac_mode == HVACMode.OFF

    def test_restores_temperature(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({RESTORE_KEY_TARGET_TEMP: 21.5})
        assert entity._desired_target_temperature == 21.5

    def test_restores_swing_horizontal_mode(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({RESTORE_KEY_SWING_HORIZONTAL_MODE: "left_right"})
        assert entity._desired_swing_horizontal_mode == "left_right"

    def test_restores_offset(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({RESTORE_KEY_CURRENT_OFFSET: 2.5})
        assert entity._current_offset == 2.5

    def test_missing_offset_defaults_to_zero(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({})
        assert entity._current_offset == 0.0


@pytest.mark.unit
class TestExtraRestoreStateData:
    def test_persists_all_desired_fields(self) -> None:
        entity = _make_entity()
        entity._desired_hvac_mode = HVACMode.HEAT
        entity._last_active_hvac_mode = HVACMode.HEAT
        entity._desired_target_temperature = 21.0
        entity._desired_swing_horizontal_mode = "left_right"
        entity._current_offset = 1.0

        data = entity.extra_restore_state_data.as_dict()
        assert data[RESTORE_KEY_HVAC_MODE] == HVACMode.HEAT
        assert data[RESTORE_KEY_LAST_ACTIVE_HVAC_MODE] == HVACMode.HEAT
        assert data[RESTORE_KEY_TARGET_TEMP] == 21.0
        assert data[RESTORE_KEY_SWING_HORIZONTAL_MODE] == "left_right"
        assert data[RESTORE_KEY_CURRENT_OFFSET] == 1.0


@pytest.mark.unit
class TestClimateCommands:
    async def test_set_hvac_mode_updates_desired(self) -> None:
        entity = _make_entity()
        await entity.async_set_hvac_mode(HVACMode.HEAT)
        assert entity._desired_hvac_mode == HVACMode.HEAT
        entity.async_write_ha_state.assert_called()

    async def test_set_hvac_mode_non_off_records_last_active(self) -> None:
        entity = _make_entity()
        await entity.async_set_hvac_mode(HVACMode.COOL)
        assert entity._last_active_hvac_mode == HVACMode.COOL

    async def test_set_hvac_mode_off_does_not_update_last_active(self) -> None:
        entity = _make_entity()
        entity._last_active_hvac_mode = HVACMode.HEAT
        await entity.async_set_hvac_mode(HVACMode.OFF)
        assert entity._last_active_hvac_mode == HVACMode.HEAT

    async def test_set_humidity_updates_desired(self) -> None:
        entity = _make_entity()
        await entity.async_set_humidity(55)
        assert entity._desired_target_humidity == 55.0
        entity.async_write_ha_state.assert_called()

    async def test_set_fan_mode_updates_desired(self) -> None:
        entity = _make_entity()
        await entity.async_set_fan_mode("high")
        assert entity._desired_fan_mode == "high"

    async def test_set_preset_mode_updates_desired(self) -> None:
        entity = _make_entity()
        await entity.async_set_preset_mode("eco")
        assert entity._desired_preset_mode == "eco"

    async def test_set_swing_mode_updates_desired(self) -> None:
        entity = _make_entity()
        await entity.async_set_swing_mode("on")
        assert entity._desired_swing_mode == "on"

    async def test_set_swing_horizontal_mode_updates_desired(self) -> None:
        entity = _make_entity()
        await entity.async_set_swing_horizontal_mode("left_right")
        assert entity._desired_swing_horizontal_mode == "left_right"

    async def test_set_aux_heat_updates_desired(self) -> None:
        entity = _make_entity()
        await entity.async_set_aux_heat(True)
        assert entity._desired_aux_heat is True

    async def test_turn_off_sets_hvac_off(self) -> None:
        entity = _make_entity()
        entity._desired_hvac_mode = HVACMode.HEAT
        await entity.async_turn_off()
        assert entity._desired_hvac_mode == HVACMode.OFF

    async def test_turn_on_restores_last_active_mode(self) -> None:
        entity = _make_entity()
        entity._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
        entity._last_active_hvac_mode = HVACMode.COOL
        await entity.async_turn_on()
        assert entity._desired_hvac_mode == HVACMode.COOL

    async def test_turn_on_falls_back_to_heat_cool(self) -> None:
        entity = _make_entity()
        entity._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.HEAT_COOL]
        entity._last_active_hvac_mode = None
        await entity.async_turn_on()
        assert entity._desired_hvac_mode == HVACMode.HEAT_COOL

    async def test_turn_on_falls_back_to_first_non_off(self) -> None:
        entity = _make_entity()
        entity._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL]
        entity._last_active_hvac_mode = None
        await entity.async_turn_on()
        assert entity._desired_hvac_mode == HVACMode.COOL

    async def test_turn_on_does_nothing_when_no_non_off_modes(self) -> None:
        entity = _make_entity()
        entity._attr_hvac_modes = [HVACMode.OFF]
        await entity.async_turn_on()
        assert entity._desired_hvac_mode == HVACMode.OFF


@pytest.mark.unit
class TestPushOrQueue:
    async def test_pushes_when_underlying_available(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("climate.thermostat", "heat"))
        entity.hass.services.async_call = AsyncMock()

        await entity._push_or_queue("set_hvac_mode", {"hvac_mode": "heat"})

        entity.hass.services.async_call.assert_called_once()
        call_args = entity.hass.services.async_call.call_args
        assert call_args[0][0] == "climate"
        assert call_args[0][1] == "set_hvac_mode"

    async def test_queues_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(
            return_value=State("climate.thermostat", STATE_UNAVAILABLE)
        )
        entity.hass.services.async_call = AsyncMock()

        await entity._push_or_queue("set_hvac_mode", {"hvac_mode": "heat"})

        entity.hass.services.async_call.assert_not_called()
        entity._state_manager.queue_pending_state.assert_called_once_with(
            "set_hvac_mode", {"hvac_mode": "heat"}
        )

    async def test_queues_when_underlying_none(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=None)

        await entity._push_or_queue("set_temperature", {"temperature": 21.0})

        entity._state_manager.queue_pending_state.assert_called_once()


@pytest.mark.unit
class TestGetClimateCorrections:
    def test_no_corrections_when_state_matches(self) -> None:
        entity = _make_entity()
        entity._desired_hvac_mode = HVACMode.HEAT
        entity._desired_target_temperature = 21.0
        entity._config_entry.options = {}

        entity.hass.states.get = MagicMock(return_value=None)

        state = State("climate.thermostat", "heat", {"temperature": 21.0})
        corrections = entity.get_climate_corrections(state)
        assert corrections == {}

    def test_returns_hvac_mode_correction(self) -> None:
        entity = _make_entity()
        entity._desired_hvac_mode = HVACMode.HEAT
        entity._config_entry.options = {}
        entity.hass.states.get = MagicMock(return_value=None)

        state = State("climate.thermostat", "cool", {})
        corrections = entity.get_climate_corrections(state)
        assert "set_hvac_mode" in corrections

    def test_swing_horizontal_correction_included(self) -> None:
        entity = _make_entity()
        entity._desired_hvac_mode = HVACMode.HEAT
        entity._desired_swing_horizontal_mode = "left_right"
        entity._config_entry.options = {}
        entity.hass.states.get = MagicMock(return_value=None)

        state = State("climate.thermostat", "heat", {"swing_horizontal_mode": "off"})
        corrections = entity.get_climate_corrections(state)
        assert "set_swing_horizontal_mode" in corrections


@pytest.mark.unit
class TestUpdateCapabilities:
    def test_updates_swing_horizontal_modes(self) -> None:
        entity = _make_entity()
        state = State(
            "climate.thermostat",
            "heat",
            {"swing_horizontal_modes": ["off", "left_right"], "hvac_modes": ["off", "heat"]},
        )
        entity._update_capabilities(state)
        assert entity._attr_swing_horizontal_modes == ["off", "left_right"]

    def test_humidity_feature_detected_correctly(self) -> None:
        entity = _make_entity()
        state = State(
            "climate.thermostat",
            "heat",
            {"hvac_modes": ["off", "heat"], "humidity": 50},
        )
        entity._update_capabilities(state)
        assert entity._attr_supported_features & ClimateEntityFeature.TARGET_HUMIDITY
