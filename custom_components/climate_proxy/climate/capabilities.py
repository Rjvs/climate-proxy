"""Capability detection for the proxied climate entity."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature

if TYPE_CHECKING:
    from homeassistant.core import State


def detect_supported_features(state: State) -> ClimateEntityFeature:
    """
    Derive ClimateEntityFeature flags by inspecting a live climate entity State.

    Checks the presence of specific attributes (not the underlying entity's own
    supported_features, which may differ) to ensure accurate proxying.
    """
    attrs = state.attributes
    features = ClimateEntityFeature(0)

    hvac_modes = attrs.get("hvac_modes", [])
    non_off_modes = [m for m in hvac_modes if m != HVACMode.OFF]
    if non_off_modes:
        features |= ClimateEntityFeature.TURN_ON
    if HVACMode.OFF in hvac_modes:
        features |= ClimateEntityFeature.TURN_OFF

    if "temperature" in attrs:
        features |= ClimateEntityFeature.TARGET_TEMPERATURE

    if "target_temp_low" in attrs or "target_temp_high" in attrs:
        features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

    if "target_humidity" in attrs:
        features |= ClimateEntityFeature.TARGET_HUMIDITY

    fan_modes = attrs.get("fan_modes")
    if fan_modes:
        features |= ClimateEntityFeature.FAN_MODE

    preset_modes = attrs.get("preset_modes")
    if preset_modes:
        features |= ClimateEntityFeature.PRESET_MODE

    swing_modes = attrs.get("swing_modes")
    if swing_modes:
        features |= ClimateEntityFeature.SWING_MODE

    if "aux_heat" in attrs:
        features |= ClimateEntityFeature.AUX_HEAT

    return features


def extract_hvac_modes(state: State) -> list[HVACMode]:
    """Return the list of HVACMode supported by the underlying entity."""
    raw = state.attributes.get("hvac_modes", [])
    result = []
    for mode in raw:
        with contextlib.suppress(ValueError):
            result.append(HVACMode(mode))
    return result or [HVACMode.OFF]


def extract_fan_modes(state: State) -> list[str] | None:
    """Return fan_modes list, or None if not supported."""
    return state.attributes.get("fan_modes") or None


def extract_preset_modes(state: State) -> list[str] | None:
    """Return preset_modes list, or None if not supported."""
    return state.attributes.get("preset_modes") or None


def extract_swing_modes(state: State) -> list[str] | None:
    """Return swing_modes list, or None if not supported."""
    return state.attributes.get("swing_modes") or None


def extract_min_max_temp(state: State) -> tuple[float, float]:
    """Return (min_temp, max_temp) from the underlying state."""
    min_temp = state.attributes.get("min_temp", 7.0)
    max_temp = state.attributes.get("max_temp", 35.0)
    return float(min_temp), float(max_temp)


def extract_temp_step(state: State) -> float:
    """Return target_temp_step from the underlying state."""
    step = state.attributes.get("target_temp_step", 0.5)
    return float(step)


def extract_temperature_unit(state: State) -> str:
    """Return the temperature unit used by the underlying entity."""
    return state.attributes.get("temperature_unit", UnitOfTemperature.CELSIUS)
