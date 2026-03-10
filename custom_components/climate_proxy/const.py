"""Constants for climate_proxy."""

from __future__ import annotations

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "climate_proxy"
INTEGRATION_NAME = "Climate Proxy"

# Config entry data keys (immutable after creation)
CONF_CLIMATE_ENTITY_ID = "climate_entity_id"
CONF_PROXY_NAME = "proxy_name"

# Config entry options keys (editable via Options Flow)
CONF_TEMPERATURE_SENSORS = "temperature_sensors"
CONF_HUMIDITY_SENSORS = "humidity_sensors"
CONF_SENSOR_ENTITY_ID = "entity_id"
CONF_SENSOR_WEIGHT = "weight"

# Defaults
DEFAULT_SENSOR_WEIGHT = 1.0

# Debounce window to prevent enforcement correction feedback loops
ENFORCEMENT_DEBOUNCE_SECONDS = 2.0

# Tolerance for floating-point comparison
TEMPERATURE_TOLERANCE = 0.1
HUMIDITY_TOLERANCE = 1.0

# Parallel updates: 0 = async-safe push integration (no polling)
PARALLEL_UPDATES = 0

# Restore state keys
RESTORE_KEY_HVAC_MODE = "hvac_mode"
RESTORE_KEY_TARGET_TEMP = "target_temperature"
RESTORE_KEY_TARGET_TEMP_LOW = "target_temperature_low"
RESTORE_KEY_TARGET_TEMP_HIGH = "target_temperature_high"
RESTORE_KEY_TARGET_HUMIDITY = "target_humidity"
RESTORE_KEY_PRESET_MODE = "preset_mode"
RESTORE_KEY_FAN_MODE = "fan_mode"
RESTORE_KEY_SWING_MODE = "swing_mode"
RESTORE_KEY_CURRENT_OFFSET = "current_offset"
RESTORE_KEY_IS_ON = "is_on"
RESTORE_KEY_CURRENT_OPTION = "current_option"
RESTORE_KEY_NATIVE_VALUE = "native_value"
RESTORE_KEY_PERCENTAGE = "percentage"
