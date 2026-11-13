"""The FEMS integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CELLS_PER_MODULE,
    CONF_BATTERY_MODULE_COUNT,
    CONF_ENABLE_CELL_VOLTAGES,
    DEFAULT_BATTERY_MODULE_COUNT,
    DEFAULT_ENABLE_CELL_VOLTAGES,
    DOMAIN,
    MANUFACTURER,
    MAX_BATTERY_MODULE_COUNT,
    MODEL,
    PLATFORMS,
)
from .coordinator import FemsDataUpdateCoordinator
from .diagnostics_coordinator import FemsDiagnosticsCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the FEMS component."""
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.version == 1:
        _LOGGER.info(
            "Migrating FEMS config entry %s from version 1 to 2",
            entry.entry_id,
        )

        new_data = dict(entry.data)

        if CONF_BATTERY_MODULE_COUNT not in new_data:
            new_data[CONF_BATTERY_MODULE_COUNT] = DEFAULT_BATTERY_MODULE_COUNT
            _LOGGER.info(
                "Added missing %s=%s to config entry %s",
                CONF_BATTERY_MODULE_COUNT,
                DEFAULT_BATTERY_MODULE_COUNT,
                entry.entry_id,
            )

        hass.config_entries.async_update_entry(
            entry,
            data=new_data,
            version=2,
        )

    return True


def _remove_entity_if_exists(
    entity_registry: er.EntityRegistry,
    unique_id: str,
    domain: str = "sensor",
) -> None:
    """Remove entity from registry if it exists."""
    entity_id = entity_registry.async_get_entity_id(domain, DOMAIN, unique_id)
    if entity_id:
        _LOGGER.debug("Removing stale entity: %s (%s)", entity_id, unique_id)
        entity_registry.async_remove(entity_id)


async def _async_cleanup_dynamic_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove stale dynamic entities after option changes."""
    entity_registry = er.async_get(hass)

    module_count = entry.options.get(
        CONF_BATTERY_MODULE_COUNT,
        entry.data.get(CONF_BATTERY_MODULE_COUNT, DEFAULT_BATTERY_MODULE_COUNT),
    )
    enable_cell_voltages = entry.options.get(
        CONF_ENABLE_CELL_VOLTAGES,
        entry.data.get(CONF_ENABLE_CELL_VOLTAGES, DEFAULT_ENABLE_CELL_VOLTAGES),
    )

    # Modul-Spread-Entities oberhalb der konfigurierten Modulanzahl entfernen
    for module in range(module_count, MAX_BATTERY_MODULE_COUNT):
        unique_id = f"{entry.entry_id}_modul_{module}_spread"
        _remove_entity_if_exists(entity_registry, unique_id)

    # Zellspannungs-Entities entfernen, wenn deaktiviert
    # oder wenn sie oberhalb der konfigurierten Modulanzahl liegen
    for module in range(MAX_BATTERY_MODULE_COUNT):
        remove_module_cells = (not enable_cell_voltages) or (module >= module_count)

        if not remove_module_cells:
            continue

        for cell in range(CELLS_PER_MODULE):
            unique_id = (
                f"{entry.entry_id}_tower0_module{module}_cell{cell:03d}_voltage"
            )
            _remove_entity_if_exists(entity_registry, unique_id)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await _async_cleanup_dynamic_entities(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FEMS from a config entry."""
    await _async_cleanup_dynamic_entities(hass, entry)

    coordinator = FemsDataUpdateCoordinator(hass, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Initial FEMS refresh failed: {err}"
        ) from err

    diagnostics_coordinator = FemsDiagnosticsCoordinator(
        hass,
        entry,
        coordinator.rest_api,
    )

    try:
        await diagnostics_coordinator.async_config_entry_first_refresh()
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Initial FEMS diagnostics refresh failed: {err}"
        ) from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.data[DOMAIN][f"{entry.entry_id}_diagnostics"] = diagnostics_coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    device_registry = dr.async_get(hass)
    system_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_system")},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name="FEMS System",
    )

    # Register the battery parent before entities create diagnostic devices.
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{entry.entry_id}_battery")},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name="Battery",
        via_device_id=system_device.id,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_diagnostics", None)

    return unload_ok