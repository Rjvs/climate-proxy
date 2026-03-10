"""Fan proxy entity — MitM wrapper for an underlying HA fan entity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from ..const import LOGGER, RESTORE_KEY_IS_ON, RESTORE_KEY_PERCENTAGE, RESTORE_KEY_PRESET_MODE

if TYPE_CHECKING:
    from homeassistant.core import Event, EventStateChangedData, State
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_registry import RegistryEntry

    from ..data import ClimateProxyConfigEntry
    from ..state_manager import ClimateProxyStateManager

PARALLEL_UPDATES = 0


class ClimateProxyFanRestoreData(ExtraStoredData):
    """Persisted desired state for a fan proxy entity."""

    def __init__(
        self,
        is_on: bool,
        percentage: int | None,
        preset_mode: str | None,
    ) -> None:
        self._is_on = is_on
        self._percentage = percentage
        self._preset_mode = preset_mode

    def as_dict(self) -> dict[str, Any]:
        """Return the stored data as a plain dict."""
        return {
            RESTORE_KEY_IS_ON: self._is_on,
            RESTORE_KEY_PERCENTAGE: self._percentage,
            RESTORE_KEY_PRESET_MODE: self._preset_mode,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> ClimateProxyFanRestoreData:
        """Reconstruct from a previously persisted dict."""
        raw_pct = restored.get(RESTORE_KEY_PERCENTAGE)
        return cls(
            is_on=bool(restored.get(RESTORE_KEY_IS_ON, False)),
            percentage=int(raw_pct) if raw_pct is not None else None,
            preset_mode=restored.get(RESTORE_KEY_PRESET_MODE),
        )


class ClimateProxyFanEntity(FanEntity, RestoreEntity):
    """
    MitM proxy for an underlying HA fan entity.

    Stores the desired on/off state, percentage, and preset mode internally
    and enforces them on the underlying entity whenever they deviate.
    Mirrors preset_modes and detects supported features from the underlying
    entity's attributes.
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
        self._desired_percentage: int | None = None
        self._desired_preset_mode: str | None = None

        # Mirrored capabilities
        self._attr_preset_modes: list[str] | None = None
        self._attr_supported_features: FanEntityFeature = FanEntityFeature(0)

        # Subscription cleanup
        self._unsub_state_change: Any = None

    # ------------------------------------------------------------------
    # RestoreEntity lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore desired state, mirror capabilities, and subscribe to underlying entity changes."""
        await super().async_added_to_hass()

        has_restored_data = False
        last_extra = await self.async_get_last_extra_data()
        if last_extra is not None:
            restored = last_extra.as_dict()
            self._desired_is_on = bool(restored.get(RESTORE_KEY_IS_ON, False))
            raw_pct = restored.get(RESTORE_KEY_PERCENTAGE)
            self._desired_percentage = int(raw_pct) if raw_pct is not None else None
            self._desired_preset_mode = restored.get(RESTORE_KEY_PRESET_MODE)
            has_restored_data = True
            LOGGER.debug(
                "Restored fan desired state for %s: is_on=%s, percentage=%s, preset_mode=%s",
                self._underlying_entity_id,
                self._desired_is_on,
                self._desired_percentage,
                self._desired_preset_mode,
            )

        # Initialize capabilities and default state from current underlying state.
        # When no restore data exists (fresh install), seed desired state from the underlying so
        # enforcement does not immediately flip a device the user never changed.
        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is not None:
            self._mirror_capabilities(underlying)
            if not has_restored_data and underlying.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                self._desired_is_on = underlying.state == "on"
                raw_pct = underlying.attributes.get("percentage")
                self._desired_percentage = int(raw_pct) if raw_pct is not None else None
                self._desired_preset_mode = underlying.attributes.get("preset_mode")
                LOGGER.debug(
                    "Seeded fan desired state from underlying for %s: is_on=%s, percentage=%s, preset_mode=%s",
                    self._underlying_entity_id,
                    self._desired_is_on,
                    self._desired_percentage,
                    self._desired_preset_mode,
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
    def extra_restore_state_data(self) -> ClimateProxyFanRestoreData:
        """Return the desired state to persist across restarts."""
        return ClimateProxyFanRestoreData(
            self._desired_is_on,
            self._desired_percentage,
            self._desired_preset_mode,
        )

    # ------------------------------------------------------------------
    # FanEntity properties
    # ------------------------------------------------------------------

    @property
    def is_on(self) -> bool:
        """Return True if the proxy desired state is on."""
        return self._desired_is_on

    @property
    def percentage(self) -> int | None:
        """Return the current (desired) percentage."""
        return self._desired_percentage

    @property
    def preset_mode(self) -> str | None:
        """Return the current (desired) preset mode."""
        return self._desired_preset_mode

    @property
    def available(self) -> bool:
        """Always available — the proxy absorbs underlying unavailability."""
        return True

    # ------------------------------------------------------------------
    # FanEntity commands (MitM: store desired → push to device)
    # ------------------------------------------------------------------

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on: update desired state, write to HA, push to underlying entity."""
        self._desired_is_on = True
        if percentage is not None:
            self._desired_percentage = percentage
        if preset_mode is not None:
            self._desired_preset_mode = preset_mode
        self.async_write_ha_state()

        service_kwargs: dict[str, Any] = {}
        if percentage is not None:
            service_kwargs["percentage"] = percentage
        if preset_mode is not None:
            service_kwargs["preset_mode"] = preset_mode

        await self._push_or_queue("turn_on", service_kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off: update desired state, write to HA, push to underlying entity."""
        self._desired_is_on = False
        self.async_write_ha_state()
        await self._push_or_queue("turn_off", {})

    async def async_set_percentage(self, percentage: int) -> None:
        """Set speed percentage: update desired state, write to HA, push to underlying entity."""
        self._desired_percentage = percentage
        if percentage > 0:
            self._desired_is_on = True
        self.async_write_ha_state()
        await self._push_or_queue("set_percentage", {"percentage": percentage})

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode: update desired state, write to HA, push to underlying entity."""
        self._desired_preset_mode = preset_mode
        self._desired_is_on = True
        self.async_write_ha_state()
        await self._push_or_queue("set_preset_mode", {"preset_mode": preset_mode})

    # ------------------------------------------------------------------
    # Correction interface (called by StateManager)
    # ------------------------------------------------------------------

    def get_corrections(self, underlying_state: State) -> dict[str, dict[str, Any]]:
        """
        Return service calls needed to bring the underlying entity to desired state.

        Returns a dict of {service: kwargs} or an empty dict if no correction needed.
        Checks on/off state first, then percentage and preset mode.
        """
        corrections: dict[str, dict[str, Any]] = {}

        underlying_is_on = underlying_state.state == "on"

        if self._desired_is_on and not underlying_is_on:
            # Need to turn on; include percentage/preset if set
            turn_on_kwargs: dict[str, Any] = {}
            if self._desired_percentage is not None:
                turn_on_kwargs["percentage"] = self._desired_percentage
            if self._desired_preset_mode is not None:
                turn_on_kwargs["preset_mode"] = self._desired_preset_mode
            corrections["turn_on"] = turn_on_kwargs
            return corrections

        if not self._desired_is_on and underlying_is_on:
            corrections["turn_off"] = {}
            return corrections

        if underlying_is_on:
            # Check percentage deviation
            if self._desired_percentage is not None:
                attrs = underlying_state.attributes
                raw_pct = attrs.get("percentage")
                if raw_pct is not None:
                    try:
                        underlying_pct = int(raw_pct)
                        if underlying_pct != self._desired_percentage:
                            corrections["set_percentage"] = {"percentage": self._desired_percentage}
                    except (ValueError, TypeError):  # fmt: skip
                        pass

            # Check preset mode deviation
            if self._desired_preset_mode is not None:
                underlying_preset = underlying_state.attributes.get("preset_mode")
                if underlying_preset != self._desired_preset_mode:
                    corrections["set_preset_mode"] = {"preset_mode": self._desired_preset_mode}

        return corrections

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mirror_capabilities(self, state: State) -> None:
        """Mirror preset_modes and detect supported features from underlying entity attributes."""
        attrs = state.attributes

        preset_modes = attrs.get("preset_modes")
        if preset_modes:
            self._attr_preset_modes = list(preset_modes)

        features = FanEntityFeature(0)
        if attrs.get("percentage") is not None or attrs.get("percentage_step") is not None:
            features |= FanEntityFeature.SET_SPEED
        if preset_modes:
            features |= FanEntityFeature.PRESET_MODE

        # Detect TURN_ON / TURN_OFF (added in HA 2024.2).
        # Check the underlying entity's supported_features bitmask; fall back to checking
        # whether the entity has on/off state (all real fan entities do).
        underlying_features = attrs.get("supported_features", 0)
        try:
            underlying_features = int(underlying_features)
        except ValueError, TypeError:
            underlying_features = 0
        if underlying_features & FanEntityFeature.TURN_ON:
            features |= FanEntityFeature.TURN_ON
        if underlying_features & FanEntityFeature.TURN_OFF:
            features |= FanEntityFeature.TURN_OFF
        # If the underlying didn't advertise them but is a real fan (has on/off), add them anyway.
        if not (features & FanEntityFeature.TURN_ON) and state.state in ("on", "off"):
            features |= FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

        self._attr_supported_features = features

    @callback
    def _on_underlying_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle state_changed on the underlying entity (sync HA callback)."""
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return
        # Mirror capabilities on each change
        self._mirror_capabilities(new_state)
        self.hass.async_create_task(
            self._state_manager.async_enforce_control_entity(self._underlying_entity_id, "fan", new_state),
            name=f"climate_proxy:fan_enforce:{self._underlying_entity_id}",
        )

    async def _push_or_queue(self, service: str, kwargs: dict[str, Any]) -> None:
        """Push a fan service call to the underlying entity, or queue if unavailable."""
        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is not None and underlying.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            await self.hass.services.async_call(
                "fan",
                service,
                kwargs,
                blocking=False,
                target={"entity_id": self._underlying_entity_id},
            )
        else:
            LOGGER.debug(
                "Dropped fan command %s for %s (unavailable); will enforce on reconnect",
                service,
                self._underlying_entity_id,
            )
