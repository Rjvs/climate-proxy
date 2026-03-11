"""Enforcement logic — compare desired vs actual climate state and produce corrections."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    HVACMode,
)
from homeassistant.components.climate.const import (
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE

from ..const import HUMIDITY_TOLERANCE, LOGGER, TEMPERATURE_TOLERANCE

if TYPE_CHECKING:
    from homeassistant.core import State


def get_climate_corrections(
    underlying_state: State,
    desired_hvac_mode: HVACMode | None,
    desired_target_temperature: float | None,
    desired_target_temperature_low: float | None,
    desired_target_temperature_high: float | None,
    desired_target_humidity: float | None,
    desired_preset_mode: str | None,
    desired_fan_mode: str | None,
    desired_swing_mode: str | None,
    desired_swing_horizontal_mode: str | None,
    effective_target_temperature: float | None = None,
    effective_target_low: float | None = None,
    effective_target_high: float | None = None,
) -> dict[str, dict[str, Any]]:
    """Compare desired vs actual climate state and produce service-call corrections.

    Compare desired state against underlying entity's actual state and produce
    a dict of {service_name: kwargs} corrections needed.

    The effective_target_* parameters are the offset-adjusted setpoints to send
    to the physical device (only relevant when external sensors are in use).
    When None, the proxy's desired values are used directly.

    Returns:
        Dict mapping climate service names to their keyword argument dicts.
        Empty dict if no corrections are needed.
    """
    attrs = underlying_state.attributes
    corrections: dict[str, dict[str, Any]] = {}

    # HVAC mode
    if desired_hvac_mode is not None:
        actual_hvac = underlying_state.state
        if actual_hvac != desired_hvac_mode:
            corrections[SERVICE_SET_HVAC_MODE] = {ATTR_HVAC_MODE: desired_hvac_mode}

    # Temperature and humidity corrections are skipped when the desired mode is OFF,
    # as pushing setpoints to an off device can trigger unintended mode changes on
    # some thermostats.
    mode_is_off = desired_hvac_mode == HVACMode.OFF

    # Temperature (single setpoint or range)
    eff_temp = effective_target_temperature if effective_target_temperature is not None else desired_target_temperature
    eff_low = effective_target_low if effective_target_low is not None else desired_target_temperature_low
    eff_high = effective_target_high if effective_target_high is not None else desired_target_temperature_high

    if not mode_is_off and eff_temp is not None:
        actual_temp = attrs.get("temperature")
        try:
            actual_temp_f = float(actual_temp) if actual_temp is not None else None
        except (TypeError, ValueError):
            LOGGER.debug(
                "Non-numeric temperature '%s' on %s — forcing correction",
                actual_temp,
                underlying_state.entity_id,
            )
            actual_temp_f = None
        if actual_temp_f is None or abs(actual_temp_f - eff_temp) > TEMPERATURE_TOLERANCE:
            corrections[SERVICE_SET_TEMPERATURE] = {ATTR_TEMPERATURE: eff_temp}
    elif not mode_is_off and eff_low is not None and eff_high is not None:
        actual_low = attrs.get(ATTR_TARGET_TEMP_LOW)
        actual_high = attrs.get(ATTR_TARGET_TEMP_HIGH)
        try:
            actual_low_f = float(actual_low) if actual_low is not None else None
        except (TypeError, ValueError):
            actual_low_f = None
        try:
            actual_high_f = float(actual_high) if actual_high is not None else None
        except (TypeError, ValueError):
            actual_high_f = None
        needs_correction = (
            actual_low_f is None
            or actual_high_f is None
            or abs(actual_low_f - eff_low) > TEMPERATURE_TOLERANCE
            or abs(actual_high_f - eff_high) > TEMPERATURE_TOLERANCE
        )
        if needs_correction:
            corrections[SERVICE_SET_TEMPERATURE] = {
                ATTR_TARGET_TEMP_LOW: eff_low,
                ATTR_TARGET_TEMP_HIGH: eff_high,
            }

    # Target humidity
    if not mode_is_off and desired_target_humidity is not None:
        actual_humidity = attrs.get(ATTR_HUMIDITY)
        try:
            actual_humidity_f = float(actual_humidity) if actual_humidity is not None else None
        except (TypeError, ValueError):
            LOGGER.debug(
                "Non-numeric humidity '%s' on %s — forcing correction",
                actual_humidity,
                underlying_state.entity_id,
            )
            actual_humidity_f = None
        if actual_humidity_f is None or abs(actual_humidity_f - desired_target_humidity) > HUMIDITY_TOLERANCE:
            corrections[SERVICE_SET_HUMIDITY] = {ATTR_HUMIDITY: desired_target_humidity}

    # Preset mode
    if desired_preset_mode is not None:
        actual_preset = attrs.get("preset_mode")
        if actual_preset != desired_preset_mode:
            corrections[SERVICE_SET_PRESET_MODE] = {ATTR_PRESET_MODE: desired_preset_mode}

    # Fan mode
    if desired_fan_mode is not None:
        actual_fan = attrs.get("fan_mode")
        if actual_fan != desired_fan_mode:
            corrections[SERVICE_SET_FAN_MODE] = {ATTR_FAN_MODE: desired_fan_mode}

    # Swing mode (vertical)
    if desired_swing_mode is not None:
        actual_swing = attrs.get("swing_mode")
        if actual_swing != desired_swing_mode:
            corrections[SERVICE_SET_SWING_MODE] = {ATTR_SWING_MODE: desired_swing_mode}

    # Swing horizontal mode
    if desired_swing_horizontal_mode is not None:
        actual_swing_h = attrs.get("swing_horizontal_mode")
        if actual_swing_h != desired_swing_horizontal_mode:
            corrections[SERVICE_SET_SWING_HORIZONTAL_MODE] = {ATTR_SWING_HORIZONTAL_MODE: desired_swing_horizontal_mode}

    return corrections
