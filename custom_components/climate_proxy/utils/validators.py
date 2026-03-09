"""Validation utilities for climate_proxy."""

from __future__ import annotations

from typing import Any


def validate_config_value(value: Any, value_type: type, min_val: Any = None, max_val: Any = None) -> bool:
    """
    Validate a configuration value.

    Args:
        value: The value to validate
        value_type: Expected type of the value
        min_val: Optional minimum value (for numeric types)
        max_val: Optional maximum value (for numeric types)

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(value, value_type):
        return False

    if min_val is not None and value < min_val:
        return False

    if max_val is not None and value > max_val:
        return False

    return True
