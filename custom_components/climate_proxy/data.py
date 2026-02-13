"""Custom types for climate_proxy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import ClimateProxyApiClient
    from .coordinator import ClimateProxyDataUpdateCoordinator


type ClimateProxyConfigEntry = ConfigEntry[ClimateProxyData]


@dataclass
class ClimateProxyData:
    """Data for climate_proxy."""

    client: ClimateProxyApiClient
    coordinator: ClimateProxyDataUpdateCoordinator
    integration: Integration
