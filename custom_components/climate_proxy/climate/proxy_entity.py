"""Climate proxy entity — the core man-in-the-middle virtual climate device."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    ATTR_AUX_HEAT,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import (
    ATTR_HVAC_ACTION,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    SERVICE_SET_AUX_HEAT,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from ..const import (
    CONF_HUMIDITY_SENSORS,
    CONF_TEMPERATURE_SENSORS,
    LOGGER,
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
from .capabilities import (
    detect_supported_features,
    extract_fan_modes,
    extract_hvac_modes,
    extract_min_max_temp,
    extract_preset_modes,
    extract_swing_horizontal_modes,
    extract_swing_modes,
    extract_temp_step,
    extract_temperature_unit,
)
from .enforcement import get_climate_corrections
from .offset_calculator import (
    calculate_device_setpoint,
    calculate_setpoint_range,
    calculate_weighted_average,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers.device_registry import DeviceInfo

    from ..data import ClimateProxyConfigEntry
    from ..state_manager import ClimateProxyStateManager

PARALLEL_UPDATES = 0


class ClimateProxyRestoreData(ExtraStoredData):
    """Holds the desired state that climate_proxy enforces on the underlying device."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def as_dict(self) -> dict[str, Any]:
        return self._data

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> ClimateProxyRestoreData:
        return cls(restored)


class ClimateProxyClimateEntity(ClimateEntity, RestoreEntity):
    """
    Virtual climate entity that wraps an underlying HA climate entity.

    Behaviour:
    - Reads capabilities dynamically from the underlying entity.
    - Stores all user-set desired values internally; these are restored across
      Home Assistant restarts via RestoreEntity.
    - All set_* / turn_on / turn_off commands update the internal desired state,
      write the proxy state to HA, then push the command to the underlying entity
      (or queue it if the underlying entity is currently unavailable).
    - The StateManager calls async_on_underlying_state_changed() whenever the
      underlying entity changes; this method refreshes readings and, if the
      underlying state deviates from the desired state, schedules a correction.
    - When external temperature/humidity sensors are configured, a dynamic offset
      is applied to the setpoint sent to the physical device.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ClimateProxyConfigEntry,
        state_manager: ClimateProxyStateManager,
        device_info: DeviceInfo,
    ) -> None:
        self.hass = hass
        self._config_entry = config_entry
        self._state_manager = state_manager
        self._attr_device_info = device_info
        self._underlying_entity_id: str = config_entry.data["climate_entity_id"]
        self._attr_unique_id = f"{config_entry.entry_id}_climate"
        self._attr_name = None  # uses device name

        # Capability flags — populated from underlying entity at setup / on change
        self._attr_supported_features = ClimateEntityFeature(0)
        self._attr_hvac_modes: list[HVACMode] = [HVACMode.OFF]
        self._attr_fan_modes: list[str] | None = None
        self._attr_preset_modes: list[str] | None = None
        self._attr_swing_modes: list[str] | None = None
        self._attr_swing_horizontal_modes: list[str] | None = None
        self._attr_min_temp: float = 7.0
        self._attr_max_temp: float = 35.0
        self._attr_target_temperature_step: float = 0.5
        self._attr_temperature_unit: str = UnitOfTemperature.CELSIUS

        # Desired (enforced) state
        self._desired_hvac_mode: HVACMode = HVACMode.OFF
        self._last_active_hvac_mode: HVACMode | None = None
        self._desired_target_temperature: float | None = None
        self._desired_target_temperature_low: float | None = None
        self._desired_target_temperature_high: float | None = None
        self._desired_target_humidity: float | None = None
        self._desired_preset_mode: str | None = None
        self._desired_fan_mode: str | None = None
        self._desired_swing_mode: str | None = None
        self._desired_swing_horizontal_mode: str | None = None
        self._desired_aux_heat: bool | None = None

        # Current readings (from underlying entity or external sensors)
        self._attr_current_temperature: float | None = None
        self._attr_current_humidity: float | None = None
        self._attr_hvac_action: HVACAction | None = None
        self._current_offset: float = 0.0

        # Whether the underlying device was unavailable on the last event
        self.underlying_was_unavailable: bool = False

    # ------------------------------------------------------------------
    # RestoreEntity lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore previous desired state and initialize from underlying entity."""
        await super().async_added_to_hass()

        last_extra = await self.async_get_last_extra_data()
        if last_extra is not None:
            self._restore_desired_state(last_extra.as_dict())
            LOGGER.debug("Restored desired state for %s", self._underlying_entity_id)

        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is not None:
            self._update_capabilities(underlying)
            self._update_current_readings(underlying)
            if underlying.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                self.underlying_was_unavailable = True

        self.async_write_ha_state()

    @property
    def extra_restore_state_data(self) -> ClimateProxyRestoreData:
        """Return the desired state to be persisted across restarts."""
        return ClimateProxyRestoreData({
            RESTORE_KEY_HVAC_MODE: self._desired_hvac_mode,
            RESTORE_KEY_LAST_ACTIVE_HVAC_MODE: self._last_active_hvac_mode,
            RESTORE_KEY_TARGET_TEMP: self._desired_target_temperature,
            RESTORE_KEY_TARGET_TEMP_LOW: self._desired_target_temperature_low,
            RESTORE_KEY_TARGET_TEMP_HIGH: self._desired_target_temperature_high,
            RESTORE_KEY_TARGET_HUMIDITY: self._desired_target_humidity,
            RESTORE_KEY_PRESET_MODE: self._desired_preset_mode,
            RESTORE_KEY_FAN_MODE: self._desired_fan_mode,
            RESTORE_KEY_SWING_MODE: self._desired_swing_mode,
            RESTORE_KEY_SWING_HORIZONTAL_MODE: self._desired_swing_horizontal_mode,
            RESTORE_KEY_AUX_HEAT: self._desired_aux_heat,
            RESTORE_KEY_CURRENT_OFFSET: self._current_offset,
        })

    def _restore_desired_state(self, data: dict[str, Any]) -> None:
        """Populate desired state from restored data dict."""
        if hvac := data.get(RESTORE_KEY_HVAC_MODE):
            try:
                self._desired_hvac_mode = HVACMode(hvac)
            except ValueError:
                pass
        if last_active := data.get(RESTORE_KEY_LAST_ACTIVE_HVAC_MODE):
            try:
                self._last_active_hvac_mode = HVACMode(last_active)
            except ValueError:
                pass
        self._desired_target_temperature = data.get(RESTORE_KEY_TARGET_TEMP)
        self._desired_target_temperature_low = data.get(RESTORE_KEY_TARGET_TEMP_LOW)
        self._desired_target_temperature_high = data.get(RESTORE_KEY_TARGET_TEMP_HIGH)
        self._desired_target_humidity = data.get(RESTORE_KEY_TARGET_HUMIDITY)
        self._desired_preset_mode = data.get(RESTORE_KEY_PRESET_MODE)
        self._desired_fan_mode = data.get(RESTORE_KEY_FAN_MODE)
        self._desired_swing_mode = data.get(RESTORE_KEY_SWING_MODE)
        self._desired_swing_horizontal_mode = data.get(RESTORE_KEY_SWING_HORIZONTAL_MODE)
        self._desired_aux_heat = data.get(RESTORE_KEY_AUX_HEAT)
        self._current_offset = float(data.get(RESTORE_KEY_CURRENT_OFFSET, 0.0))

    # ------------------------------------------------------------------
    # ClimateEntity properties
    # ------------------------------------------------------------------

    @property
    def hvac_mode(self) -> HVACMode:
        return self._desired_hvac_mode

    @property
    def target_temperature(self) -> float | None:
        return self._desired_target_temperature

    @property
    def target_temperature_low(self) -> float | None:
        return self._desired_target_temperature_low

    @property
    def target_temperature_high(self) -> float | None:
        return self._desired_target_temperature_high

    @property
    def target_humidity(self) -> int | None:
        if self._desired_target_humidity is not None:
            return int(self._desired_target_humidity)
        return None

    @property
    def preset_mode(self) -> str | None:
        return self._desired_preset_mode

    @property
    def fan_mode(self) -> str | None:
        return self._desired_fan_mode

    @property
    def swing_mode(self) -> str | None:
        return self._desired_swing_mode

    @property
    def swing_horizontal_mode(self) -> str | None:
        return self._desired_swing_horizontal_mode

    @property
    def is_aux_heat(self) -> bool | None:
        return self._desired_aux_heat

    @property
    def available(self) -> bool:
        # Always available — unavailability of underlying device is handled via command queue
        return True

    # ------------------------------------------------------------------
    # ClimateEntity commands (MitM: store desired → push to device)
    # ------------------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode != HVACMode.OFF:
            self._last_active_hvac_mode = hvac_mode
        self._desired_hvac_mode = hvac_mode
        self.async_write_ha_state()
        await self._push_or_queue(SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: hvac_mode})

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        hvac = kwargs.get(ATTR_HVAC_MODE)

        if temp is not None:
            self._desired_target_temperature = float(temp)
        if low is not None:
            self._desired_target_temperature_low = float(low)
        if high is not None:
            self._desired_target_temperature_high = float(high)
        if hvac is not None:
            try:
                mode = HVACMode(hvac)
                if mode != HVACMode.OFF:
                    self._last_active_hvac_mode = mode
                self._desired_hvac_mode = mode
            except ValueError:
                pass

        self.async_write_ha_state()
        effective_temp, effective_low, effective_high = self._get_effective_setpoints()

        service_kwargs: dict[str, Any] = {}
        if effective_temp is not None:
            service_kwargs[ATTR_TEMPERATURE] = effective_temp
        if effective_low is not None:
            service_kwargs[ATTR_TARGET_TEMP_LOW] = effective_low
        if effective_high is not None:
            service_kwargs[ATTR_TARGET_TEMP_HIGH] = effective_high
        if hvac is not None:
            service_kwargs[ATTR_HVAC_MODE] = hvac

        if service_kwargs:
            await self._push_or_queue(SERVICE_SET_TEMPERATURE, service_kwargs)

    async def async_set_humidity(self, humidity: int) -> None:
        self._desired_target_humidity = float(humidity)
        self.async_write_ha_state()
        await self._push_or_queue(SERVICE_SET_HUMIDITY, {"humidity": humidity})

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        self._desired_fan_mode = fan_mode
        self.async_write_ha_state()
        await self._push_or_queue(SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: fan_mode})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        self._desired_preset_mode = preset_mode
        self.async_write_ha_state()
        await self._push_or_queue(SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: preset_mode})

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        self._desired_swing_mode = swing_mode
        self.async_write_ha_state()
        await self._push_or_queue(SERVICE_SET_SWING_MODE, {ATTR_SWING_MODE: swing_mode})

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        self._desired_swing_horizontal_mode = swing_horizontal_mode
        self.async_write_ha_state()
        await self._push_or_queue(
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {ATTR_SWING_HORIZONTAL_MODE: swing_horizontal_mode},
        )

    async def async_set_aux_heat(self, aux_heat: bool) -> None:
        self._desired_aux_heat = aux_heat
        self.async_write_ha_state()
        await self._push_or_queue(SERVICE_SET_AUX_HEAT, {ATTR_AUX_HEAT: aux_heat})

    async def async_turn_on(self) -> None:
        non_off = [m for m in self._attr_hvac_modes if m != HVACMode.OFF]
        if not non_off:
            return
        # Prefer restoring the last explicitly-set non-OFF mode
        if self._last_active_hvac_mode is not None and self._last_active_hvac_mode in non_off:
            target = self._last_active_hvac_mode
        elif HVACMode.HEAT_COOL in non_off:
            target = HVACMode.HEAT_COOL
        else:
            target = non_off[0]
        await self.async_set_hvac_mode(target)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    # ------------------------------------------------------------------
    # State update callbacks (called by StateManager)
    # ------------------------------------------------------------------

    async def async_on_underlying_state_changed(self, new_state: State) -> None:
        """Called by StateManager when the underlying climate entity changes."""
        self.underlying_was_unavailable = new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        self._update_capabilities(new_state)
        self._update_current_readings(new_state)
        self.async_write_ha_state()

    async def async_on_sensor_changed(self) -> None:
        """Called by StateManager when a reference temperature/humidity sensor changes."""
        self._recalculate_offset()
        # Push updated effective setpoints to underlying device
        effective_temp, effective_low, effective_high = self._get_effective_setpoints()
        if effective_temp is not None or (effective_low is not None and effective_high is not None):
            kwargs: dict[str, Any] = {}
            if effective_temp is not None:
                kwargs[ATTR_TEMPERATURE] = effective_temp
            if effective_low is not None:
                kwargs[ATTR_TARGET_TEMP_LOW] = effective_low
            if effective_high is not None:
                kwargs[ATTR_TARGET_TEMP_HIGH] = effective_high
            await self._push_or_queue(SERVICE_SET_TEMPERATURE, kwargs)
        self.async_write_ha_state()

    async def async_apply_pending_state(self, pending: dict[str, Any]) -> None:
        """Apply a dict of pending service commands to the underlying device."""
        for service, kwargs in pending.items():
            await self.hass.services.async_call(
                "climate",
                service,
                kwargs,
                blocking=False,
                target={"entity_id": self._underlying_entity_id},
            )

    def get_climate_corrections(self, underlying_state: State) -> dict[str, dict[str, Any]]:
        """Return corrections needed to bring the underlying entity back to desired state."""
        effective_temp, effective_low, effective_high = self._get_effective_setpoints()
        return get_climate_corrections(
            underlying_state=underlying_state,
            desired_hvac_mode=self._desired_hvac_mode,
            desired_target_temperature=self._desired_target_temperature,
            desired_target_temperature_low=self._desired_target_temperature_low,
            desired_target_temperature_high=self._desired_target_temperature_high,
            desired_target_humidity=self._desired_target_humidity,
            desired_preset_mode=self._desired_preset_mode,
            desired_fan_mode=self._desired_fan_mode,
            desired_swing_mode=self._desired_swing_mode,
            desired_swing_horizontal_mode=self._desired_swing_horizontal_mode,
            desired_aux_heat=self._desired_aux_heat,
            effective_target_temperature=effective_temp,
            effective_target_low=effective_low,
            effective_target_high=effective_high,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_capabilities(self, state: State) -> None:
        """Refresh capability flags from underlying entity's current state."""
        self._attr_supported_features = detect_supported_features(state)
        self._attr_hvac_modes = extract_hvac_modes(state)
        self._attr_fan_modes = extract_fan_modes(state)
        self._attr_preset_modes = extract_preset_modes(state)
        self._attr_swing_modes = extract_swing_modes(state)
        self._attr_swing_horizontal_modes = extract_swing_horizontal_modes(state)
        self._attr_min_temp, self._attr_max_temp = extract_min_max_temp(state)
        self._attr_target_temperature_step = extract_temp_step(state)
        self._attr_temperature_unit = extract_temperature_unit(state)

    def _update_current_readings(self, state: State) -> None:
        """Update current_temperature and current_humidity from external sensors or underlying device."""
        temp_sensors = self._config_entry.options.get(CONF_TEMPERATURE_SENSORS, [])
        humidity_sensors = self._config_entry.options.get(CONF_HUMIDITY_SENSORS, [])

        if temp_sensors:
            weighted = calculate_weighted_average(temp_sensors, self.hass)
            self._attr_current_temperature = weighted
        else:
            raw = state.attributes.get("current_temperature")
            self._attr_current_temperature = float(raw) if raw is not None else None

        if humidity_sensors:
            weighted = calculate_weighted_average(humidity_sensors, self.hass)
            self._attr_current_humidity = weighted
        else:
            raw = state.attributes.get("current_humidity")
            self._attr_current_humidity = float(raw) if raw is not None else None

        raw_action = state.attributes.get(ATTR_HVAC_ACTION)
        if raw_action is not None:
            try:
                self._attr_hvac_action = HVACAction(raw_action)
            except ValueError:
                self._attr_hvac_action = None
        else:
            self._attr_hvac_action = None

    def _recalculate_offset(self) -> None:
        """Recalculate the temperature offset when external sensors are in use."""
        temp_sensors = self._config_entry.options.get(CONF_TEMPERATURE_SENSORS, [])
        if not temp_sensors:
            self._current_offset = 0.0
            return

        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is None:
            return

        device_internal_raw = underlying.attributes.get("current_temperature")
        if device_internal_raw is None:
            return

        external_temp = calculate_weighted_average(temp_sensors, self.hass)
        if external_temp is None:
            return

        device_internal = float(device_internal_raw)
        self._current_offset = device_internal - external_temp
        self._attr_current_temperature = external_temp

    def _get_effective_setpoints(
        self,
    ) -> tuple[float | None, float | None, float | None]:
        """
        Return (effective_temp, effective_low, effective_high) accounting for offset.

        When external sensors are configured, the effective values are offset-adjusted
        so the physical device tracks the external reference sensor.
        """
        temp_sensors = self._config_entry.options.get(CONF_TEMPERATURE_SENSORS, [])
        if not temp_sensors:
            return (
                self._desired_target_temperature,
                self._desired_target_temperature_low,
                self._desired_target_temperature_high,
            )

        # External sensors in use — apply offset
        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is None:
            return (
                self._desired_target_temperature,
                self._desired_target_temperature_low,
                self._desired_target_temperature_high,
            )

        device_internal_raw = underlying.attributes.get("current_temperature")
        external_temp = calculate_weighted_average(temp_sensors, self.hass)

        if device_internal_raw is None or external_temp is None:
            return (
                self._desired_target_temperature,
                self._desired_target_temperature_low,
                self._desired_target_temperature_high,
            )

        device_internal = float(device_internal_raw)

        if self._desired_target_temperature is not None:
            eff_temp = calculate_device_setpoint(
                self._desired_target_temperature,
                device_internal,
                external_temp,
                self._attr_min_temp,
                self._attr_max_temp,
            )
            return eff_temp, None, None

        if (
            self._desired_target_temperature_low is not None
            and self._desired_target_temperature_high is not None
        ):
            eff_low, eff_high = calculate_setpoint_range(
                self._desired_target_temperature_low,
                self._desired_target_temperature_high,
                device_internal,
                external_temp,
                self._attr_min_temp,
                self._attr_max_temp,
            )
            return None, eff_low, eff_high

        return None, None, None

    async def _push_or_queue(self, service: str, kwargs: dict[str, Any]) -> None:
        """Push a climate service call to the underlying entity, or queue if unavailable."""
        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is not None and underlying.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            await self.hass.services.async_call(
                "climate",
                service,
                kwargs,
                blocking=False,
                target={"entity_id": self._underlying_entity_id},
            )
        else:
            self._state_manager.queue_pending_state(service, kwargs)
            LOGGER.debug(
                "Queued command %s for %s (device unavailable)",
                service,
                self._underlying_entity_id,
            )
