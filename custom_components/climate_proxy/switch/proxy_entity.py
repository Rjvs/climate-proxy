"""Switch proxy entity — MitM wrapper for an underlying HA switch entity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from ..const import LOGGER, PARALLEL_UPDATES, RESTORE_KEY_IS_ON

if TYPE_CHECKING:
    from homeassistant.core import Event, EventStateChangedData, State
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_registry import RegistryEntry

    from ..data import ClimateProxyConfigEntry
    from ..state_manager import ClimateProxyStateManager

PARALLEL_UPDATES = PARALLEL_UPDATES  # noqa: PLW0127


class ClimateProxySwitchRestoreData(ExtraStoredData):
    """Persisted desired state for a switch proxy entity."""

    def __init__(self, is_on: bool) -> None:
        self._is_on = is_on

    def as_dict(self) -> dict[str, Any]:
        return {RESTORE_KEY_IS_ON: self._is_on}

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> ClimateProxySwitchRestoreData:
        return cls(bool(restored.get(RESTORE_KEY_IS_ON, False)))


class ClimateProxySwitchEntity(SwitchEntity, RestoreEntity):
    """
    MitM proxy for an underlying HA switch entity.

    Stores the desired on/off state internally and enforces it on the
    underlying entity whenever it deviates (e.g. after a restart or
    unexpected state change).
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
        self._config_entry = config_entry
        self._underlying_entry = underlying_entry
        self._state_manager = state_manager
        self._attr_device_info = device_info

        self._underlying_entity_id: str = underlying_entry.entity_id
        self._attr_unique_id = f"{config_entry.entry_id}_{underlying_entry.entity_id}"
        self._attr_name = underlying_entry.name or underlying_entry.original_name

        # Desired state
        self._desired_is_on: bool = False

        # Subscription cleanup
        self._unsub_state_change: Any = None

    # ------------------------------------------------------------------
    # RestoreEntity lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore desired state and subscribe to underlying entity changes."""
        await super().async_added_to_hass()

        last_extra = await self.async_get_last_extra_data()
        if last_extra is not None:
            restored = last_extra.as_dict()
            self._desired_is_on = bool(restored.get(RESTORE_KEY_IS_ON, False))
            LOGGER.debug(
                "Restored switch desired state for %s: is_on=%s",
                self._underlying_entity_id,
                self._desired_is_on,
            )

        self._unsub_state_change = async_track_state_change_event(
            self.hass,
            [self._underlying_entity_id],
            self._on_underlying_state_changed,
        )

        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel state change subscription."""
        if self._unsub_state_change is not None:
            self._unsub_state_change()
            self._unsub_state_change = None

    @property
    def extra_restore_state_data(self) -> ClimateProxySwitchRestoreData:
        """Return the desired state to persist across restarts."""
        return ClimateProxySwitchRestoreData(self._desired_is_on)

    # ------------------------------------------------------------------
    # SwitchEntity properties
    # ------------------------------------------------------------------

    @property
    def is_on(self) -> bool:
        """Return True if the proxy desired state is on."""
        return self._desired_is_on

    @property
    def available(self) -> bool:
        """Always available — the proxy absorbs underlying unavailability."""
        return True

    # ------------------------------------------------------------------
    # SwitchEntity commands (MitM: store desired → push to device)
    # ------------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on: update desired state, write to HA, push to underlying entity."""
        self._desired_is_on = True
        self.async_write_ha_state()
        await self._push_or_queue("turn_on", {})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off: update desired state, write to HA, push to underlying entity."""
        self._desired_is_on = False
        self.async_write_ha_state()
        await self._push_or_queue("turn_off", {})

    # ------------------------------------------------------------------
    # Correction interface (called by StateManager)
    # ------------------------------------------------------------------

    def get_corrections(self, underlying_state: State) -> dict[str, dict[str, Any]]:
        """
        Return service calls needed to bring the underlying entity to desired state.

        Returns a dict of {service: kwargs} or an empty dict if no correction needed.
        """
        underlying_is_on = underlying_state.state == "on"
        if self._desired_is_on and not underlying_is_on:
            return {"turn_on": {}}
        if not self._desired_is_on and underlying_is_on:
            return {"turn_off": {}}
        return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_underlying_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state_changed on the underlying entity (sync HA callback)."""
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return
        self.hass.async_create_task(
            self._state_manager.async_enforce_control_entity(
                self._underlying_entity_id, "switch", new_state
            ),
            name=f"climate_proxy:switch_enforce:{self._underlying_entity_id}",
        )

    async def _push_or_queue(self, service: str, kwargs: dict[str, Any]) -> None:
        """Push a homeassistant service call to the underlying entity, or queue if unavailable."""
        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is not None and underlying.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            await self.hass.services.async_call(
                "homeassistant",
                service,
                {"entity_id": self._underlying_entity_id, **kwargs},
                blocking=False,
            )
        else:
            self._state_manager.queue_pending_state(service, kwargs)
            LOGGER.debug(
                "Queued switch command %s for %s (device unavailable)",
                service,
                self._underlying_entity_id,
            )
