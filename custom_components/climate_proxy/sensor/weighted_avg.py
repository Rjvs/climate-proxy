"""Computed weighted-average sensor entities for temperature and humidity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

from ..climate.offset_calculator import calculate_weighted_average
from ..const import CONF_HUMIDITY_SENSORS, CONF_TEMPERATURE_SENSORS

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

    from ..data import ClimateProxyConfigEntry
    from ..state_manager import ClimateProxyStateManager

PARALLEL_UPDATES = 0


class WeightedAvgTemperatureSensor(SensorEntity):
    """
    Diagnostic sensor that exposes the weighted average of all configured
    temperature sensors for this climate_proxy entry.

    Its value is recomputed on demand by reading the current HA state of each
    contributing sensor; no polling is required because the state manager calls
    async_write_ha_state() whenever any contributing sensor changes.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "weighted_avg_temperature"
    # Unit is Celsius by default; can be updated from underlying device capabilities
    # without changing this value because HA performs unit conversion automatically.
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        config_entry: ClimateProxyConfigEntry,
        state_manager: ClimateProxyStateManager,
        device_info: DeviceInfo,
    ) -> None:
        """Initialise the weighted average temperature sensor.

        Args:
            config_entry: The climate_proxy config entry (options hold sensor list).
            state_manager: Shared state manager; used for registration only.
            device_info: DeviceInfo that groups this entity under the proxy device.
        """
        self._config_entry = config_entry
        self._state_manager = state_manager
        self._attr_device_info = device_info

        self._attr_unique_id = f"{config_entry.entry_id}_weighted_avg_temperature"

    # ------------------------------------------------------------------
    # SensorEntity properties
    # ------------------------------------------------------------------

    @property
    def native_value(self) -> float | None:
        """Return the current weighted average temperature, or None if unavailable."""
        sensor_configs = self._config_entry.options.get(CONF_TEMPERATURE_SENSORS, [])
        if not sensor_configs:
            return None

        result = calculate_weighted_average(sensor_configs, self.hass)
        if result is not None:
            # Round to two decimal places to avoid spurious state changes from
            # floating-point noise.
            return round(result, 2)
        return None


class WeightedAvgHumiditySensor(SensorEntity):
    """
    Diagnostic sensor that exposes the weighted average of all configured
    humidity sensors for this climate_proxy entry.

    Its value is recomputed on demand by reading the current HA state of each
    contributing sensor; no polling is required because the state manager calls
    async_write_ha_state() whenever any contributing sensor changes.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "weighted_avg_humidity"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        config_entry: ClimateProxyConfigEntry,
        state_manager: ClimateProxyStateManager,
        device_info: DeviceInfo,
    ) -> None:
        """Initialise the weighted average humidity sensor.

        Args:
            config_entry: The climate_proxy config entry (options hold sensor list).
            state_manager: Shared state manager; used for registration only.
            device_info: DeviceInfo that groups this entity under the proxy device.
        """
        self._config_entry = config_entry
        self._state_manager = state_manager
        self._attr_device_info = device_info

        self._attr_unique_id = f"{config_entry.entry_id}_weighted_avg_humidity"

    # ------------------------------------------------------------------
    # SensorEntity properties
    # ------------------------------------------------------------------

    @property
    def native_value(self) -> float | None:
        """Return the current weighted average humidity, or None if unavailable."""
        sensor_configs = self._config_entry.options.get(CONF_HUMIDITY_SENSORS, [])
        if not sensor_configs:
            return None

        result = calculate_weighted_average(sensor_configs, self.hass)
        if result is not None:
            return round(result, 2)
        return None
