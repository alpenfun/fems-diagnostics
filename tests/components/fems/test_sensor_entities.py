"""Tests for FEMS sensor entity creation logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fems.const import (
    CONF_BATTERY_MODULE_COUNT,
    CONF_DIAGNOSTICS_INTERVAL,
    CONF_ENABLE_CELL_VOLTAGES,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_MODBUS_SLAVE,
    CONF_PASSWORD,
    CONF_REST_HOST,
    CONF_REST_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DOMAIN,
)
from custom_components.fems.sensor import async_setup_entry


def _build_entry(
    enable_cell_voltages: bool = True,
    battery_module_count: int = 7,
) -> MockConfigEntry:
    """Create a config entry for sensor tests."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="FEMS (192.168.11.104)",
        data={
            CONF_REST_HOST: "192.168.11.104",
            CONF_REST_PORT: 8084,
            CONF_MODBUS_HOST: "192.168.11.104",
            CONF_MODBUS_PORT: 502,
            CONF_MODBUS_SLAVE: 1,
            CONF_USERNAME: "x",
            CONF_PASSWORD: "user",
            CONF_BATTERY_MODULE_COUNT: battery_module_count,
        },
        options={
            CONF_SCAN_INTERVAL: 30,
            CONF_DIAGNOSTICS_INTERVAL: 120,
            CONF_BATTERY_MODULE_COUNT: battery_module_count,
            CONF_ENABLE_CELL_VOLTAGES: enable_cell_voltages,
        },
        unique_id="192.168.11.104:8084",
        entry_id="fems-test-entry",
    )


def _build_main_coordinator() -> MagicMock:
    """Create a mocked main coordinator."""
    coordinator = MagicMock()
    coordinator.data = MagicMock()
    coordinator.data.rest = {
        "battery0/Soc": 78,
        "battery0/Soh": 96,
        "battery0/MinCellVoltage": 3210,
        "battery0/MaxCellVoltage": 3290,
        "battery0/Tower0PackVoltage": 3645,
        "battery0/Tower0NoOfCycles": 123,
    }
    coordinator.data.modbus = {
        "ess_soc": 78,
        "ess_active_power": 1234.0,
    }
    coordinator.last_update_success = True
    coordinator.charger_ids = (0, 1, 2)
    return coordinator


def _build_diagnostics_coordinator(
    battery_module_count: int = 7,
    include_cell_voltages: bool = True,
) -> MagicMock:
    """Create a mocked diagnostics coordinator."""
    coordinator = MagicMock()
    coordinator.data = MagicMock()

    rest_data: dict[str, int] = {}

    for module in range(battery_module_count):
        rest_data[f"battery0/Tower0Module{module}Cell000Voltage"] = 3280 + module
        rest_data[f"battery0/Tower0Module{module}Cell001Voltage"] = 3281 + module

    if not include_cell_voltages:
        rest_data = {}

    coordinator.data.rest = rest_data
    coordinator.data.modbus = {}
    coordinator.last_update_success = True
    return coordinator


async def test_cell_voltage_entities_created_when_enabled(hass: HomeAssistant) -> None:
    """Test that cell voltage entities are created when enabled."""
    entry = _build_entry(enable_cell_voltages=True, battery_module_count=2)
    entry.add_to_hass(hass)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = _build_main_coordinator()
    hass.data[DOMAIN][f"{entry.entry_id}_diagnostics"] = _build_diagnostics_coordinator(
        battery_module_count=2,
        include_cell_voltages=True,
    )

    added_entities = []

    def _capture_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, entry, _capture_add_entities)

    entity_unique_ids = {entity.unique_id for entity in added_entities if hasattr(entity, "unique_id")}
    
    assert any("tower0_module0_cell000_voltage" in unique_id.lower() for unique_id in entity_unique_ids)
    assert any("tower0_module1_cell001_voltage" in unique_id.lower() for unique_id in entity_unique_ids)


async def test_cell_voltage_entities_not_created_when_disabled(hass: HomeAssistant) -> None:
    """Test that cell voltage entities are not created when disabled."""
    entry = _build_entry(enable_cell_voltages=False, battery_module_count=2)
    entry.add_to_hass(hass)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = _build_main_coordinator()
    hass.data[DOMAIN][f"{entry.entry_id}_diagnostics"] = _build_diagnostics_coordinator(
        battery_module_count=2,
        include_cell_voltages=True,
    )

    added_entities = []

    def _capture_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, entry, _capture_add_entities)

    entity_unique_ids = {entity.unique_id for entity in added_entities if hasattr(entity, "unique_id")}

    assert not any("tower0_module" in unique_id.lower() for unique_id in entity_unique_ids)


async def test_only_configured_modules_create_cell_entities(hass: HomeAssistant) -> None:
    """Test that only configured battery modules are represented."""
    entry = _build_entry(enable_cell_voltages=True, battery_module_count=2)
    entry.add_to_hass(hass)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = _build_main_coordinator()
    hass.data[DOMAIN][f"{entry.entry_id}_diagnostics"] = _build_diagnostics_coordinator(
        battery_module_count=2,
        include_cell_voltages=True,
    )

    added_entities = []

    def _capture_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, entry, _capture_add_entities)

    entity_unique_ids = {entity.unique_id for entity in added_entities if hasattr(entity, "unique_id")}

    assert any("tower0_module0_cell000_voltage" in unique_id.lower() for unique_id in entity_unique_ids)
    assert any("tower0_module1_cell000_voltage" in unique_id.lower() for unique_id in entity_unique_ids)
    assert not any("tower0_module2_" in unique_id.lower() for unique_id in entity_unique_ids)

async def test_dynamic_charger_entities_created(
    hass: HomeAssistant,
) -> None:
    """Test that sensors are created for all detected chargers."""
    entry = _build_entry(
        enable_cell_voltages=False,
        battery_module_count=2,
    )
    entry.add_to_hass(hass)

    main_coordinator = _build_main_coordinator()
    main_coordinator.entry = entry
    main_coordinator.charger_ids = (0, 1, 2)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = main_coordinator
    hass.data[DOMAIN][f"{entry.entry_id}_diagnostics"] = (
        _build_diagnostics_coordinator(
            battery_module_count=2,
            include_cell_voltages=False,
        )
    )

    added_entities = []

    def _capture_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(
        hass,
        entry,
        _capture_add_entities,
    )

    entity_unique_ids = {
        entity.unique_id
        for entity in added_entities
        if hasattr(entity, "unique_id")
    }

    for charger_id in (0, 1, 2):
        assert f"fems-test-entry_charger{charger_id}_power" in entity_unique_ids
        assert f"fems-test-entry_charger{charger_id}_voltage" in entity_unique_ids
        assert f"fems-test-entry_charger{charger_id}_current" in entity_unique_ids
