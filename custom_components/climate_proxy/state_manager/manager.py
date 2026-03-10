"""State manager for climate_proxy — replaces DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..const import CONF_CLIMATE_ENTITY_ID, ENFORCEMENT_DEBOUNCE_SECONDS, LOGGER
from .subscriptions import get_all_sensor_ids

if TYPE_CHECKING:
    from homeassistant.core import Event, EventStateChangedData, State

    from ..data import ClimateProxyConfigEntry


class ClimateProxyStateManager:
    """
    Event-driven state manager for a single climate_proxy config entry.

    Replaces the DataUpdateCoordinator — there is no polling cycle.
    All data arrives via state_changed events on the HA event bus.

    Lifecycle:
        async_setup()    — subscribe to events; call after platform entities are created
        async_teardown() — cancel all subscriptions; call from async_unload_entry
    """

    def __init__(self, hass: HomeAssistant, config_entry: ClimateProxyConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self._climate_entity_id: str = config_entry.data[CONF_CLIMATE_ENTITY_ID]
        self._unsub_callbacks: list[Any] = []

        # Reference to proxy entities — set by platform async_setup_entry callbacks
        self.climate_proxy_entity: Any = None  # ClimateProxyClimateEntity
        self.sensor_proxy_entities: list[Any] = []
        self.binary_sensor_proxy_entities: list[Any] = []
        self.switch_proxy_entities: dict[str, Any] = {}  # underlying_entity_id → entity
        self.select_proxy_entities: dict[str, Any] = {}
        self.number_proxy_entities: dict[str, Any] = {}
        self.button_proxy_entities: dict[str, Any] = {}
        self.fan_proxy_entities: dict[str, Any] = {}
        self.weighted_avg_entities: list[Any] = []

        # Pending desired state — applied when underlying device becomes available
        self.pending_state: dict[str, Any] = {}

        # Debounce: set True while pushing a correction to prevent feedback loops
        self._correcting = False
        self._debounce_task: asyncio.Task | None = None

    @property
    def debounce_active(self) -> bool:
        """Return True while a correction push is in progress (debounce window open)."""
        return self._correcting

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_setup(self) -> None:
        """Subscribe to state_changed events for the underlying device and sensors."""
        # Subscribe to underlying climate entity
        unsub_climate = async_track_state_change_event(
            self.hass,
            [self._climate_entity_id],
            self._on_climate_changed,
        )
        self._unsub_callbacks.append(unsub_climate)

        # Subscribe to all configured temperature and humidity sensors
        sensor_ids = get_all_sensor_ids(self.config_entry)
        if sensor_ids:
            unsub_sensors = async_track_state_change_event(
                self.hass,
                sensor_ids,
                self._on_sensor_changed,
            )
            self._unsub_callbacks.append(unsub_sensors)

        LOGGER.debug(
            "StateManager for %s subscribed to %s + %d sensors",
            self._climate_entity_id,
            self._climate_entity_id,
            len(sensor_ids),
        )

    async def async_teardown(self) -> None:
        """Cancel all event subscriptions."""
        for unsub in self._unsub_callbacks:
            unsub()
        self._unsub_callbacks.clear()
        if self._debounce_task is not None:
            self._debounce_task.cancel()
        LOGGER.debug("StateManager for %s torn down", self._climate_entity_id)

    # ------------------------------------------------------------------
    # Climate entity event handling
    # ------------------------------------------------------------------

    @callback
    def _on_climate_changed(self, event: Event[EventStateChangedData]) -> None:
        """React to state_changed on the underlying climate entity (sync callback)."""
        new_state = event.data.get("new_state")
        self.hass.async_create_task(
            self._async_handle_climate_changed(new_state),
            name=f"climate_proxy:climate_changed:{self._climate_entity_id}",
        )

    async def _async_handle_climate_changed(self, new_state: State | None) -> None:
        """
        Main handler called when the underlying climate entity changes state.

        1. If now available after being unavailable — drain pending_state queue.
        2. Update current_temperature / current_humidity on the proxy climate entity.
        3. For each MitM control entity: check if underlying value deviates from
           desired; if so and not within debounce window, push a correction.
        4. Notify all pass-through entities to refresh their state.
        """
        if new_state is None:
            return

        if self.climate_proxy_entity is not None:
            was_unavailable = self.climate_proxy_entity.underlying_was_unavailable

            # Notify proxy climate entity of the state change
            await self.climate_proxy_entity.async_on_underlying_state_changed(new_state)

            # If device just came back from unavailable, drain pending state
            if was_unavailable and new_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                await self._async_drain_pending_state()
                # Fall through: always enforce desired state after reconnect, even if
                # nothing was queued — the device may have come back in a different state.

            # Enforce desired state if not in debounce window
            if not self._correcting:
                await self._async_enforce_climate_state(new_state)

        # Notify pass-through sensor entities of new underlying climate state
        for entity in self.sensor_proxy_entities:
            if entity.underlying_entity_id == self._climate_entity_id:
                entity.async_write_ha_state()

    async def _async_enforce_climate_state(self, underlying_state: State) -> None:
        """Push corrections to underlying climate entity if desired state differs."""
        if self.climate_proxy_entity is None:
            return
        corrections = self.climate_proxy_entity.get_climate_corrections(underlying_state)
        if corrections:
            await self._start_debounce()
            for service, kwargs in corrections.items():
                await self.hass.services.async_call(
                    "climate",
                    service,
                    kwargs,
                    blocking=False,
                    target={"entity_id": self._climate_entity_id},
                )

    # ------------------------------------------------------------------
    # Sensor event handling (temperature / humidity sensors)
    # ------------------------------------------------------------------

    @callback
    def _on_sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        """React to state_changed on a temperature or humidity sensor."""
        self.hass.async_create_task(
            self._async_handle_sensor_changed(),
            name="climate_proxy:sensor_changed",
        )

    async def _async_handle_sensor_changed(self) -> None:
        """
        Recalculate weighted averages and update device setpoint offset.

        1. Recompute weighted average temperature and humidity.
        2. Notify weighted-avg sensor entities to write new state.
        3. If using external temperature sensors: recompute offset and push
           corrected device setpoint to underlying climate entity.
        """
        if self.climate_proxy_entity is not None:
            await self.climate_proxy_entity.async_on_sensor_changed()

        for entity in self.weighted_avg_entities:
            entity.async_write_ha_state()

    # ------------------------------------------------------------------
    # Control entity (switch / select / number / fan) enforcement
    # ------------------------------------------------------------------

    async def async_enforce_control_entity(
        self,
        underlying_entity_id: str,
        platform: str,
        underlying_state: State,
    ) -> None:
        """Check if a MitM control entity deviates from desired state and correct it.

        Check whether a MitM control entity's underlying state deviates from
        desired, and push a correction if needed.

        Called by the MitM entities themselves on state_changed.
        """
        if self._correcting:
            return

        entity: Any = None
        if platform == "switch":
            entity = self.switch_proxy_entities.get(underlying_entity_id)
        elif platform == "select":
            entity = self.select_proxy_entities.get(underlying_entity_id)
        elif platform == "number":
            entity = self.number_proxy_entities.get(underlying_entity_id)
        elif platform == "fan":
            entity = self.fan_proxy_entities.get(underlying_entity_id)

        if entity is None:
            return

        corrections = entity.get_corrections(underlying_state)
        if corrections:
            await self._start_debounce()
            for service, kwargs in corrections.items():
                await self.hass.services.async_call(
                    platform,
                    service,
                    kwargs,
                    blocking=False,
                    target={"entity_id": underlying_entity_id},
                )

    # ------------------------------------------------------------------
    # Pending state queue (used when underlying device is unavailable)
    # ------------------------------------------------------------------

    def queue_pending_state(self, key: str, value: Any) -> None:
        """Store a desired state key/value to be applied when device becomes available."""
        self.pending_state[key] = value

    async def _async_drain_pending_state(self) -> None:
        """Apply all queued pending state to the underlying device."""
        if not self.pending_state:
            return
        LOGGER.debug(
            "Draining %d pending state entries to %s",
            len(self.pending_state),
            self._climate_entity_id,
        )
        if self.climate_proxy_entity is not None:
            pending = dict(self.pending_state)
            self.pending_state.clear()
            await self.climate_proxy_entity.async_apply_pending_state(pending)
        else:
            self.pending_state.clear()

    # ------------------------------------------------------------------
    # Debounce helpers
    # ------------------------------------------------------------------

    async def _start_debounce(self) -> None:
        """Set correcting flag, clear it after ENFORCEMENT_DEBOUNCE_SECONDS."""
        self._correcting = True
        if self._debounce_task is not None:
            self._debounce_task.cancel()
        self._debounce_task = self.hass.async_create_task(
            self._clear_debounce(),
            name="climate_proxy:debounce_clear",
        )

    async def _clear_debounce(self) -> None:
        try:
            await asyncio.sleep(ENFORCEMENT_DEBOUNCE_SECONDS)
            self._correcting = False
        except asyncio.CancelledError:
            pass  # A newer debounce is now running; it will clear _correcting when it expires.
