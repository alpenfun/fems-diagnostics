"""Sensor platform for fems-diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CELLS_PER_MODULE,
    CONF_BATTERY_MODULE_COUNT,
    CONF_ENABLE_CELL_VOLTAGES,
    DEFAULT_BATTERY_MODULE_COUNT,
    DEFAULT_ENABLE_CELL_VOLTAGES,
    DOMAIN,
)
from .coordinator import FemsDataUpdateCoordinator
from .diagnostics_coordinator import FemsDiagnosticsCoordinator
from .entity import FemsCoordinatorEntity


def _rest_available(coordinator: Any) -> bool:
    """Return True if REST data is available."""
    return bool(coordinator.data.rest)


def _diagnostics_rest_available(coordinator: Any) -> bool:
    """Return True if diagnostics REST data is available."""
    return bool(coordinator.data.rest)


def _modbus_available(coordinator: FemsDataUpdateCoordinator) -> bool:
    """Return True if Modbus data is available."""
    return bool(coordinator.data.modbus)


@dataclass(frozen=True, kw_only=True)
class FemsSensorDescription(SensorEntityDescription):
    """Describe a FEMS sensor."""

    value_fn: Callable[[Any], Any]
    available_fn: Callable[[Any], bool] | None = None


def _rest_value(coordinator: Any, key: str) -> Any:
    """Return raw REST value."""
    return coordinator.data.rest.get(key)


def _rest_bool_value(coordinator: Any, key: str) -> int:
    """Return REST diagnostic flag as 0/1 instead of None."""
    value = coordinator.data.rest.get(key)
    return 1 if value in (True, 1, "1", "true", "True", "ON", "on") else 0


def _scaled_rest_value(
    coordinator: Any,
    key: str,
    divisor: float,
    precision: int,
) -> float | None:
    """Return scaled REST value."""
    value = coordinator.data.rest.get(key)
    if value is None:
        return None
    return round(value / divisor, precision)


def _scaled_modbus_value(
    coordinator: FemsDataUpdateCoordinator,
    key: str,
    divisor: float,
    precision: int,
) -> float | None:
    """Return scaled Modbus value."""
    value = coordinator.data.modbus.get(key)
    if value is None:
        return None
    return round(value / divisor, precision)


def _cell_voltage_rest_key(module: int, cell: int) -> str:
    """Return REST key for one cell voltage."""
    return f"battery0/Tower0Module{module}Cell{cell:03d}Voltage"


def _cell_voltage_value_fn(
    module: int,
    cell: int,
) -> Callable[[Any], float | None]:
    """Create value function for one cell voltage."""
    rest_key = _cell_voltage_rest_key(module, cell)

    def value_fn(coordinator: Any) -> float | None:
        return _scaled_rest_value(coordinator, rest_key, 1000, 3)

    return value_fn


def _module_cell_voltages(
    coordinator: Any,
    module: int,
) -> list[float]:
    """Return all available cell voltages for one module."""
    values: list[float] = []

    for cell in range(CELLS_PER_MODULE):
        value = _scaled_rest_value(
            coordinator,
            _cell_voltage_rest_key(module, cell),
            1000,
            3,
        )
        if value is not None:
            values.append(value)

    return values


def _module_spread_value_fn(
    module: int,
) -> Callable[[Any], float | None]:
    """Create value function for one module spread."""

    def value_fn(coordinator: Any) -> float | None:
        values = _module_cell_voltages(coordinator, module)
        if len(values) < 2:
            return None
        return round(max(values) - min(values), 3)

    return value_fn


def _battery_cell_voltage_spread(
    coordinator: Any,
) -> float | None:
    """Return overall battery cell voltage spread."""
    min_voltage = _scaled_rest_value(coordinator, "battery0/MinCellVoltage", 1000, 3)
    max_voltage = _scaled_rest_value(coordinator, "battery0/MaxCellVoltage", 1000, 3)

    if min_voltage is None or max_voltage is None:
        return None

    return round(max_voltage - min_voltage, 3)

def _battery_cell_voltage_spread_status(
    coordinator: Any,
) -> str | None:
    """Return evaluated status of battery cell voltage spread."""

    spread = _battery_cell_voltage_spread(coordinator)

    soc = _scaled_rest_value(coordinator, "battery0/Soc", 1, 1)
    current = _scaled_rest_value(coordinator, "battery0/Current", 10, 1)

    return _evaluate_spread(spread, soc, current)

def _charger_value_fn(
    charger_id: int,
    channel: str,
) -> Callable[[Any], Any]:
    """Create value function for one charger channel."""
    rest_key = f"charger{charger_id}/{channel}"

    def value_fn(coordinator: Any) -> Any:
        return _rest_value(coordinator, rest_key)

    return value_fn


def _charger_scaled_value_fn(
    charger_id: int,
    channel: str,
    divisor: float,
    precision: int,
) -> Callable[[Any], float | None]:
    """Create scaled value function for one charger channel."""
    rest_key = f"charger{charger_id}/{channel}"

    def value_fn(coordinator: Any) -> float | None:
        return _scaled_rest_value(
            coordinator,
            rest_key,
            divisor,
            precision,
        )

    return value_fn


def _build_charger_sensors(
    charger_ids: tuple[int, ...],
) -> list[FemsSensorDescription]:
    """Build sensors dynamically for detected FEMS chargers."""
    sensors: list[FemsSensorDescription] = []

    for charger_id in charger_ids:
        sensors.extend(
            [
                FemsSensorDescription(
                    key=f"charger{charger_id}_power",
                    translation_key="charger_power",
                    native_unit_of_measurement=UnitOfPower.WATT,
                    device_class=SensorDeviceClass.POWER,
                    state_class=SensorStateClass.MEASUREMENT,
                    value_fn=_charger_value_fn(
                        charger_id,
                        "ActualPower",
                    ),
                    available_fn=_rest_available,
                ),
                FemsSensorDescription(
                    key=f"charger{charger_id}_voltage",
                    translation_key="charger_voltage",
                    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                    device_class=SensorDeviceClass.VOLTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    value_fn=_charger_scaled_value_fn(
                        charger_id,
                        "Voltage",
                        1000,
                        1,
                    ),
                    available_fn=_rest_available,
                ),
                FemsSensorDescription(
                    key=f"charger{charger_id}_current",
                    translation_key="charger_current",
                    native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                    device_class=SensorDeviceClass.CURRENT,
                    state_class=SensorStateClass.MEASUREMENT,
                    value_fn=_charger_scaled_value_fn(
                        charger_id,
                        "Current",
                        1000,
                        1,
                    ),
                    available_fn=_rest_available,
                ),
            ]
        )

    return sensors
BASE_SENSORS: tuple[FemsSensorDescription, ...] = (
    FemsSensorDescription(
        key="battery_soc",
        translation_key="battery_soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _rest_value(c, "battery0/Soc"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_soh",
        translation_key="battery_soh",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _rest_value(c, "battery0/Soh"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_current",
        translation_key="battery_current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _rest_value(c, "battery0/Current"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_voltage_dc",
        translation_key="battery_voltage_dc",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _rest_value(c, "battery0/Voltage"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_pack_voltage",
        translation_key="battery_pack_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _scaled_rest_value(c, "battery0/Tower0PackVoltage", 10, 1),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_cycles",
        translation_key="battery_cycles",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _rest_value(c, "battery0/Tower0NoOfCycles"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_capacity",
        translation_key="battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda c: _scaled_rest_value(c, "battery0/Capacity", 1000, 3),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_state",
        translation_key="battery_state",
        value_fn=lambda c: _rest_value(c, "battery0/State"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_state_machine",
        translation_key="battery_state_machine",
        value_fn=lambda c: _rest_value(c, "battery0/StateMachine"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_start_stop",
        translation_key="battery_start_stop",
        value_fn=lambda c: _rest_value(c, "battery0/StartStop"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_min_cell_voltage",
        translation_key="battery_min_cell_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _scaled_rest_value(c, "battery0/MinCellVoltage", 1000, 3),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_max_cell_voltage",
        translation_key="battery_max_cell_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _scaled_rest_value(c, "battery0/MaxCellVoltage", 1000, 3),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="cell_voltage_spread",
        translation_key="cell_voltage_spread",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_battery_cell_voltage_spread,
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="cell_voltage_spread_status",
        translation_key="cell_voltage_spread_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_battery_cell_voltage_spread_status,
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_min_cell_temperature",
        translation_key="battery_min_cell_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _rest_value(c, "battery0/MinCellTemperature"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_max_cell_temperature",
        translation_key="battery_max_cell_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: _rest_value(c, "battery0/MaxCellTemperature"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="tower0_min_cell_voltage",
        translation_key="tower0_min_cell_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _scaled_rest_value(
            c, "battery0/Tower0MinCellVoltage", 1000, 3
        ),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="tower0_max_cell_voltage",
        translation_key="tower0_max_cell_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _scaled_rest_value(
            c, "battery0/Tower0MaxCellVoltage", 1000, 3
        ),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="tower0_min_temperature",
        translation_key="tower0_min_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _scaled_rest_value(c, "battery0/Tower0MinTemperature", 10, 1),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="tower0_max_temperature",
        translation_key="tower0_max_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _scaled_rest_value(c, "battery0/Tower0MaxTemperature", 10, 1),
        available_fn=_rest_available,
    ),








    FemsSensorDescription(
        key="battery_run_failed",
        translation_key="battery_run_failed",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/RunFailed"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="battery_modbus_communication_failed",
        translation_key="battery_modbus_communication_failed",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/ModbusCommunicationFailed"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="low_min_voltage_fault",
        translation_key="low_min_voltage_fault",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/LowMinVoltageFault"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="low_min_voltage_warning",
        translation_key="low_min_voltage_warning",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/LowMinVoltageWarning"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="low_min_voltage_fault_battery_stopped",
        translation_key="low_min_voltage_fault_battery_stopped",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(
            c, "battery0/LowMinVoltageFaultBatteryStopped"
        ),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="level1_cell_under_voltage",
        translation_key="level1_cell_under_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/Level1CellUnderVoltage"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="level2_cell_under_voltage",
        translation_key="level2_cell_under_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/Level2CellUnderVoltage"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="tower0_level1_cell_under_voltage",
        translation_key="tower0_level1_cell_under_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/Tower0Level1CellUnderVoltage"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="tower0_level2_cell_under_voltage",
        translation_key="tower0_level2_cell_under_voltage",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/Tower0Level2CellUnderVoltage"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="status_fault",
        translation_key="status_fault",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/StatusFault"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="status_warning",
        translation_key="status_warning",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/StatusWarning"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="status_alarm",
        translation_key="status_alarm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/StatusAlarm"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="tower0_status_fault",
        translation_key="tower0_status_fault",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/Tower0StatusFault"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="tower0_status_warning",
        translation_key="tower0_status_warning",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/Tower0StatusWarning"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="tower0_status_alarm",
        translation_key="tower0_status_alarm",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: _rest_bool_value(c, "battery0/Tower0StatusAlarm"),
        available_fn=_rest_available,
    ),
    FemsSensorDescription(
        key="ess_soc_modbus",
        translation_key="ess_soc_modbus",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("ess_soc"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="ess_power",
        translation_key="ess_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("ess_active_power"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="pv_power",
        translation_key="pv_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("production_dc_actual_power"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("grid_active_power"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="house_power",
        translation_key="house_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("consumption_active_power"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="ess_power_l1",
        translation_key="ess_power_l1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("ess_active_power_l1"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="ess_power_l2",
        translation_key="ess_power_l2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("ess_active_power_l2"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="ess_power_l3",
        translation_key="ess_power_l3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("ess_active_power_l3"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="grid_power_l1",
        translation_key="grid_power_l1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("grid_active_power_l1"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="grid_power_l2",
        translation_key="grid_power_l2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("grid_active_power_l2"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="grid_power_l3",
        translation_key="grid_power_l3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("grid_active_power_l3"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="house_power_l1",
        translation_key="house_power_l1",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("consumption_active_power_l1"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="house_power_l2",
        translation_key="house_power_l2",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("consumption_active_power_l2"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="house_power_l3",
        translation_key="house_power_l3",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("consumption_active_power_l3"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="ess_discharge_power",
        translation_key="ess_discharge_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.data.modbus.get("ess_discharge_power"),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="ess_active_charge_energy",
        translation_key="ess_active_charge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: _scaled_modbus_value(
            c, "ess_active_charge_energy", 1000, 3
        ),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="ess_active_discharge_energy",
        translation_key="ess_active_discharge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: _scaled_modbus_value(
            c, "ess_active_discharge_energy", 1000, 3
        ),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="grid_buy_energy",
        translation_key="grid_buy_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: _scaled_modbus_value(c, "grid_buy_active_energy", 1000, 3),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="grid_sell_energy",
        translation_key="grid_sell_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: _scaled_modbus_value(c, "grid_sell_active_energy", 1000, 3),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="pv_energy",
        translation_key="pv_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: _scaled_modbus_value(
            c, "production_active_energy", 1000, 3
        ),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="house_energy",
        translation_key="house_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: _scaled_modbus_value(
            c, "consumption_active_energy", 1000, 3
        ),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="battery_charge_energy",
        translation_key="battery_charge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: _scaled_modbus_value(c, "ess_dc_charge_energy", 1000, 3),
        available_fn=_modbus_available,
    ),
    FemsSensorDescription(
        key="battery_discharge_energy",
        translation_key="battery_discharge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: _scaled_modbus_value(
            c, "ess_dc_discharge_energy", 1000, 3
        ),
        available_fn=_modbus_available,
    ),
)


def _build_module_spread_sensors(module_count: int) -> list[FemsSensorDescription]:
    """Build module spread sensors dynamically."""
    sensors: list[FemsSensorDescription] = []

    for module in range(module_count):
        sensors.append(
            FemsSensorDescription(
                key=f"modul_{module}_spread",
                translation_key=f"modul_{module}_spread",
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                device_class=SensorDeviceClass.VOLTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
                value_fn=_module_spread_value_fn(module),
                available_fn=_diagnostics_rest_available,
            )
        )

    return sensors

def _evaluate_spread(
    spread: float | None,
    soc: float | None,
    current: float | None,
) -> str | None:
    """Evaluate cell voltage spread with context awareness."""

    if spread is None:
        return None

    # Schutz: keine Bewertung ohne Kontext
    if soc is None or current is None:
        return "not_evaluable"

    # Kontext: niedriger SOC
    if soc < 20:
        return "low_soc"

    # Kontext: hoher Strom
    if abs(current) > 5:
        return "under_load"

    # Normale Bewertung
    if spread < 0.02:
        return "normal"
    if spread <= 0.05:
        return "observe"

    return "critical"

def _build_cell_voltage_sensors(
    module_count: int,
    enabled_default: bool,
) -> list[FemsSensorDescription]:
    """Build cell voltage sensors dynamically."""
    sensors: list[FemsSensorDescription] = []

    for module in range(module_count):
        for cell in range(CELLS_PER_MODULE):
            sensors.append(
                FemsSensorDescription(
                    key=f"tower0_module{module}_cell{cell:03d}_voltage",
                    translation_key=f"tower0_module{module}_cell{cell:03d}_voltage",
                    native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                    device_class=SensorDeviceClass.VOLTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=enabled_default,
                    value_fn=_cell_voltage_value_fn(module, cell),
                    available_fn=_diagnostics_rest_available,
                )
            )

    return sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FEMS sensors."""
    coordinator: FemsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    diagnostics_coordinator: FemsDiagnosticsCoordinator = hass.data[DOMAIN][
        f"{entry.entry_id}_diagnostics"
    ]

    module_count = entry.options.get(
        CONF_BATTERY_MODULE_COUNT,
        entry.data.get(
            CONF_BATTERY_MODULE_COUNT,
            DEFAULT_BATTERY_MODULE_COUNT,
        ),
    )
    enable_cell_voltages = entry.options.get(
        CONF_ENABLE_CELL_VOLTAGES,
        entry.data.get(
            CONF_ENABLE_CELL_VOLTAGES,
            DEFAULT_ENABLE_CELL_VOLTAGES,
        ),
    )

    base_entities = [
        FemsSensorEntity(coordinator, description)
        for description in BASE_SENSORS
    ]

    charger_descriptions = _build_charger_sensors(
        coordinator.charger_ids or ()
    )

    charger_entities = [
        FemsSensorEntity(coordinator, description)
        for description in charger_descriptions
    ]
    diagnostics_descriptions = [
        *_build_module_spread_sensors(module_count),
    ]

    if enable_cell_voltages:
        diagnostics_descriptions.extend(
            _build_cell_voltage_sensors(
                module_count=module_count,
                enabled_default=False,
            )
        )

    diagnostics_entities = [
        FemsSensorEntity(diagnostics_coordinator, description)
        for description in diagnostics_descriptions
    ]

    async_add_entities(
        [
            *base_entities,
            *charger_entities,
            *diagnostics_entities,
        ]
    )

class FemsSensorEntity(FemsCoordinatorEntity, SensorEntity):
    """Representation of a FEMS sensor."""

    entity_description: FemsSensorDescription

    def __init__(
        self,
        coordinator: FemsDataUpdateCoordinator | FemsDiagnosticsCoordinator,
        description: FemsSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        if self.entity_description.available_fn is not None:
            return self.entity_description.available_fn(self.coordinator)
        return super().available