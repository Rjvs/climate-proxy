"""Pass-through sensor entity that mirrors an underlying HA sensor entity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

from ..const import PARALLEL_UPDATES

if TYPE_CHECKING:
    from homeassistant.core import Event, EventStateChangedData
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_registry import RegistryEntry

    from ..data import ClimateProxyConfigEntry
    from ..state_manager import ClimateProxyStateManager

PARALLEL_UPDATES = PARALLEL_UPDATES  # noqa: PLW0127


class ClimateProxySensorEntity(SensorEntity):
    """
    A pass-through sensor entity that mirrors an underlying HA sensor entity.

    Subscribes to state changes of the underlying entity and reflects its
    native_value, native_unit_of_measurement, device_class, state_class, and
    extra_state_attributes onto this proxy entity.

    When the underlying entity is unavailable or unknown this entity marks
    itself unavailable as well.
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
        """Initialise the proxy sensor entity.

        Args:
            config_entry: The climate_proxy config entry.
            underlying_entry: The entity registry entry for the underlying sensor.
            state_manager: The shared state manager for this config entry.
            device_info: DeviceInfo that groups this entity under the proxy device.
        """
        self._config_entry = config_entry
        self._underlying_entry = underlying_entry
        self._state_manager = state_manager
        self._attr_device_info = device_info

        self.underlying_entity_id: str = underlying_entry.entity_id

        # Unique ID is scoped to this config entry so the same underlying entity
        # can be proxied by different config entries without collision.
        self._attr_unique_id = f"{config_entry.entry_id}_{underlying_entry.entity_id}"

        # Use the underlying entity's original name as the friendly name of this
        # proxy entity so the UI looks natural.
        self._attr_name = underlying_entry.name or underlying_entry.original_name

        # Unsubscribe callback returned by async_track_state_change_event.
        self._unsub_state_change: Any = None

        # Internal availability flag — True unless underlying is unavailable/unknown.
        self._underlying_available: bool = True

    # ------------------------------------------------------------------
    # HA entity lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Subscribe to state changes of the underlying entity."""
        await super().async_added_to_hass()

        # Register with the state manager so it can call async_write_ha_state()
        # when it decides a refresh is needed (e.g. batch climate updates).
        self._state_manager.sensor_proxy_entities.append(self)

        # Bootstrap state from whatever the underlying entity currently reports.
        self._refresh_from_underlying()

        # Subscribe to future changes on the underlying entity.
        self._unsub_state_change = async_track_state_change_event(
            self.hass,
            [self.underlying_entity_id],
            self._on_underlying_state_changed,
        )

        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from state change events and deregister from state manager."""
        if self._unsub_state_change is not None:
            self._unsub_state_change()
            self._unsub_state_change = None

        try:
            self._state_manager.sensor_proxy_entities.remove(self)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # State change callback
    # ------------------------------------------------------------------

    @callback
    def _on_underlying_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state_changed events from the underlying sensor entity."""
        self._refresh_from_underlying()
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_from_underlying(self) -> None:
        """Read the current state of the underlying entity and cache the values."""
        state = self.hass.states.get(self.underlying_entity_id)

        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._underlying_available = False
            return

        self._underlying_available = True

        # Mirror native_value — attempt float conversion for numeric sensors,
        # fall back to the raw string for non-numeric ones.
        raw = state.state
        try:
            self._attr_native_value = float(raw)
        except (ValueError, TypeError):
            self._attr_native_value = raw

        # Mirror unit, device class, state class
        self._attr_native_unit_of_measurement = state.attributes.get(
            "unit_of_measurement"
        )
        self._attr_device_class = state.attributes.get("device_class")
        self._attr_state_class = state.attributes.get("state_class")

    # ------------------------------------------------------------------
    # SensorEntity properties
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Return False when the underlying entity is unavailable or unknown."""
        return self._underlying_available

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional attributes from the underlying entity's state."""
        state = self.hass.states.get(self.underlying_entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None

        # Exclude standard HA attributes that are already surfaced via dedicated
        # SensorEntity properties so we don't duplicate them.
        excluded = {"unit_of_measurement", "device_class", "state_class", "friendly_name"}
        return {
            key: value
            for key, value in state.attributes.items()
            if key not in excluded
        } or None
