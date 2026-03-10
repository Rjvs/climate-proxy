"""Unit tests for button/proxy_entity.py — ClimateProxyButtonEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.climate_proxy.button.proxy_entity import ClimateProxyButtonEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State


def _make_entity() -> ClimateProxyButtonEntity:
    """Build a ClimateProxyButtonEntity with all dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = "button.test_button"
    underlying_entry.name = "Test Button"
    underlying_entry.original_name = "Test Button"

    state_manager = MagicMock()
    device_info = MagicMock()

    entity = ClimateProxyButtonEntity(
        config_entry=config_entry,
        underlying_entry=underlying_entry,
        state_manager=state_manager,
        device_info=device_info,
    )
    entity.hass = MagicMock()
    entity.hass.services.async_call = AsyncMock()
    return entity


@pytest.mark.unit
class TestClimateProxyButtonEntity:
    def test_unique_id_includes_entry_and_entity(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "button.test_button" in entity.unique_id

    def test_always_available(self) -> None:
        entity = _make_entity()
        assert entity.available is True

    async def test_async_press_calls_button_service_when_available(self) -> None:
        entity = _make_entity()
        # Use a datetime-like string to represent a previously-pressed (available) button;
        # STATE_UNKNOWN ("unknown") is filtered out by the proxy, so we avoid it here.
        entity.hass.states.get = MagicMock(return_value=State("button.test_button", "2024-01-01T00:00:00+00:00", {}))

        await entity.async_press()

        entity.hass.services.async_call.assert_called_once_with(
            "button",
            "press",
            {"entity_id": "button.test_button"},
            blocking=False,
        )

    async def test_async_press_dropped_when_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("button.test_button", STATE_UNAVAILABLE, {}))

        await entity.async_press()

        entity.hass.services.async_call.assert_not_called()

    async def test_async_press_dropped_when_unknown(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=State("button.test_button", STATE_UNKNOWN, {}))

        await entity.async_press()

        entity.hass.services.async_call.assert_not_called()

    async def test_async_press_dropped_when_state_is_none(self) -> None:
        entity = _make_entity()
        entity.hass.states.get = MagicMock(return_value=None)

        await entity.async_press()

        entity.hass.services.async_call.assert_not_called()
