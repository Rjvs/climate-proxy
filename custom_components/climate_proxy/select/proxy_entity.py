"""Select proxy entity — MitM wrapper for an underlying HA select entity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from ..const import LOGGER, RESTORE_KEY_CURRENT_OPTION

if TYPE_CHECKING:
    from homeassistant.core import Event, EventStateChangedData, State
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_registry import RegistryEntry

    from ..data import ClimateProxyConfigEntry
    from ..state_manager import ClimateProxyStateManager

PARALLEL_UPDATES = 0


class ClimateProxySelectRestoreData(ExtraStoredData):
    """Persisted desired state for a select proxy entity."""

    def __init__(self, option: str | None) -> None:
        self._option = option

    def as_dict(self) -> dict[str, Any]:
        return {RESTORE_KEY_CURRENT_OPTION: self._option}

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> ClimateProxySelectRestoreData:
        return cls(restored.get(RESTORE_KEY_CURRENT_OPTION))


class ClimateProxySelectEntity(SelectEntity, RestoreEntity):
    """
    MitM proxy for an underlying HA select entity.

    Stores the desired selected option internally and enforces it on the
    underlying entity whenever it deviates.
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
        self._desired_option: str | None = None
        self._attr_options: list[str] = []

        # Subscription cleanup
        self._unsub_state_change: Any = None

    # ------------------------------------------------------------------
    # RestoreEntity lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore desired state, mirror options, and subscribe to underlying entity changes."""
        await super().async_added_to_hass()

        last_extra = await self.async_get_last_extra_data()
        if last_extra is not None:
            restored = last_extra.as_dict()
            self._desired_option = restored.get(RESTORE_KEY_CURRENT_OPTION)
            LOGGER.debug(
                "Restored select desired state for %s: option=%s",
                self._underlying_entity_id,
                self._desired_option,
            )

        # Initialize options and default option from current underlying state
        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is not None:
            self._attr_options = list(underlying.attributes.get("options", []))
            if self._desired_option is None and underlying.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                self._desired_option = underlying.state

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
    def extra_restore_state_data(self) -> ClimateProxySelectRestoreData:
        """Return the desired state to persist across restarts."""
        return ClimateProxySelectRestoreData(self._desired_option)

    # ------------------------------------------------------------------
    # SelectEntity properties
    # ------------------------------------------------------------------

    @property
    def current_option(self) -> str | None:
        """Return the current (desired) option."""
        return self._desired_option

    @property
    def available(self) -> bool:
        """Always available — the proxy absorbs underlying unavailability."""
        return True

    # ------------------------------------------------------------------
    # SelectEntity commands (MitM: store desired → push to device)
    # ------------------------------------------------------------------

    async def async_select_option(self, option: str) -> None:
        """Select an option: update desired state, write to HA, push to underlying entity."""
        self._desired_option = option
        self.async_write_ha_state()
        await self._push_or_queue("select_option", {"option": option})

    # ------------------------------------------------------------------
    # Correction interface (called by StateManager)
    # ------------------------------------------------------------------

    def get_corrections(self, underlying_state: State) -> dict[str, dict[str, Any]]:
        """
        Return service calls needed to bring the underlying entity to desired state.

        Returns a dict of {service: kwargs} or an empty dict if no correction needed.
        """
        if self._desired_option is None:
            return {}
        # Also refresh options list on each correction check
        options = list(underlying_state.attributes.get("options", []))
        if options:
            self._attr_options = options
        if underlying_state.state != self._desired_option:
            return {"select_option": {"option": self._desired_option}}
        return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @callback
    def _on_underlying_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state_changed on the underlying entity (sync HA callback)."""
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return
        # Mirror options list update
        options = list(new_state.attributes.get("options", []))
        if options:
            self._attr_options = options
        self.hass.async_create_task(
            self._state_manager.async_enforce_control_entity(
                self._underlying_entity_id, "select", new_state
            ),
            name=f"climate_proxy:select_enforce:{self._underlying_entity_id}",
        )

    async def _push_or_queue(self, service: str, kwargs: dict[str, Any]) -> None:
        """Push a select service call to the underlying entity, or queue if unavailable."""
        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is not None and underlying.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            await self.hass.services.async_call(
                "select",
                service,
                kwargs,
                blocking=False,
                target={"entity_id": self._underlying_entity_id},
            )
        else:
            LOGGER.debug(
                "Dropped select command %s for %s (unavailable); will enforce on reconnect",
                service,
                self._underlying_entity_id,
            )
