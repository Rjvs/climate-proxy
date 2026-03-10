"""Unit tests for entity_discovery.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.climate_proxy.state_manager.entity_discovery import discover_underlying_entities
from homeassistant.const import Platform


@pytest.mark.unit
class TestDiscoverUnderlyingEntities:
    """Tests for discover_underlying_entities()."""

    def _setup_mocks(
        self,
        climate_entity_id: str,
        device_id: str,
        other_entities: list[tuple[str, str]],  # (entity_id, domain)
    ) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
        """Build mock entity/device registry."""
        hass = MagicMock()

        climate_entry = MagicMock()
        climate_entry.entity_id = climate_entity_id
        climate_entry.device_id = device_id
        climate_entry.domain = "climate"

        device = MagicMock()
        device.id = device_id

        # Build other entity mocks
        other_mocks = []
        for eid, domain in other_entities:
            entry = MagicMock()
            entry.entity_id = eid
            entry.domain = domain
            other_mocks.append(entry)

        # All device entities = climate + others
        all_entries = [climate_entry, *other_mocks]

        entity_reg = MagicMock()
        entity_reg.async_get = MagicMock(return_value=climate_entry)

        device_reg = MagicMock()
        device_reg.async_get = MagicMock(return_value=device)

        with (
            patch(
                "custom_components.climate_proxy.state_manager.entity_discovery.er.async_get", return_value=entity_reg
            ),
            patch(
                "custom_components.climate_proxy.state_manager.entity_discovery.dr.async_get", return_value=device_reg
            ),
            patch(
                "custom_components.climate_proxy.state_manager.entity_discovery.er.async_entries_for_device",
                return_value=all_entries,
            ),
        ):
            return discover_underlying_entities(hass, climate_entity_id)

    def test_no_other_entities(self) -> None:
        result = self._setup_mocks("climate.test", "dev1", [])
        # climate entity itself is excluded
        assert result == {}

    def test_sensor_and_switch_entities(self) -> None:
        result = self._setup_mocks(
            "climate.test",
            "dev1",
            [
                ("sensor.temp", "sensor"),
                ("switch.lock", "switch"),
            ],
        )
        assert Platform.SENSOR in result
        assert Platform.SWITCH in result
        assert len(result[Platform.SENSOR]) == 1
        assert len(result[Platform.SWITCH]) == 1

    def test_unknown_platform_excluded(self) -> None:
        result = self._setup_mocks(
            "climate.test",
            "dev1",
            [("media_player.speaker", "media_player")],
        )
        assert result == {}

    def test_no_device_id_returns_empty(self) -> None:
        hass = MagicMock()
        climate_entry = MagicMock()
        climate_entry.device_id = None

        entity_reg = MagicMock()
        entity_reg.async_get = MagicMock(return_value=climate_entry)

        with patch(
            "custom_components.climate_proxy.state_manager.entity_discovery.er.async_get",
            return_value=entity_reg,
        ):
            result = discover_underlying_entities(hass, "climate.test")

        assert result == {}

    def test_entity_not_in_registry_returns_empty(self) -> None:
        hass = MagicMock()
        entity_reg = MagicMock()
        entity_reg.async_get = MagicMock(return_value=None)

        with patch(
            "custom_components.climate_proxy.state_manager.entity_discovery.er.async_get",
            return_value=entity_reg,
        ):
            result = discover_underlying_entities(hass, "climate.test")

        assert result == {}
