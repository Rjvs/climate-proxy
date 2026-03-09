"""Custom types for climate_proxy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.const import Platform

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_registry import RegistryEntry
    from homeassistant.loader import Integration

    from .state_manager import ClimateProxyStateManager


type ClimateProxyConfigEntry = ConfigEntry[ClimateProxyData]


@dataclass
class ClimateProxyData:
    """Runtime data for a climate_proxy config entry."""

    state_manager: ClimateProxyStateManager
    integration: Integration
    discovered_entities: dict[Platform, list[RegistryEntry]] = field(default_factory=dict)
    active_platforms: list[Platform] = field(default_factory=list)
