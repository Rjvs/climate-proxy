"""Unit tests for binary_sensor/proxy_entity.py — ClimateProxyBinarySensorEntity."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State

from custom_components.climate_proxy.binary_sensor.proxy_entity import (
    ClimateProxyBinarySensorEntity,
)


def _make_entity(
    underlying_entity_id: str = "binary_sensor.test_sensor",
    device_class: str | None = None,
) -> ClimateProxyBinarySensorEntity:
    """Build a ClimateProxyBinarySensorEntity with all dependencies mocked."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry"

    underlying_entry = MagicMock()
    underlying_entry.entity_id = underlying_entity_id
    underlying_entry.name = "Test Sensor"
    underlying_entry.original_name = "Test Sensor"
    underlying_entry.device_class = device_class

    state_manager = MagicMock()
    state_manager.binary_sensor_proxy_entities = []
    device_info = MagicMock()

    return ClimateProxyBinarySensorEntity(
        config_entry=config_entry,
        underlying_entry=underlying_entry,
        state_manager=state_manager,
        device_info=device_info,
    )


@pytest.mark.unit
class TestClimateProxyBinarySensorEntityInit:
    def test_unique_id_includes_entry_and_entity(self) -> None:
        entity = _make_entity()
        assert "test_entry" in entity.unique_id
        assert "binary_sensor.test_sensor" in entity.unique_id

    def test_name_uses_registry_entry_name(self) -> None:
        entity = _make_entity()
        assert entity._attr_name == "Test Sensor"

    def test_name_falls_back_to_original_name(self) -> None:
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry"
        underlying_entry = MagicMock()
        underlying_entry.entity_id = "binary_sensor.test"
        underlying_entry.name = None
        underlying_entry.original_name = "Original Name"
        underlying_entry.device_class = None
        entity = ClimateProxyBinarySensorEntity(
            config_entry=config_entry,
            underlying_entry=underlying_entry,
            state_manager=MagicMock(),
            device_info=MagicMock(),
        )
        assert entity._attr_name == "Original Name"

    def test_device_class_set_from_registry_entry(self) -> None:
        entity = _make_entity(device_class="motion")
        assert entity._attr_device_class == BinarySensorDeviceClass.MOTION

    def test_invalid_device_class_from_registry_ignored(self) -> None:
        entity = _make_entity(device_class="not_a_real_class")
        # Should not raise; device_class left at default (unset)
        assert entity._attr_device_class is None

    def test_no_device_class_when_registry_entry_has_none(self) -> None:
        entity = _make_entity(device_class=None)
        assert entity._attr_device_class is None


@pytest.mark.unit
class TestClimateProxyBinarySensorEntityProperties:
    def test_is_on_returns_true_when_underlying_on(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("binary_sensor.test_sensor", STATE_ON)
        )
        assert entity.is_on is True

    def test_is_on_returns_false_when_underlying_off(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("binary_sensor.test_sensor", STATE_OFF)
        )
        assert entity.is_on is False

    def test_is_on_returns_none_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("binary_sensor.test_sensor", STATE_UNAVAILABLE)
        )
        assert entity.is_on is None

    def test_is_on_returns_none_when_underlying_unknown(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("binary_sensor.test_sensor", STATE_UNKNOWN)
        )
        assert entity.is_on is None

    def test_is_on_returns_none_when_underlying_missing(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=None)
        assert entity.is_on is None

    def test_available_true_when_underlying_on(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("binary_sensor.test_sensor", STATE_ON)
        )
        assert entity.available is True

    def test_available_false_when_underlying_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("binary_sensor.test_sensor", STATE_UNAVAILABLE)
        )
        assert entity.available is False

    def test_available_false_when_underlying_unknown(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("binary_sensor.test_sensor", STATE_UNKNOWN)
        )
        assert entity.available is False

    def test_available_false_when_underlying_missing(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=None)
        assert entity.available is False

    def test_extra_state_attributes_returns_non_standard_attrs(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State(
                "binary_sensor.test_sensor",
                STATE_ON,
                attributes={
                    "device_class": "motion",
                    "friendly_name": "Motion Sensor",
                    "custom_attr": "custom_value",
                },
            )
        )
        attrs = entity.extra_state_attributes
        assert attrs is not None
        assert "custom_attr" in attrs
        assert "device_class" not in attrs
        assert "friendly_name" not in attrs

    def test_extra_state_attributes_returns_none_when_unavailable(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State("binary_sensor.test_sensor", STATE_UNAVAILABLE)
        )
        assert entity.extra_state_attributes is None

    def test_extra_state_attributes_returns_none_when_missing(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=None)
        assert entity.extra_state_attributes is None

    def test_extra_state_attributes_returns_none_when_no_extra_attrs(self) -> None:
        """When underlying only has excluded attrs, result is None (not empty dict)."""
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State(
                "binary_sensor.test_sensor",
                STATE_ON,
                attributes={"device_class": "motion", "friendly_name": "X"},
            )
        )
        assert entity.extra_state_attributes is None


@pytest.mark.unit
class TestClimateProxyBinarySensorEntityDeviceClass:
    def test_refresh_device_class_updates_from_state_attrs(self) -> None:
        entity = _make_entity()
        state = State(
            "binary_sensor.test_sensor",
            STATE_ON,
            attributes={"device_class": "window"},
        )
        entity._refresh_device_class(state)
        assert entity._attr_device_class == BinarySensorDeviceClass.WINDOW

    def test_refresh_device_class_preserves_unknown_string(self) -> None:
        entity = _make_entity()
        state = State(
            "binary_sensor.test_sensor",
            STATE_ON,
            attributes={"device_class": "totally_custom"},
        )
        entity._refresh_device_class(state)
        assert entity._attr_device_class == "totally_custom"

    def test_refresh_device_class_noop_when_attr_absent(self) -> None:
        entity = _make_entity(device_class="motion")
        state = State("binary_sensor.test_sensor", STATE_ON, attributes={})
        entity._refresh_device_class(state)
        # _attr_device_class unchanged from __init__
        assert entity._attr_device_class == BinarySensorDeviceClass.MOTION


@pytest.mark.unit
class TestClimateProxyBinarySensorEntityStateChange:
    def test_on_underlying_state_changed_is_callback(self) -> None:
        """_on_underlying_state_changed must be decorated with @callback."""
        entity = _make_entity()
        assert getattr(entity._on_underlying_state_changed, "_hass_callback", False) is True

    def test_on_underlying_state_changed_writes_ha_state(self) -> None:
        entity = _make_entity()
        entity.async_write_ha_state = MagicMock()

        event = MagicMock()
        event.data = {"new_state": State("binary_sensor.test_sensor", STATE_ON)}
        entity._on_underlying_state_changed(event)

        entity.async_write_ha_state.assert_called_once()

    def test_on_underlying_state_changed_refreshes_device_class(self) -> None:
        entity = _make_entity()
        entity.async_write_ha_state = MagicMock()

        new_state = State(
            "binary_sensor.test_sensor",
            STATE_ON,
            attributes={"device_class": "door"},
        )
        event = MagicMock()
        event.data = {"new_state": new_state}
        entity._on_underlying_state_changed(event)

        assert entity._attr_device_class == BinarySensorDeviceClass.DOOR

    def test_on_underlying_state_changed_handles_none_new_state(self) -> None:
        """Entity removed — new_state is None; should not refresh but still write state."""
        entity = _make_entity()
        entity.async_write_ha_state = MagicMock()

        event = MagicMock()
        event.data = {"new_state": None}
        entity._on_underlying_state_changed(event)

        entity.async_write_ha_state.assert_called_once()


@pytest.mark.unit
class TestClimateProxyBinarySensorEntityLifecycle:
    async def test_async_added_registers_with_state_manager(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=None)
        entity.async_write_ha_state = MagicMock()

        with patch(
            "custom_components.climate_proxy.binary_sensor.proxy_entity.async_track_state_change_event",
            return_value=MagicMock(),
        ):
            await entity.async_added_to_hass()

        assert entity in entity._state_manager.binary_sensor_proxy_entities

    async def test_async_added_subscribes_to_underlying(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(return_value=None)
        entity.async_write_ha_state = MagicMock()

        with patch(
            "custom_components.climate_proxy.binary_sensor.proxy_entity.async_track_state_change_event",
            return_value=MagicMock(),
        ) as mock_subscribe:
            await entity.async_added_to_hass()

        mock_subscribe.assert_called_once()
        entity_ids = mock_subscribe.call_args[0][1]
        assert "binary_sensor.test_sensor" in entity_ids

    async def test_async_added_bootstraps_device_class_from_state(self) -> None:
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.hass.states.get = MagicMock(
            return_value=State(
                "binary_sensor.test_sensor",
                STATE_ON,
                attributes={"device_class": "smoke"},
            )
        )
        entity.async_write_ha_state = MagicMock()

        with patch(
            "custom_components.climate_proxy.binary_sensor.proxy_entity.async_track_state_change_event",
            return_value=MagicMock(),
        ):
            await entity.async_added_to_hass()

        assert entity._attr_device_class == BinarySensorDeviceClass.SMOKE

    async def test_async_will_remove_cancels_subscription(self) -> None:
        entity = _make_entity()
        mock_unsub = MagicMock()
        entity._unsub_state_change = mock_unsub

        await entity.async_will_remove_from_hass()

        mock_unsub.assert_called_once()
        assert entity._unsub_state_change is None

    async def test_async_will_remove_deregisters_from_state_manager(self) -> None:
        entity = _make_entity()
        entity._state_manager.binary_sensor_proxy_entities = [entity]
        entity._unsub_state_change = MagicMock()

        await entity.async_will_remove_from_hass()

        assert entity not in entity._state_manager.binary_sensor_proxy_entities

    async def test_async_will_remove_tolerates_missing_from_state_manager(self) -> None:
        """Should not raise if entity is not in the list (e.g., added twice)."""
        entity = _make_entity()
        entity._unsub_state_change = MagicMock()
        # entity not in the list
        assert entity not in entity._state_manager.binary_sensor_proxy_entities
        await entity.async_will_remove_from_hass()  # must not raise
