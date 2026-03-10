"""Offset and weighted average calculations for climate_proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from ..const import CONF_SENSOR_ENTITY_ID, CONF_SENSOR_WEIGHT, DEFAULT_SENSOR_WEIGHT

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def calculate_weighted_average(
    sensor_configs: list[dict],
    hass: HomeAssistant,
) -> float | None:
    """
    Calculate a weighted average from a list of sensor configurations.

    Args:
        sensor_configs: List of dicts with 'entity_id' and 'weight' keys.
        hass: Home Assistant instance used to read sensor states.

    Returns:
        Weighted average as float, or None if all sensors are unavailable/unknown.
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for config in sensor_configs:
        entity_id = config[CONF_SENSOR_ENTITY_ID]
        weight = float(config.get(CONF_SENSOR_WEIGHT, DEFAULT_SENSOR_WEIGHT))

        state = hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
            continue

        try:
            value = float(state.state)
        except (ValueError, TypeError):  # fmt: skip
            continue

        weighted_sum += value * weight
        total_weight += weight

    if total_weight == 0.0:
        return None

    return weighted_sum / total_weight


def calculate_device_setpoint(
    proxy_target: float,
    device_internal_temp: float,
    external_temp: float,
    min_temp: float,
    max_temp: float,
) -> float:
    """
    Calculate the setpoint to send to the physical device when using external sensors.

    The offset corrects for the difference between where the device's internal
    sensor reads and what the external reference sensor reads. The device will
    stop heating/cooling when its internal sensor reaches device_setpoint, which
    happens exactly when the external sensor reaches proxy_target.

    Formula:
        offset = device_internal_temp - external_temp
        device_setpoint = clamp(proxy_target + offset, min_temp, max_temp)

    Args:
        proxy_target: The temperature the user wants the external sensor to reach.
        device_internal_temp: Current reading of the underlying device's built-in sensor.
        external_temp: Current weighted average of the external reference sensors.
        min_temp: Minimum temperature supported by the physical device.
        max_temp: Maximum temperature supported by the physical device.

    Returns:
        Setpoint to send to the physical device, clamped to [min_temp, max_temp].
    """
    offset = device_internal_temp - external_temp
    return max(min_temp, min(max_temp, proxy_target + offset))


def calculate_setpoint_range(
    proxy_target_low: float,
    proxy_target_high: float,
    device_internal_temp: float,
    external_temp: float,
    min_temp: float,
    max_temp: float,
) -> tuple[float, float]:
    """
    Calculate device setpoint range when using TARGET_TEMPERATURE_RANGE and external sensors.

    Args:
        proxy_target_low: Low bound of the user's desired temperature range.
        proxy_target_high: High bound of the user's desired temperature range.
        device_internal_temp: Device's built-in sensor reading.
        external_temp: Weighted average of external sensors.
        min_temp: Minimum temperature supported by the physical device.
        max_temp: Maximum temperature supported by the physical device.

    Returns:
        (device_setpoint_low, device_setpoint_high) clamped to [min_temp, max_temp].
    """
    offset = device_internal_temp - external_temp
    low = max(min_temp, min(max_temp, proxy_target_low + offset))
    high = max(min_temp, min(max_temp, proxy_target_high + offset))
    return low, high
