"""Options flow for climate_proxy.

Allows the user to reconfigure external temperature/humidity sensors and their
weights after initial setup. Reloads the config entry automatically on save
(via OptionsFlowWithReload).

Steps (mirrors config flow steps 2–5):
    1. async_step_init           — pre-load current values, jump to step 2
    2. async_step_temp_sensors   — pick temperature sensors (optional)
    3. async_step_temp_weights   — set weight per sensor (skipped if none)
    4. async_step_humidity_sensors — pick humidity sensors (optional)
    5. async_step_humidity_weights — set weight per sensor (skipped if none)
"""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries

from ..const import CONF_HUMIDITY_SENSORS, CONF_TEMPERATURE_SENSORS
from .helpers import build_sensor_list, extract_entity_ids, extract_weights
from .schemas.config import (
    get_humidity_sensors_schema,
    get_humidity_weights_schema,
    get_temperature_sensors_schema,
    get_temperature_weights_schema,
)


class ClimateProxyOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle options flow — reconfigure sensors and weights after initial setup."""

    def __init__(self) -> None:
        """Initialise intermediate state for the multi-step options flow."""
        self._temp_sensor_ids: list[str] = []
        self._temp_sensors: list[dict[str, Any]] = []
        self._humidity_sensor_ids: list[str] = []
        self._humidity_sensors: list[dict[str, Any]] = []

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Entry point — pre-load current values then jump to temperature sensor selection."""
        current_temp = self.config_entry.options.get(CONF_TEMPERATURE_SENSORS, [])
        self._temp_sensor_ids = extract_entity_ids(current_temp)
        current_humidity = self.config_entry.options.get(CONF_HUMIDITY_SENSORS, [])
        self._humidity_sensor_ids = extract_entity_ids(current_humidity)
        return await self.async_step_temp_sensors()

    async def async_step_temp_sensors(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select temperature sensors."""
        if user_input is not None:
            self._temp_sensor_ids = user_input.get("temperature_sensor_ids", [])
            if self._temp_sensor_ids:
                return await self.async_step_temp_weights()
            self._temp_sensors = []
            return await self.async_step_humidity_sensors()

        return self.async_show_form(
            step_id="temp_sensors",
            data_schema=get_temperature_sensors_schema(self._temp_sensor_ids),
        )

    async def async_step_temp_weights(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Set weights for temperature sensors."""
        current = self.config_entry.options.get(CONF_TEMPERATURE_SENSORS, [])
        current_weights = extract_weights(current)

        if user_input is not None:
            self._temp_sensors = build_sensor_list(self._temp_sensor_ids, {k: float(v) for k, v in user_input.items()})
            return await self.async_step_humidity_sensors()

        return self.async_show_form(
            step_id="temp_weights",
            data_schema=get_temperature_weights_schema(self._temp_sensor_ids, current_weights),
        )

    async def async_step_humidity_sensors(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Select humidity sensors."""
        if user_input is not None:
            self._humidity_sensor_ids = user_input.get("humidity_sensor_ids", [])
            if self._humidity_sensor_ids:
                return await self.async_step_humidity_weights()
            self._humidity_sensors = []
            return self._create_options_entry()

        return self.async_show_form(
            step_id="humidity_sensors",
            data_schema=get_humidity_sensors_schema(self._humidity_sensor_ids),
        )

    async def async_step_humidity_weights(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Set weights for humidity sensors."""
        current = self.config_entry.options.get(CONF_HUMIDITY_SENSORS, [])
        current_weights = extract_weights(current)

        if user_input is not None:
            self._humidity_sensors = build_sensor_list(
                self._humidity_sensor_ids, {k: float(v) for k, v in user_input.items()}
            )
            return self._create_options_entry()

        return self.async_show_form(
            step_id="humidity_weights",
            data_schema=get_humidity_weights_schema(self._humidity_sensor_ids, current_weights),
        )

    def _create_options_entry(self) -> config_entries.ConfigFlowResult:
        return self.async_create_entry(
            data={
                CONF_TEMPERATURE_SENSORS: self._temp_sensors,
                CONF_HUMIDITY_SENSORS: self._humidity_sensors,
            }
        )


__all__ = ["ClimateProxyOptionsFlow"]
