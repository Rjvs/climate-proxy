"""Shared helper functions for config and options flows."""

from __future__ import annotations

from typing import Any

from ..const import CONF_SENSOR_ENTITY_ID, CONF_SENSOR_WEIGHT


def build_sensor_list(entity_ids: list[str], weights: dict[str, float]) -> list[dict[str, Any]]:
    """Convert parallel lists of entity_ids and weights dict to sensor config list."""
    return [{CONF_SENSOR_ENTITY_ID: eid, CONF_SENSOR_WEIGHT: weights.get(eid, 1.0)} for eid in entity_ids]


def extract_entity_ids(sensor_list: list[dict[str, Any]]) -> list[str]:
    """Extract entity IDs from sensor config list."""
    return [s[CONF_SENSOR_ENTITY_ID] for s in sensor_list]


def extract_weights(sensor_list: list[dict[str, Any]]) -> dict[str, float]:
    """Extract {entity_id: weight} dict from sensor config list."""
    return {s[CONF_SENSOR_ENTITY_ID]: float(s.get(CONF_SENSOR_WEIGHT, 1.0)) for s in sensor_list}


__all__ = ["build_sensor_list", "extract_entity_ids", "extract_weights"]
