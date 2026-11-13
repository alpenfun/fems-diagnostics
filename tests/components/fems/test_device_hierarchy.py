"""Tests for the FEMS device registry hierarchy."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.helpers import device_registry as dr

from custom_components.fems.const import DOMAIN
from custom_components.fems.entity import FemsCoordinatorEntity


@pytest.mark.parametrize(
    ("entity_key", "device_suffix", "parent"),
    [
        ("battery_soc", "battery", "battery"),
        ("fault_status", "battery_diagnose", "battery"),
        ("tower0_module0_cell000_voltage", "cell_diagnose", "battery"),
        ("charger0_actual_power", "charger0", "system"),
        ("charger2_actual_power", "charger2", "system"),
        ("ess_power", "energy_management", "system"),
    ],
)
async def test_device_info_uses_parent_device_id(
    hass, mock_config_entry, entity_key, device_suffix, parent
) -> None:
    """DeviceInfo must use registry IDs and preserve the FEMS hierarchy."""
    entry = mock_config_entry
    entry.add_to_hass(hass)

    registry = dr.async_get(hass)
    system_device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_system")},
    )
    battery_device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_battery")},
        via_device_id=system_device.id,
    )

    coordinator = MagicMock()
    coordinator.entry = entry
    coordinator.hass = hass

    entity = FemsCoordinatorEntity(coordinator)
    entity.entity_description = MagicMock(key=entity_key)

    info = entity.device_info

    expected_parent_id = (
        battery_device.id if parent == "battery" else system_device.id
    )
    assert info.via_device_id == expected_parent_id
    assert info.identifiers == {(DOMAIN, f"{entry.entry_id}_{device_suffix}")}
