"""Base entity class for climate_proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


class ClimateProxyEntity(Entity):
    """
    Base entity class for climate_proxy.

    Provides:
    - Device info tied to the proxy config entry
    - Unique ID generation: {entry_id}_{underlying_entity_id}
    - has_entity_name = True (HA naming conventions)
    - should_poll = False (event-driven, no polling)
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        config_entry: ConfigEntry,
        underlying_entity_id: str,
        device_info: DeviceInfo,
    ) -> None:
        """
        Initialize the base entity.

        Args:
            config_entry: The config entry this entity belongs to.
            underlying_entity_id: Entity ID of the underlying HA entity being proxied.
            device_info: DeviceInfo for the proxy device.
        """
        self._config_entry = config_entry
        self._underlying_entity_id = underlying_entity_id
        self._attr_unique_id = f"{config_entry.entry_id}_{underlying_entity_id}"
        self._attr_device_info = device_info
