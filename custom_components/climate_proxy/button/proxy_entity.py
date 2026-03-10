"""Button proxy entity — pass-through wrapper for an underlying HA button entity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import STATE_UNAVAILABLE

from ..const import LOGGER

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_registry import RegistryEntry

    from ..data import ClimateProxyConfigEntry
    from ..state_manager import ClimateProxyStateManager

PARALLEL_UPDATES = 0


class ClimateProxyButtonEntity(ButtonEntity):
    """
    Proxy for an underlying HA button entity.

    Buttons are stateless one-shot actions; there is no desired state to
    restore or enforce.  Pressing the proxy button immediately forwards a
    ``button.press`` service call to the underlying entity (if available).
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

    # ------------------------------------------------------------------
    # ButtonEntity commands
    # ------------------------------------------------------------------

    async def async_press(self) -> None:
        """Forward the press action to the underlying button entity."""
        underlying = self.hass.states.get(self._underlying_entity_id)
        if underlying is not None and underlying.state != STATE_UNAVAILABLE:
            await self.hass.services.async_call(
                "button",
                "press",
                {"entity_id": self._underlying_entity_id},
                blocking=False,
            )
        else:
            LOGGER.debug(
                "Button press for %s dropped — underlying entity unavailable",
                self._underlying_entity_id,
            )

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Always available — button press is best-effort."""
        return True
