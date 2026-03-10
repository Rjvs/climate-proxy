"""Unit tests for button/proxy_entity.py — ClimateProxyButtonEntity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State

from custom_components.climate_proxy.button.proxy_entity import ClimateProxyButtonEntity


def _make_entity(
    underlying_entity_id: str = "button.test_button",
) -> ClimateProxyButtonEntity:
    """Build a ClimateProxyButtonEntity with all dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = underlying_entity_id
    underlying_entry.name = "Test Button"
    underlying_entry.original_name = "Test Button"

    state_manager = MagicMock()
    device_info = MagicMock()

    return ClimateProxyButtonEntity(
        config_entry=config_entry,
        underlying_entry=underlying_entry,
        state_manager=state_manager,
        device_info=device_info,
    )


@pytest.mark.unit
class TestClimateProxyButtonEntityInit:
    def test_unique_id_includes_entry_and_entity(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "button.test_button" in entity.unique_id

    def test_name_uses_registry_entry_name(self) -> None:
        entity = _make_entity()
        assert entity._attr_name == "Test Button"

    def test_name_falls_back_to_original_name(self) -> None:
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        underlying_entry = MagicMock()
        underlying_entry.entity_id = "button.test"
        underlying_entry.name = None
        underlying_entry.original_name = "Original Button"
        entity = ClimateProxyButtonEntity(
            config_entry=config_entry,
            underlying_entry=underlying_entry,
            state_manager=MagicMock(),
            device_info=MagicMock(),
        )
        assert entity._attr_name == "Original Button"

    def test_should_poll_is_false(self) -> None:
        entity = _make_entity()
        assert entity._attr_should_poll is False

    def test_has_entity_name_is_true(self) -> None:
        entity = _make_entity()
        assert entity._attr_has_entity_name is True


@pytest.mark.unit
class TestClimateProxyButtonEntityAvailability:
    def test_is_always_available(self) -> None:
        """Buttons are best-effort; the proxy is always available."""
        entity = _make_entity()
        assert entity.available is True

    def test_available_even_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("button.test_button", STATE_UNAVAILABLE)
        )
        assert entity.available is True

    def test_available_even_when_underlying_missing(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=None)
        assert entity.available is True


@pytest.mark.unit
class TestClimateProxyButtonEntityPress:
    async def test_press_forwards_to_underlying_when_available(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("button.test_button", "unknown")
        )
        entity.hass.services.async_call = AsyncMock()

        await entity.async_press()

        entity.hass.services.async_call.assert_called_once_with(
            "button",
            "press",
            {"entity_id": "button.test_button"},
            blocking=False,
        )

    async def test_press_dropped_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("button.test_button", STATE_UNAVAILABLE)
        )
        entity.hass.services.async_call = AsyncMock()

        await entity.async_press()

        entity.hass.services.async_call.assert_not_called()

    async def test_press_dropped_when_underlying_unknown(self) -> None:
        """STATE_UNKNOWN (string 'unknown') is treated as unavailable for press."""
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("button.test_button", STATE_UNKNOWN)
        )
        entity.hass.services.async_call = AsyncMock()

        await entity.async_press()

        entity.hass.services.async_call.assert_not_called()

    async def test_press_dropped_when_underlying_missing(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=None)
        entity.hass.services.async_call = AsyncMock()

        await entity.async_press()

        entity.hass.services.async_call.assert_not_called()

    async def test_press_uses_button_domain(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("button.test_button", "unknown")
        )
        entity.hass.services.async_call = AsyncMock()

        await entity.async_press()

        call_args = entity.hass.services.async_call.call_args
        assert call_args[0][0] == "button"
        assert call_args[0][1] == "press"

    async def test_press_targets_correct_underlying_entity(self) -> None:
        entity = _make_entity(underlying_entity_id="button.my_specific_button")
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("button.my_specific_button", "unknown")
        )
        entity.hass.services.async_call = AsyncMock()

        await entity.async_press()

        call_kwargs = entity.hass.services.async_call.call_args[0][2]
        assert call_kwargs["entity_id"] == "button.my_specific_button"

    async def test_press_uses_blocking_false(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("button.test_button", "unknown")
        )
        entity.hass.services.async_call = AsyncMock()

        await entity.async_press()

        call_kwargs = entity.hass.services.async_call.call_args[1]
        assert call_kwargs.get("blocking") is False
