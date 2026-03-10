"""Config flow schemas for climate_proxy."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.helpers import selector

from ...const import CONF_CLIMATE_ENTITY_ID, CONF_PROXY_NAME, DEFAULT_SENSOR_WEIGHT


def get_user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Schema for step 1: name + climate entity selection."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_PROXY_NAME,
                default=defaults.get(CONF_PROXY_NAME, vol.UNDEFINED),
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)),
            vol.Required(
                CONF_CLIMATE_ENTITY_ID,
                default=defaults.get(CONF_CLIMATE_ENTITY_ID, vol.UNDEFINED),
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="climate", multiple=False)),
        }
    )


def get_temperature_sensors_schema(current: list[str] | None = None) -> vol.Schema:
    """Schema for temperature sensor selection step."""
    return vol.Schema(
        {
            vol.Optional(
                "temperature_sensor_ids",
                default=current or [],
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="temperature",
                    multiple=True,
                )
            ),
        }
    )


def get_temperature_weights_schema(
    entity_ids: list[str], current_weights: dict[str, float] | None = None
) -> vol.Schema:
    """Dynamically build a schema with one weight input per selected temperature sensor."""
    current_weights = current_weights or {}
    schema_dict: dict[Any, Any] = {}
    for entity_id in entity_ids:
        schema_dict[vol.Optional(entity_id, default=current_weights.get(entity_id, DEFAULT_SENSOR_WEIGHT))] = (
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=10.0,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            )
        )
    return vol.Schema(schema_dict)


def get_humidity_sensors_schema(current: list[str] | None = None) -> vol.Schema:
    """Schema for humidity sensor selection step."""
    return vol.Schema(
        {
            vol.Optional(
                "humidity_sensor_ids",
                default=current or [],
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="humidity",
                    multiple=True,
                )
            ),
        }
    )


def get_humidity_weights_schema(entity_ids: list[str], current_weights: dict[str, float] | None = None) -> vol.Schema:
    """Dynamically build a schema with one weight input per selected humidity sensor."""
    current_weights = current_weights or {}
    schema_dict: dict[Any, Any] = {}
    for entity_id in entity_ids:
        schema_dict[vol.Optional(entity_id, default=current_weights.get(entity_id, DEFAULT_SENSOR_WEIGHT))] = (
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=10.0,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            )
        )
    return vol.Schema(schema_dict)


__all__ = [
    "get_humidity_sensors_schema",
    "get_humidity_weights_schema",
    "get_temperature_sensors_schema",
    "get_temperature_weights_schema",
    "get_user_schema",
]
