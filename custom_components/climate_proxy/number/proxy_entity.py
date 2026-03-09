"""Number proxy entity — MitM wrapper for an underlying HA number entity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from ..const import LOGGER, PARALLEL_UPDATES, RESTORE_KEY_NATIVE_VALUE, TEMPERATURE_TOLERANCE

if TYPE_CHECKING:
    from homeassistant.core import Event, EventStateChangedData, State
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_registry import RegistryEntry

    from ..data import ClimateProxyConfigEntry
    from ..state_manager import ClimateProxyStateManager

PARALLEL_UPDATES = PARALLEL_UPDATES  # noqa: PLW0127


class ClimateProxyNumberRestoreData(ExtraStoredData):
    """Persisted desired state for a number proxy entity."""

    def __init__(self, value: float | None) -> None:
        self._value = value

    def as_dict(self) -> dict[str, Any]:
        return {RESTORE_KEY_NATIVE_VALUE: self._value}

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> ClimateProxyNumberRestoreData:
        raw = restored.get(RESTORE_KEY_NATIVE_VALUE)
        return cls(float(raw) if raw is not None else None)


class ClimateProxyNumberEntity(NumberEntity, RestoreEntity):
    """
    MitM proxy for an underlying HA number entity.

    Stores the desired numeric value internally and enforces it on the
    underlying entity whenever it deviates beyond TEMPERATURE_TOLERANCE.
    Mirrors min, max, step, mode, and unit_of_measurement from the
    underlying entity's attributes.
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
        self._desired_value: float | None = None

        # Mirrored capabilities (updated from underlying entity)
        self._attr_native_min_value: float = 0.0
        self._attr_native_max_value: float = 100.0
        self._attr_native_step: float = 1.0
        self._attr_mode: NumberMode = NumberMode.AUTO
        self._attr_native_unit_of_measurement: str | None = None

        # Subscription cleanup
        self._unsub_state_change: Any = None

    # ------------------------------------------------------------------
    # RestoreEntity lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore desired state, mirror capabilities, and subscribe to underlying entity changes."""
        await super().async_added_to_hass()

        last_extra = await self.async_get_last_extra_data()
        if last_extra is not None:
            restored = last_extra.as_dict()
            raw = restored.get(RESTORE_KEY_NATIVE_VALUE)
            self._desired_value = float(raw) if raw is not None else None
            LOGGER.debug(
                "Restored number desired state for %s: value=%s",
                self._underlying_entity_id,
                self._desired_value,
            )

        # Initialize capabilities and default value from current underlying state
        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is not None:
            self._mirror_capabilities(underlying)
            if self._desired_value is None and underlying.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                try:
                    self._desired_value = float(underlying.state)
                except (ValueError, TypeError):
                    pass

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
    def extra_restore_state_data(self) -> ClimateProxyNumberRestoreData:
        """Return the desired state to persist across restarts."""
        return ClimateProxyNumberRestoreData(self._desired_value)

    # ------------------------------------------------------------------
    # NumberEntity properties
    # ------------------------------------------------------------------

    @property
    def native_value(self) -> float | None:
        """Return the current (desired) value."""
        return self._desired_value

    @property
    def available(self) -> bool:
        """Always available — the proxy absorbs underlying unavailability."""
        return True

    # ------------------------------------------------------------------
    # NumberEntity commands (MitM: store desired → push to device)
    # ------------------------------------------------------------------

    async def async_set_native_value(self, value: float) -> None:
        """Set value: update desired state, write to HA, push to underlying entity."""
        self._desired_value = value
        self.async_write_ha_state()
        await self._push_or_queue("set_value", {"value": value})

    # ------------------------------------------------------------------
    # Correction interface (called by StateManager)
    # ------------------------------------------------------------------

    def get_corrections(self, underlying_state: State) -> dict[str, dict[str, Any]]:
        """
        Return service calls needed to bring the underlying entity to desired state.

        Uses TEMPERATURE_TOLERANCE for floating-point comparison.
        Returns a dict of {service: kwargs} or an empty dict if no correction needed.
        """
        if self._desired_value is None:
            return {}
        if underlying_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return {}
        try:
            underlying_value = float(underlying_state.state)
        except (ValueError, TypeError):
            return {}
        if abs(underlying_value - self._desired_value) > TEMPERATURE_TOLERANCE:
            return {"set_value": {"value": self._desired_value}}
        return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mirror_capabilities(self, state: State) -> None:
        """Mirror min, max, step, mode, and unit from underlying entity attributes."""
        attrs = state.attributes
        raw_min = attrs.get("min")
        if raw_min is not None:
            try:
                self._attr_native_min_value = float(raw_min)
            except (ValueError, TypeError):
                pass
        raw_max = attrs.get("max")
        if raw_max is not None:
            try:
                self._attr_native_max_value = float(raw_max)
            except (ValueError, TypeError):
                pass
        raw_step = attrs.get("step")
        if raw_step is not None:
            try:
                self._attr_native_step = float(raw_step)
            except (ValueError, TypeError):
                pass
        raw_mode = attrs.get("mode")
        if raw_mode is not None:
            try:
                self._attr_mode = NumberMode(raw_mode)
            except ValueError:
                pass
        self._attr_native_unit_of_measurement = attrs.get("unit_of_measurement")

    def _on_underlying_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle state_changed on the underlying entity (sync HA callback)."""
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return
        # Mirror capabilities on each change
        self._mirror_capabilities(new_state)
        self.hass.async_create_task(
            self._state_manager.async_enforce_control_entity(
                self._underlying_entity_id, "number", new_state
            ),
            name=f"climate_proxy:number_enforce:{self._underlying_entity_id}",
        )

    async def _push_or_queue(self, service: str, kwargs: dict[str, Any]) -> None:
        """Push a number service call to the underlying entity, or queue if unavailable."""
        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is not None and underlying.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            await self.hass.services.async_call(
                "number",
                service,
                {"entity_id": self._underlying_entity_id, **kwargs},
                blocking=False,
            )
        else:
            self._state_manager.queue_pending_state(service, kwargs)
            LOGGER.debug(
                "Queued number command %s for %s (device unavailable)",
                service,
                self._underlying_entity_id,
            )
