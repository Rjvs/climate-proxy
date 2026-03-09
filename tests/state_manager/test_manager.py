"""Unit tests for state_manager/manager.py — ClimateProxyStateManager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import State

from custom_components.climate_proxy.state_manager.manager import ClimateProxyStateManager


def _make_manager() -> ClimateProxyStateManager:
    """Build a ClimateProxyStateManager with mocked hass and config_entry."""
    hass = MagicMock()
    hass.async_create_task = MagicMock()

    config_entry = MagicMock()
    config_entry.data = {"climate_entity_id": "climate.test_thermostat"}
    config_entry.options = {}

    return ClimateProxyStateManager(hass=hass, config_entry=config_entry)


@pytest.mark.unit
class TestStateManagerLifecycle:
    async def test_setup_subscribes_to_climate_entity(self) -> None:
        """async_setup registers a subscription for the climate entity."""
        manager = _make_manager()

        with patch(
            "custom_components.climate_proxy.state_manager.manager.async_track_state_change_event",
            return_value=MagicMock(),
        ) as mock_subscribe:
            await manager.async_setup()

        # At least one subscription call with the climate entity ID
        assert mock_subscribe.called
        first_call_entity_ids = mock_subscribe.call_args_list[0][0][1]
        assert "climate.test_thermostat" in first_call_entity_ids

    async def test_setup_subscribes_to_sensors_when_configured(self) -> None:
        """When sensors are configured, async_setup registers a second subscription."""
        hass = MagicMock()
        hass.async_create_task = MagicMock()

        config_entry = MagicMock()
        config_entry.data = {"climate_entity_id": "climate.test_thermostat"}
        config_entry.options = {
            "temperature_sensors": [
                {"entity_id": "sensor.bedroom", "weight": 1.0},
            ],
            "humidity_sensors": [],
        }

        manager = ClimateProxyStateManager(hass=hass, config_entry=config_entry)

        with patch(
            "custom_components.climate_proxy.state_manager.manager.async_track_state_change_event",
            return_value=MagicMock(),
        ) as mock_subscribe:
            await manager.async_setup()

        # Two subscriptions: climate + sensors
        assert mock_subscribe.call_count == 2

    async def test_teardown_cancels_subscriptions(self) -> None:
        """async_teardown calls all unsubscribe callbacks."""
        manager = _make_manager()
        unsub1 = MagicMock()
        unsub2 = MagicMock()
        manager._unsub_callbacks = [unsub1, unsub2]

        await manager.async_teardown()

        unsub1.assert_called_once()
        unsub2.assert_called_once()
        assert manager._unsub_callbacks == []

    async def test_teardown_cancels_debounce_task(self) -> None:
        """async_teardown cancels any pending debounce task."""
        manager = _make_manager()
        mock_task = MagicMock()
        manager._debounce_task = mock_task

        await manager.async_teardown()

        mock_task.cancel.assert_called_once()


@pytest.mark.unit
class TestPendingStateQueue:
    def test_queue_pending_state_stores_value(self) -> None:
        manager = _make_manager()
        manager.queue_pending_state("set_hvac_mode", {"hvac_mode": "heat"})
        assert manager.pending_state["set_hvac_mode"] == {"hvac_mode": "heat"}

    def test_queue_pending_state_overwrites_same_key(self) -> None:
        manager = _make_manager()
        manager.queue_pending_state("set_temperature", {"temperature": 20.0})
        manager.queue_pending_state("set_temperature", {"temperature": 22.0})
        assert manager.pending_state["set_temperature"]["temperature"] == 22.0

    async def test_drain_calls_apply_on_climate_proxy(self) -> None:
        manager = _make_manager()
        manager.queue_pending_state("set_hvac_mode", {"hvac_mode": "heat"})

        climate_proxy = MagicMock()
        climate_proxy.async_apply_pending_state = AsyncMock()
        manager.climate_proxy_entity = climate_proxy

        await manager._async_drain_pending_state()

        climate_proxy.async_apply_pending_state.assert_called_once_with(
            {"set_hvac_mode": {"hvac_mode": "heat"}}
        )
        assert manager.pending_state == {}

    async def test_drain_does_nothing_when_empty(self) -> None:
        manager = _make_manager()
        climate_proxy = MagicMock()
        climate_proxy.async_apply_pending_state = AsyncMock()
        manager.climate_proxy_entity = climate_proxy

        await manager._async_drain_pending_state()

        climate_proxy.async_apply_pending_state.assert_not_called()


@pytest.mark.unit
class TestControlEntityEnforcement:
    async def test_no_enforcement_during_debounce(self) -> None:
        """When _correcting is True, async_enforce_control_entity returns early."""
        manager = _make_manager()
        manager._correcting = True

        switch_entity = MagicMock()
        switch_entity.get_corrections = MagicMock(return_value={"turn_on": {}})
        manager.switch_proxy_entities["switch.test"] = switch_entity

        state = State("switch.test", "off")
        await manager.async_enforce_control_entity("switch.test", "switch", state)

        switch_entity.get_corrections.assert_not_called()

    async def test_enforcement_calls_service_for_switch(self) -> None:
        manager = _make_manager()
        manager.hass.services.async_call = AsyncMock()

        switch_entity = MagicMock()
        switch_entity.get_corrections = MagicMock(return_value={"turn_on": {}})
        manager.switch_proxy_entities["switch.test"] = switch_entity

        state = State("switch.test", "off")

        with patch.object(manager, "_start_debounce", new_callable=AsyncMock):
            await manager.async_enforce_control_entity("switch.test", "switch", state)

        manager.hass.services.async_call.assert_called_once_with(
            "switch",
            "turn_on",
            {},
            blocking=False,
            target={"entity_id": "switch.test"},
        )

    async def test_no_enforcement_for_unknown_entity(self) -> None:
        manager = _make_manager()
        manager.hass.services.async_call = AsyncMock()

        state = State("switch.unknown", "off")
        await manager.async_enforce_control_entity("switch.unknown", "switch", state)

        manager.hass.services.async_call.assert_not_called()
