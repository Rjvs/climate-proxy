"""Binary sensor proxy entity — pass-through wrapper for an underlying HA binary_sensor entity."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

if TYPE_CHECKING:
    from homeassistant.core import Event, EventStateChangedData
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_registry import RegistryEntry

    from ..data import ClimateProxyConfigEntry
    from ..state_manager import ClimateProxyStateManager

PARALLEL_UPDATES = 0


class ClimateProxyBinarySensorEntity(BinarySensorEntity):
    """
    Pass-through proxy for an underlying HA binary_sensor entity.

    Mirrors ``is_on``, ``device_class``, and availability from the underlying
    entity.  No desired state is stored or enforced — binary sensors are
    read-only pass-throughs.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        config_entry: ClimateProxyConfigEntry,
        underlying_entry: RegistryEntry,
        state_manager: ClimateProxyStateManager,
        device_info: DeviceInfo,
    ) -> None:
        """Initialise the binary sensor proxy entity."""
        self._config_entry = config_entry
        self._underlying_entry = underlying_entry
        self._state_manager = state_manager
        self._attr_device_info = device_info

        self._underlying_entity_id: str = underlying_entry.entity_id
        self._attr_unique_id = f"{config_entry.entry_id}_{underlying_entry.entity_id}"
        self._attr_name = underlying_entry.name or underlying_entry.original_name

        # Mirror device_class from registry entry when available
        if underlying_entry.device_class:
            with contextlib.suppress(ValueError):
                self._attr_device_class = BinarySensorDeviceClass(underlying_entry.device_class)

        # Subscription cleanup
        self._unsub_state_change: Any = None

    # ------------------------------------------------------------------
    # HA entity lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Subscribe to state changes of the underlying entity and bootstrap state."""
        await super().async_added_to_hass()

        # Register with state manager so batch refreshes can reach this entity
        self._state_manager.binary_sensor_proxy_entities.append(self)

        # Bootstrap device_class from current underlying state attributes
        state = self.hass.states.get(self._underlying_entity_id)
        if state is not None:
            self._refresh_device_class(state)

        self._unsub_state_change = async_track_state_change_event(
            self.hass,
            [self._underlying_entity_id],
            self._on_underlying_state_changed,
        )

        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel state change subscription and deregister from state manager."""
        if self._unsub_state_change is not None:
            self._unsub_state_change()
            self._unsub_state_change = None

        with contextlib.suppress(ValueError):
            self._state_manager.binary_sensor_proxy_entities.remove(self)

    # ------------------------------------------------------------------
    # BinarySensorEntity properties
    # ------------------------------------------------------------------

    @property
    def is_on(self) -> bool | None:
        """Return True when the underlying binary sensor is on."""
        state = self.hass.states.get(self._underlying_entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state.state == STATE_ON

    @property
    def available(self) -> bool:
        """Return False when the underlying entity is unavailable or unknown."""
        state = self.hass.states.get(self._underlying_entity_id)
        if state is None:
            return False
        return state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Mirror extra attributes from the underlying entity."""
        state = self.hass.states.get(self._underlying_entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        excluded = {"device_class", "friendly_name"}
        return {k: v for k, v in state.attributes.items() if k not in excluded} or None

    # ------------------------------------------------------------------
    # State change callback
    # ------------------------------------------------------------------

    @callback
    def _on_underlying_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle state_changed events from the underlying binary sensor entity."""
        new_state = event.data.get("new_state")
        if new_state is not None:
            self._refresh_device_class(new_state)
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_device_class(self, state: Any) -> None:
        """Mirror device_class from underlying entity state attributes."""
        raw_dc = state.attributes.get("device_class")
        if raw_dc is not None:
            try:
                self._attr_device_class = BinarySensorDeviceClass(raw_dc)
            except ValueError:
                self._attr_device_class = raw_dc  # type: ignore[assignment]
