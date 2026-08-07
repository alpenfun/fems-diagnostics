"""Base entity for fems-diagnostics"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL


_DEVICE_DEFINITIONS: dict[str, dict[str, str]] = {
    "system": {
        "suffix": "system",
        "name": "FEMS System",
    },
    "battery": {
        "suffix": "battery",
        "name": "Battery",
    },
    "battery_diagnose": {
        "suffix": "battery_diagnose",
        "name": "Battery Diagnostics",
    },
    "cell_diagnose": {
        "suffix": "cell_diagnose",
        "name": "Cell Diagnostics",
    },
    "charger0": {
        "suffix": "charger0",
        "name": "Charger 0",
    },
    "charger1": {
        "suffix": "charger1",
        "name": "Charger 1",
    },
    "energy_management": {
        "suffix": "energy_management",
        "name": "Energy Management",
    },
}


def _device_key_from_entity_key(entity_key: str) -> str:
    """Map an entity key to a logical Home Assistant device."""
    if entity_key.startswith("tower0_module"):
        return "cell_diagnose"

    if entity_key.startswith("modul_") and entity_key.endswith("_spread"):
        return "cell_diagnose"

    if entity_key in {
        "fault_status",
        "rest_communication",
        "modbus_communication",
        "system_ok",
        "system_warning",
        "system_error",
        "battery_run_failed",
        "battery_modbus_communication_failed",
        "low_min_voltage_fault",
        "low_min_voltage_warning",
        "low_min_voltage_fault_battery_stopped",
        "level1_cell_under_voltage",
        "level2_cell_under_voltage",
        "tower0_level1_cell_under_voltage",
        "tower0_level2_cell_under_voltage",
        "status_fault",
        "status_warning",
        "status_alarm",
        "tower0_status_fault",
        "tower0_status_warning",
        "tower0_status_alarm",
    }:
        return "battery_diagnose"

    if entity_key.startswith("charger"):
        prefix = entity_key.split("_", 1)[0]

        if prefix.startswith("charger") and prefix[7:].isdigit():
            return prefix

    if entity_key in {
        "ess_power",
        "pv_power",
        "grid_power",
        "house_power",
        "ess_power_l1",
        "ess_power_l2",
        "ess_power_l3",
        "grid_power_l1",
        "grid_power_l2",
        "grid_power_l3",
        "house_power_l1",
        "house_power_l2",
        "house_power_l3",
        "ess_discharge_power",
        "ess_active_charge_energy",
        "ess_active_discharge_energy",
        "grid_buy_energy",
        "grid_sell_energy",
        "pv_energy",
        "house_energy",
        "battery_charge_energy",
        "battery_discharge_energy",
    }:
        return "energy_management"

    if entity_key in {
        "battery_soc",
        "battery_soh",
        "battery_current",
        "battery_voltage_dc",
        "battery_pack_voltage",
        "battery_cycles",
        "battery_capacity",
        "battery_state",
        "battery_state_machine",
        "battery_start_stop",
        "battery_min_cell_voltage",
        "battery_max_cell_voltage",
        "battery_min_cell_temperature",
        "battery_max_cell_temperature",
        "cell_voltage_spread",
        "tower0_min_cell_voltage",
        "tower0_max_cell_voltage",
        "tower0_min_temperature",
        "tower0_max_temperature",
        "ess_soc_modbus",
    }:
        return "battery"

    return "battery"


class FemsCoordinatorEntity(CoordinatorEntity):
    """Base FEMS entity."""

    _attr_has_entity_name = True

    @property
    def _fems_entity_key(self) -> str:
        """Return entity key."""
        description = getattr(self, "entity_description", None)
        return getattr(description, "key", "")

    @property
    def _fems_device_key(self) -> str:
        """Return logical device key."""
        return _device_key_from_entity_key(self._fems_entity_key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        entry_id = self.coordinator.entry.entry_id

        system_identifier = (DOMAIN, f"{entry_id}_system")
        battery_identifier = (DOMAIN, f"{entry_id}_battery")

        device_key = self._fems_device_key

        if device_key.startswith("charger") and device_key[7:].isdigit():
            charger_id = device_key[7:]
            device_def = {
                "suffix": device_key,
                "name": f"Charger {charger_id}",
            }
        else:
            device_def = _DEVICE_DEFINITIONS[device_key]

        device_identifier = (DOMAIN, f"{entry_id}_{device_def['suffix']}")

        if device_key == "system":
            return DeviceInfo(
                identifiers={system_identifier},
                name=_DEVICE_DEFINITIONS["system"]["name"],
                manufacturer=MANUFACTURER,
                model=MODEL,
            )

        if device_key == "battery":
            return DeviceInfo(
                identifiers={battery_identifier},
                name=_DEVICE_DEFINITIONS["battery"]["name"],
                manufacturer=MANUFACTURER,
                model=MODEL,
                via_device=system_identifier,
            )

        if device_key in {"battery_diagnose", "cell_diagnose"}:
            return DeviceInfo(
                identifiers={device_identifier},
                name=device_def["name"],
                manufacturer=MANUFACTURER,
                model=MODEL,
                via_device=battery_identifier,
            )

        return DeviceInfo(
            identifiers={device_identifier},
            name=device_def["name"],
            manufacturer=MANUFACTURER,
            model=MODEL,
            via_device=system_identifier,
        )
