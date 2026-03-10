"""Unit tests for climate/proxy_entity.py — ClimateProxyClimateEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.climate_proxy.climate.proxy_entity import ClimateProxyClimateEntity, ClimateProxyRestoreData
from custom_components.climate_proxy.const import (
    CONF_SENSOR_ENTITY_ID,
    CONF_SENSOR_WEIGHT,
    CONF_TEMPERATURE_SENSORS,
    RESTORE_KEY_FAN_MODE,
    RESTORE_KEY_HVAC_MODE,
    RESTORE_KEY_PRESET_MODE,
    RESTORE_KEY_SWING_MODE,
    RESTORE_KEY_TARGET_HUMIDITY,
    RESTORE_KEY_TARGET_TEMP,
    RESTORE_KEY_TARGET_TEMP_HIGH,
    RESTORE_KEY_TARGET_TEMP_LOW,
)
from homeassistant.components.climate import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import STATE_UNAVAILABLE, UnitOfTemperature
from homeassistant.core import State


def _make_entity() -> ClimateProxyClimateEntity:
    """Build a ClimateProxyClimateEntity with all dependencies mocked."""
    hass = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.services.async_call = AsyncMock()

    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"climate_entity_id": "climate.underlying"}
    config_entry.options = {}

    state_manager = MagicMock()
    state_manager.queue_pending_state = MagicMock()
    device_info = MagicMock()

    entity = ClimateProxyClimateEntity(
        hass=hass,
        config_entry=config_entry,
        state_manager=state_manager,
        device_info=device_info,
    )
    entity.async_write_ha_state = MagicMock()
    return entity


def _make_underlying_state(
    hvac_mode: str = HVACMode.HEAT,
    attributes: dict | None = None,
) -> State:
    """Build a minimal underlying climate State."""
    attrs = {
        "hvac_modes": ["off", "heat", "cool"],
        "temperature": 21.0,
        "current_temperature": 19.0,
        "min_temp": 10.0,
        "max_temp": 35.0,
        "target_temp_step": 0.5,
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
    }
    if attributes:
        attrs.update(attributes)
    return State("climate.underlying", hvac_mode, attrs)


@pytest.mark.unit
class TestClimateProxyRestoreData:
    def test_round_trip(self) -> None:
        data = {"hvac_mode": "heat", "target_temperature": 22.0}
        restore = ClimateProxyRestoreData(data)
        assert restore.as_dict() == data

    def test_from_dict_returns_same_data(self) -> None:
        data = {"hvac_mode": "cool", "target_temperature": 20.0}
        restore = ClimateProxyRestoreData.from_dict(data)
        assert restore.as_dict() == data


@pytest.mark.unit
class TestClimateProxyClimateEntityInit:
    def test_initial_hvac_mode_is_off(self) -> None:
        entity = _make_entity()
        assert entity.hvac_mode == HVACMode.OFF

    def test_initial_target_temperature_is_none(self) -> None:
        entity = _make_entity()
        assert entity.target_temperature is None

    def test_initial_humidity_is_none(self) -> None:
        entity = _make_entity()
        assert entity.target_humidity is None

    def test_always_available(self) -> None:
        entity = _make_entity()
        assert entity.available is True

    def test_unique_id_contains_entry_and_climate_suffix(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "climate" in entity.unique_id

    def test_name_is_none_for_device_name(self) -> None:
        entity = _make_entity()
        assert entity._attr_name is None


@pytest.mark.unit
class TestRestoreDesiredState:
    def test_restore_hvac_mode(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({RESTORE_KEY_HVAC_MODE: "cool"})
        assert entity._desired_hvac_mode == HVACMode.COOL

    def test_restore_invalid_hvac_mode_leaves_default(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({RESTORE_KEY_HVAC_MODE: "not_a_mode"})
        assert entity._desired_hvac_mode == HVACMode.OFF

    def test_restore_target_temperature(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({RESTORE_KEY_TARGET_TEMP: 22.5})
        assert entity._desired_target_temperature == 22.5

    def test_restore_temperature_range(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state({RESTORE_KEY_TARGET_TEMP_LOW: 18.0, RESTORE_KEY_TARGET_TEMP_HIGH: 24.0})
        assert entity._desired_target_temperature_low == 18.0
        assert entity._desired_target_temperature_high == 24.0

    def test_restore_preset_fan_swing(self) -> None:
        entity = _make_entity()
        entity._restore_desired_state(
            {
                RESTORE_KEY_PRESET_MODE: "eco",
                RESTORE_KEY_FAN_MODE: "auto",
                RESTORE_KEY_SWING_MODE: "on",
                RESTORE_KEY_TARGET_HUMIDITY: 50.0,
            }
        )
        assert entity._desired_preset_mode == "eco"
        assert entity._desired_fan_mode == "auto"
        assert entity._desired_swing_mode == "on"
        assert entity._desired_target_humidity == 50.0


@pytest.mark.unit
class TestExtraRestoreStateData:
    def test_extra_restore_state_data_contains_hvac_mode(self) -> None:
        entity = _make_entity()
        entity._desired_hvac_mode = HVACMode.COOL
        data = entity.extra_restore_state_data.as_dict()
        assert data[RESTORE_KEY_HVAC_MODE] == HVACMode.COOL

    def test_extra_restore_state_data_contains_temperatures(self) -> None:
        entity = _make_entity()
        entity._desired_target_temperature = 21.5
        data = entity.extra_restore_state_data.as_dict()
        assert data[RESTORE_KEY_TARGET_TEMP] == 21.5


@pytest.mark.unit
class TestCapabilityUpdate:
    def test_updates_hvac_modes_from_underlying(self) -> None:
        entity = _make_entity()
        state = _make_underlying_state(attributes={"hvac_modes": ["off", "heat", "cool", "auto"]})
        entity._update_capabilities(state)
        assert HVACMode.COOL in entity._attr_hvac_modes

    def test_updates_min_max_temp(self) -> None:
        entity = _make_entity()
        state = _make_underlying_state(attributes={"min_temp": 5.0, "max_temp": 40.0})
        entity._update_capabilities(state)
        assert entity._attr_min_temp == 5.0
        assert entity._attr_max_temp == 40.0

    def test_updates_temperature_unit(self) -> None:
        entity = _make_entity()
        # HA climate entities report their unit via "temperature_unit" in state attrs
        state = _make_underlying_state(attributes={"temperature_unit": UnitOfTemperature.FAHRENHEIT})
        entity._update_capabilities(state)
        assert entity._attr_temperature_unit == UnitOfTemperature.FAHRENHEIT


@pytest.mark.unit
class TestCurrentReadings:
    def test_reads_current_temp_from_underlying(self) -> None:
        entity = _make_entity()
        state = _make_underlying_state(attributes={"current_temperature": 20.0})
        entity._update_current_readings(state)
        assert entity._attr_current_temperature == 20.0

    def test_reads_hvac_action_from_underlying(self) -> None:
        entity = _make_entity()
        state = _make_underlying_state(attributes={"hvac_action": "heating"})
        entity._update_current_readings(state)
        assert entity._attr_hvac_action == HVACAction.HEATING

    def test_uses_weighted_avg_when_sensors_configured(self) -> None:
        entity = _make_entity()
        entity._config_entry.options = {
            CONF_TEMPERATURE_SENSORS: [{CONF_SENSOR_ENTITY_ID: "sensor.ext_temp", CONF_SENSOR_WEIGHT: 1.0}]
        }
        sensor_state = MagicMock()
        sensor_state.state = "23.5"

        def get_state(entity_id: str) -> MagicMock | None:
            if entity_id == "sensor.ext_temp":
                return sensor_state
            return None

        entity.hass.states.get = get_state
        state = _make_underlying_state(attributes={"current_temperature": 19.0})
        entity._update_current_readings(state)
        assert entity._attr_current_temperature == pytest.approx(23.5)

    def test_invalid_hvac_action_sets_none(self) -> None:
        entity = _make_entity()
        state = _make_underlying_state(attributes={"hvac_action": "not_valid"})
        entity._update_current_readings(state)
        assert entity._attr_hvac_action is None


@pytest.mark.unit
class TestCommandsAndPushOrQueue:
    async def test_set_hvac_mode_updates_desired_and_pushes(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_set_hvac_mode(HVACMode.COOL)

        assert entity._desired_hvac_mode == HVACMode.COOL
        entity.async_write_ha_state.assert_called()
        entity.hass.services.async_call.assert_called_once()
        call_args = entity.hass.services.async_call.call_args
        assert call_args[0][0] == "climate"
        assert call_args[0][1] == "set_hvac_mode"

    async def test_set_temperature_updates_desired_and_pushes(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_set_temperature(temperature=22.0)

        assert entity._desired_target_temperature == 22.0
        entity.hass.services.async_call.assert_called_once()

    async def test_set_temperature_range(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_set_temperature(target_temp_low=18.0, target_temp_high=24.0)

        assert entity._desired_target_temperature_low == 18.0
        assert entity._desired_target_temperature_high == 24.0

    async def test_set_humidity_updates_desired(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_set_humidity(55)

        assert entity._desired_target_humidity == 55.0

    async def test_set_fan_mode_updates_desired(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_set_fan_mode("high")

        assert entity._desired_fan_mode == "high"

    async def test_set_preset_mode_updates_desired(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_set_preset_mode("eco")

        assert entity._desired_preset_mode == "eco"

    async def test_set_swing_mode_updates_desired(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_set_swing_mode("on")

        assert entity._desired_swing_mode == "on"

    async def test_turn_on_sets_first_non_off_mode(self) -> None:
        entity = _make_entity()
        entity._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_turn_on()

        assert entity._desired_hvac_mode == HVACMode.HEAT

    async def test_turn_on_prefers_heat_cool(self) -> None:
        entity = _make_entity()
        entity._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.HEAT_COOL]
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_turn_on()

        assert entity._desired_hvac_mode == HVACMode.HEAT_COOL

    async def test_turn_off_sets_hvac_off(self) -> None:
        entity = _make_entity()
        entity._desired_hvac_mode = HVACMode.HEAT
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_turn_off()

        assert entity._desired_hvac_mode == HVACMode.OFF

    async def test_queue_command_when_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("climate.underlying", STATE_UNAVAILABLE))

        await entity.async_set_hvac_mode(HVACMode.COOL)

        entity.hass.services.async_call.assert_not_called()
        entity._state_manager.queue_pending_state.assert_called_once()

    async def test_push_when_available(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=_make_underlying_state())

        await entity.async_set_hvac_mode(HVACMode.HEAT)

        entity.hass.services.async_call.assert_called_once()
        entity._state_manager.queue_pending_state.assert_not_called()


@pytest.mark.unit
class TestOnUnderlyingStateChanged:
    async def test_updates_underlying_was_unavailable_flag(self) -> None:
        entity = _make_entity()
        state = State("climate.underlying", STATE_UNAVAILABLE)
        await entity.async_on_underlying_state_changed(state)
        assert entity.underlying_was_unavailable is True

    async def test_clears_unavailable_flag_when_available(self) -> None:
        entity = _make_entity()
        state = _make_underlying_state(hvac_mode=HVACMode.HEAT)
        await entity.async_on_underlying_state_changed(state)
        assert entity.underlying_was_unavailable is False

    async def test_writes_ha_state_on_change(self) -> None:
        entity = _make_entity()
        state = _make_underlying_state()
        await entity.async_on_underlying_state_changed(state)
        entity.async_write_ha_state.assert_called()


@pytest.mark.unit
class TestGetClimateCorrections:
    def test_no_corrections_when_desired_matches_actual(self) -> None:
        entity = _make_entity()
        entity._desired_hvac_mode = HVACMode.HEAT
        entity._desired_target_temperature = 21.0
        state = _make_underlying_state(hvac_mode=HVACMode.HEAT, attributes={"temperature": 21.0})
        corrections = entity.get_climate_corrections(state)
        assert corrections == {}

    def test_correction_when_hvac_mode_differs(self) -> None:
        entity = _make_entity()
        entity._desired_hvac_mode = HVACMode.COOL
        state = _make_underlying_state(hvac_mode=HVACMode.HEAT)
        corrections = entity.get_climate_corrections(state)
        assert "set_hvac_mode" in corrections

    def test_correction_when_temperature_differs(self) -> None:
        entity = _make_entity()
        entity._desired_hvac_mode = HVACMode.HEAT
        entity._desired_target_temperature = 22.0
        state = _make_underlying_state(hvac_mode=HVACMode.HEAT, attributes={"temperature": 19.0})
        corrections = entity.get_climate_corrections(state)
        assert "set_temperature" in corrections


@pytest.mark.unit
class TestApplyPendingState:
    async def test_apply_pending_state_calls_services(self) -> None:
        entity = _make_entity()
        pending = {
            "set_hvac_mode": {"hvac_mode": "heat"},
            "set_temperature": {"temperature": 22.0},
        }
        await entity.async_apply_pending_state(pending)
        assert entity.hass.services.async_call.call_count == 2


@pytest.mark.unit
class TestEffectiveSetpoints:
    def test_no_external_sensors_returns_desired(self) -> None:
        entity = _make_entity()
        entity._desired_target_temperature = 21.0
        temp, low, high = entity._get_effective_setpoints()
        assert temp == 21.0
        assert low is None
        assert high is None

    def test_with_external_sensors_applies_offset(self) -> None:
        entity = _make_entity()
        entity._desired_target_temperature = 22.0
        entity._config_entry.options = {
            CONF_TEMPERATURE_SENSORS: [{CONF_SENSOR_ENTITY_ID: "sensor.ext", CONF_SENSOR_WEIGHT: 1.0}]
        }
        # underlying device reads 23°C, external sensor reads 20°C → offset +3
        underlying_state = _make_underlying_state(attributes={"current_temperature": 23.0})
        sensor_state = MagicMock()
        sensor_state.state = "20.0"

        def get_state(entity_id: str) -> State | MagicMock | None:
            if entity_id == "climate.underlying":
                return underlying_state
            if entity_id == "sensor.ext":
                return sensor_state
            return None

        entity.hass.states.get = get_state
        temp, low, _high = entity._get_effective_setpoints()
        # proxy_target=22 + offset(23-20)=3 → device setpoint=25
        assert temp == pytest.approx(25.0)
        assert low is None

    def test_no_external_sensors_returns_desired_range(self) -> None:
        entity = _make_entity()
        entity._desired_target_temperature_low = 18.0
        entity._desired_target_temperature_high = 24.0
        temp, low, high = entity._get_effective_setpoints()
        assert temp is None
        assert low == 18.0
        assert high == 24.0
