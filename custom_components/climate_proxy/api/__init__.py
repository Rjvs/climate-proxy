"""API package for climate_proxy."""

from .client import (
    ClimateProxyApiClient,
    ClimateProxyApiClientAuthenticationError,
    ClimateProxyApiClientCommunicationError,
    ClimateProxyApiClientError,
)

__all__ = [
    "ClimateProxyApiClient",
    "ClimateProxyApiClientAuthenticationError",
    "ClimateProxyApiClientCommunicationError",
    "ClimateProxyApiClientError",
]
