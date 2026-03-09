"""Repairs platform for climate_proxy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import issue_registry as ir

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow based on the issue_id."""
    if issue_id == "missing_configuration":
        return MissingConfigurationRepairFlow()
    return ConfirmRepairFlow()


class MissingConfigurationRepairFlow(RepairsFlow):
    """Handler for missing configuration repair."""

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Handle the initial repair step."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self.handler)
            if entry:
                ir.async_delete_issue(self.hass, entry.domain, "missing_configuration")
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="init")


class ConfirmRepairFlow(RepairsFlow):
    """Generic confirm-and-close handler for unrecognised issue IDs."""

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Handle the initial repair step."""
        if user_input is not None:
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="init")
