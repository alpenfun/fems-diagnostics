"""Tests for FEMS integration init and migration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import device_registry as dr

from custom_components.fems import async_migrate_entry, async_setup_entry, async_unload_entry
from custom_components.fems.const import (
    CONF_BATTERY_MODULE_COUNT,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_MODBUS_SLAVE,
    CONF_PASSWORD,
    CONF_REST_HOST,
    CONF_REST_PORT,
    CONF_USERNAME,
    DEFAULT_BATTERY_MODULE_COUNT,
    DOMAIN,
)


async def test_migrate_entry_v1_to_v2_adds_battery_module_count(hass) -> None:
    """Test migration from version 1 to version 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="FEMS old",
        version=1,
        data={
            CONF_REST_HOST: "192.168.11.104",
            CONF_REST_PORT: 8084,
            CONF_MODBUS_HOST: "192.168.11.104",
            CONF_MODBUS_PORT: 502,
            CONF_MODBUS_SLAVE: 1,
            CONF_USERNAME: "x",
            CONF_PASSWORD: "user",
        },
        entry_id="old-entry-id",
    )
    entry.add_to_hass(hass)

    migrated = await async_migrate_entry(hass, entry)

    assert migrated is True
    assert entry.version == 2
    assert entry.data[CONF_BATTERY_MODULE_COUNT] == DEFAULT_BATTERY_MODULE_COUNT


async def test_setup_and_unload_entry_smoke(
    hass,
    mock_config_entry,
    mock_forward_entry_setups,
    mock_unload_platforms,
) -> None:
    """Smoke test for setup and unload."""
    mock_config_entry.add_to_hass(hass)

    mock_main_coordinator = MagicMock()
    mock_main_coordinator.async_config_entry_first_refresh = AsyncMock()

    mock_diag_coordinator = MagicMock()
    mock_diag_coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "custom_components.fems.FemsDataUpdateCoordinator",
            return_value=mock_main_coordinator,
        ),
        patch(
            "custom_components.fems.FemsDiagnosticsCoordinator",
            return_value=mock_diag_coordinator,
        ),
    ):
        assert await async_setup_entry(hass, mock_config_entry) is True

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert f"{mock_config_entry.entry_id}_diagnostics" in hass.data[DOMAIN]

    mock_main_coordinator.async_config_entry_first_refresh.assert_awaited_once()
    mock_diag_coordinator.async_config_entry_first_refresh.assert_awaited_once()

    system_id = dr.async_get_device_id_by_identifier(
        hass, (DOMAIN, f"{mock_config_entry.entry_id}_system"),
        config_entry_id=mock_config_entry.entry_id,
    )
    battery_id = dr.async_get_device_id_by_identifier(
        hass, (DOMAIN, f"{mock_config_entry.entry_id}_battery"),
        config_entry_id=mock_config_entry.entry_id,
    )
    assert dr.async_get(hass).async_get(battery_id).via_device_id == system_id

    assert await async_unload_entry(hass, mock_config_entry) is True
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]
    assert f"{mock_config_entry.entry_id}_diagnostics" not in hass.data[DOMAIN]