"""
Config flow for climate_proxy.

5-step flow:
    1. async_step_user          — name + climate entity selection
    2. async_step_temp_sensors  — pick temperature sensors (optional)
    3. async_step_temp_weights  — set weight per sensor (skipped if none selected)
    4. async_step_humidity_sensors — pick humidity sensors (optional)
    5. async_step_humidity_weights — set weight per sensor (skipped if none selected)

Options flow runs steps 2–5 with current values pre-filled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant import config_entries

from ..const import (
    CONF_CLIMATE_ENTITY_ID,
    CONF_HUMIDITY_SENSORS,
    CONF_PROXY_NAME,
    CONF_SENSOR_ENTITY_ID,
    CONF_SENSOR_WEIGHT,
    CONF_TEMPERATURE_SENSORS,
    DOMAIN,
)
from .schemas.config import (
    get_humidity_sensors_schema,
    get_humidity_weights_schema,
    get_temperature_sensors_schema,
    get_temperature_weights_schema,
    get_user_schema,
)

if TYPE_CHECKING:
    pass


def _build_sensor_list(entity_ids: list[str], weights: dict[str, float]) -> list[dict[str, Any]]:
    """Convert parallel lists of entity_ids and weights dict to sensor config list."""
    return [
        {CONF_SENSOR_ENTITY_ID: eid, CONF_SENSOR_WEIGHT: weights.get(eid, 1.0)}
        for eid in entity_ids
    ]


def _extract_entity_ids(sensor_list: list[dict[str, Any]]) -> list[str]:
    """Extract entity IDs from sensor config list."""
    return [s[CONF_SENSOR_ENTITY_ID] for s in sensor_list]


def _extract_weights(sensor_list: list[dict[str, Any]]) -> dict[str, float]:
    """Extract {entity_id: weight} dict from sensor config list."""
    return {s[CONF_SENSOR_ENTITY_ID]: float(s.get(CONF_SENSOR_WEIGHT, 1.0)) for s in sensor_list}


class ClimateProxyConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for climate_proxy."""

    VERSION = 1

    def __init__(self) -> None:
        # Step 1 data
        self._proxy_name: str = ""
        self._climate_entity_id: str = ""
        # Step 2–3 data
        self._temp_sensor_ids: list[str] = []
        self._temp_sensors: list[dict[str, Any]] = []
        # Step 4–5 data
        self._humidity_sensor_ids: list[str] = []
        self._humidity_sensors: list[dict[str, Any]] = []

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ClimateProxyOptionsFlow:
        """Return the options flow handler."""
        return ClimateProxyOptionsFlow()

    # ------------------------------------------------------------------
    # Step 1: Name + climate entity
    # ------------------------------------------------------------------

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle initial setup: name and underlying climate entity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            climate_entity_id = user_input[CONF_CLIMATE_ENTITY_ID]

            # Validate the entity exists
            if self.hass.states.get(climate_entity_id) is None:
                errors[CONF_CLIMATE_ENTITY_ID] = "entity_not_found"
            else:
                # Prevent two proxies for the same underlying device
                await self.async_set_unique_id(climate_entity_id)
                self._abort_if_unique_id_configured()

                self._proxy_name = user_input[CONF_PROXY_NAME]
                self._climate_entity_id = climate_entity_id
                return await self.async_step_temp_sensors()

        return self.async_show_form(
            step_id="user",
            data_schema=get_user_schema(user_input),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Step 2: Temperature sensor selection
    # ------------------------------------------------------------------

    async def async_step_temp_sensors(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle temperature sensor selection."""
        if user_input is not None:
            self._temp_sensor_ids = user_input.get("temperature_sensor_ids", [])
            if self._temp_sensor_ids:
                return await self.async_step_temp_weights()
            else:
                self._temp_sensors = []
                return await self.async_step_humidity_sensors()

        return self.async_show_form(
            step_id="temp_sensors",
            data_schema=get_temperature_sensors_schema(self._temp_sensor_ids),
        )

    # ------------------------------------------------------------------
    # Step 3: Temperature sensor weights
    # ------------------------------------------------------------------

    async def async_step_temp_weights(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle weight assignment for temperature sensors."""
        if user_input is not None:
            self._temp_sensors = _build_sensor_list(self._temp_sensor_ids, {k: float(v) for k, v in user_input.items()})
            return await self.async_step_humidity_sensors()

        return self.async_show_form(
            step_id="temp_weights",
            data_schema=get_temperature_weights_schema(self._temp_sensor_ids),
        )

    # ------------------------------------------------------------------
    # Step 4: Humidity sensor selection
    # ------------------------------------------------------------------

    async def async_step_humidity_sensors(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle humidity sensor selection."""
        if user_input is not None:
            self._humidity_sensor_ids = user_input.get("humidity_sensor_ids", [])
            if self._humidity_sensor_ids:
                return await self.async_step_humidity_weights()
            else:
                self._humidity_sensors = []
                return self._create_entry()

        return self.async_show_form(
            step_id="humidity_sensors",
            data_schema=get_humidity_sensors_schema(self._humidity_sensor_ids),
        )

    # ------------------------------------------------------------------
    # Step 5: Humidity sensor weights
    # ------------------------------------------------------------------

    async def async_step_humidity_weights(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle weight assignment for humidity sensors."""
        if user_input is not None:
            self._humidity_sensors = _build_sensor_list(self._humidity_sensor_ids, {k: float(v) for k, v in user_input.items()})
            return self._create_entry()

        return self.async_show_form(
            step_id="humidity_weights",
            data_schema=get_humidity_weights_schema(self._humidity_sensor_ids),
        )

    # ------------------------------------------------------------------
    # Final: create config entry
    # ------------------------------------------------------------------

    def _create_entry(self) -> config_entries.ConfigFlowResult:
        return self.async_create_entry(
            title=self._proxy_name,
            data={
                CONF_PROXY_NAME: self._proxy_name,
                CONF_CLIMATE_ENTITY_ID: self._climate_entity_id,
            },
            options={
                CONF_TEMPERATURE_SENSORS: self._temp_sensors,
                CONF_HUMIDITY_SENSORS: self._humidity_sensors,
            },
        )


class ClimateProxyOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow — reconfigure sensors and weights after initial setup."""

    def __init__(self) -> None:
        self._temp_sensor_ids: list[str] = []
        self._temp_sensors: list[dict[str, Any]] = []
        self._humidity_sensor_ids: list[str] = []
        self._humidity_sensors: list[dict[str, Any]] = []

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Entry point — jump to temperature sensor selection."""
        # Pre-load current values
        current_temp = self.config_entry.options.get(CONF_TEMPERATURE_SENSORS, [])
        self._temp_sensor_ids = _extract_entity_ids(current_temp)
        current_humidity = self.config_entry.options.get(CONF_HUMIDITY_SENSORS, [])
        self._humidity_sensor_ids = _extract_entity_ids(current_humidity)
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
        current_weights = _extract_weights(current)

        if user_input is not None:
            self._temp_sensors = _build_sensor_list(self._temp_sensor_ids, {k: float(v) for k, v in user_input.items()})
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
        current_weights = _extract_weights(current)

        if user_input is not None:
            self._humidity_sensors = _build_sensor_list(self._humidity_sensor_ids, {k: float(v) for k, v in user_input.items()})
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


__all__ = ["ClimateProxyConfigFlowHandler", "ClimateProxyOptionsFlow"]
