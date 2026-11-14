"""Data update coordinator for fems-diagnostics."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BATTERY_MODULE_COUNT,
    CONF_DIAGNOSTICS_INTERVAL,
    CONF_MODBUS_HOST,
    CONF_MODBUS_PORT,
    CONF_MODBUS_SLAVE,
    CONF_PASSWORD,
    CONF_REST_HOST,
    CONF_REST_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_BATTERY_MODULE_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MODBUS_FLOAT32_HOLDING_REGISTERS,
    MODBUS_FLOAT64_HOLDING_REGISTERS,
    MODBUS_TIMEOUT,
    MODBUS_UINT16_INPUT_REGISTERS,
    REST_TIMEOUT,
)
from .fems_modbus import FemsModbusApi
from .fems_rest import FemsRestApi

_LOGGER = logging.getLogger(__name__)

REST_COLLECTION_TIMEOUT = max(REST_TIMEOUT, 20)


@dataclass
class FemsData:
    """Container for all fetched FEMS data."""

    rest: dict[str, Any]
    modbus: dict[str, Any]


class FemsDataUpdateCoordinator(DataUpdateCoordinator[FemsData]):
    """Coordinator for FEMS."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.entry = entry
        self.battery_module_count = entry.options.get(
            CONF_BATTERY_MODULE_COUNT,
            entry.data.get(
                CONF_BATTERY_MODULE_COUNT,
                DEFAULT_BATTERY_MODULE_COUNT,
            ),
        )
        self.scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            DEFAULT_SCAN_INTERVAL,
        )

        self.charger_ids: tuple[int, ...] | None = None

        session = async_get_clientsession(hass)
        self.rest_api = FemsRestApi(
            host=entry.data[CONF_REST_HOST],
            port=entry.data[CONF_REST_PORT],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=session,
        )
        self.modbus_api = FemsModbusApi(
            host=entry.data[CONF_MODBUS_HOST],
            port=entry.data[CONF_MODBUS_PORT],
            slave=entry.data[CONF_MODBUS_SLAVE],
        )

        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=self.scan_interval),
            always_update=False,
        )

    async def _async_discover_chargers(self) -> tuple[int, ...]:
        """Detect available FEMS charger components once at startup."""
        charger_ids: list[int] = []

        for charger_id in range(8):
            channel = f"charger{charger_id}/ActualPower"

            try:
                result = await self.rest_api.async_fetch_group(channel)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "FEMS charger discovery failed for charger%s: %r",
                    charger_id,
                    err,
                )
                continue

            if f"charger{charger_id}/ActualPower" in result:
                charger_ids.append(charger_id)

        _LOGGER.info(
            "Detected FEMS charger components: %s",
            ", ".join(f"charger{i}" for i in charger_ids) or "none",
        )

        return tuple(charger_ids)

    def _build_rest_groups(self) -> list[str]:
        """Build REST groups for the main coordinator."""
        battery_group = (
            "battery0/("
            "Soc|"
            "Soh|"
            "Current|"
            "Voltage|"
            "Tower0PackVoltage|"
            "Tower0NoOfCycles|"
            "Capacity|"
            "State|"
            "StateMachine|"
            "StartStop|"
            "RunFailed|"
            "ModbusCommunicationFailed|"
            "MinCellVoltage|"
            "MaxCellVoltage|"
            "MinCellTemperature|"
            "MaxCellTemperature|"
            "Tower0MinCellVoltage|"
            "Tower0MaxCellVoltage|"
            "Tower0MinTemperature|"
            "Tower0MaxTemperature|"
            "LowMinVoltageFault|"
            "LowMinVoltageWarning|"
            "LowMinVoltageFaultBatteryStopped|"
            "Level1CellUnderVoltage|"
            "Level2CellUnderVoltage|"
            "Tower0Level1CellUnderVoltage|"
            "Tower0Level2CellUnderVoltage|"
            "StatusFault|"
            "StatusWarning|"
            "StatusAlarm|"
            "Tower0StatusFault|"
            "Tower0StatusWarning|"
            "Tower0StatusAlarm"
            ")"
        )
        charger_groups = [
            f"charger{charger_id}/(ActualPower|Voltage|Current)"
            for charger_id in (self.charger_ids or ())
        ]

        return [
            battery_group,
            *charger_groups,
        ]

    async def _async_fetch_rest_group(
        self,
        group: str,
    ) -> tuple[str, dict[str, Any] | Exception]:
        """Fetch one REST group."""
        try:
            result = await self.rest_api.async_fetch_group(group)
            return group, result
        except Exception as err:  # noqa: BLE001
            return group, err

    async def _async_fetch_rest_data(self) -> dict[str, Any]:
        """Fetch all REST data and keep partial results."""

        if self.charger_ids is None:
            self.charger_ids = await self._async_discover_chargers()

        groups = self._build_rest_groups()
        rest: dict[str, Any] = {}
        errors: list[tuple[str, Exception]] = []

        task_to_group: dict[asyncio.Task, str] = {}
        tasks: list[asyncio.Task] = []

        for group in groups:
            task = asyncio.create_task(self._async_fetch_rest_group(group))
            task_to_group[task] = group
            tasks.append(task)

        try:
            done, pending = await asyncio.wait(
                tasks,
                timeout=REST_COLLECTION_TIMEOUT,
            )

            for task in done:
                group, result = await task
                if isinstance(result, Exception):
                    errors.append((group, result))
                    _LOGGER.debug("FEMS REST group failed: %s | %r", group, result)
                    continue
                rest.update(result)

            if pending:
                pending_groups = [task_to_group[task] for task in pending]
                _LOGGER.warning(
                    "FEMS REST collection reached timeout after %ss; %s request(s) still pending: %s",
                    REST_COLLECTION_TIMEOUT,
                    len(pending_groups),
                    pending_groups,
                )

                for task in pending:
                    task.cancel()

                cancelled = await asyncio.gather(*pending, return_exceptions=True)
                for task, item in zip(pending, cancelled, strict=False):
                    group = task_to_group[task]
                    if isinstance(item, Exception) and not isinstance(
                        item, asyncio.CancelledError
                    ):
                        _LOGGER.debug(
                            "Cancelled REST task result for %s: %r",
                            group,
                            item,
                        )

                errors.append(
                    (
                        "REST_COLLECTION_TIMEOUT",
                        TimeoutError(
                            f"{len(pending_groups)} REST request(s) did not finish in time: {pending_groups}"
                        ),
                    )
                )

        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

        if errors and rest:
            _LOGGER.warning(
                "FEMS REST partial data: %s request(s) failed or timed out; keeping %s value(s)",
                len(errors),
                len(rest),
            )

        if not rest:
            first_group, first_error = errors[0] if errors else (
                "unknown",
                RuntimeError("No REST data received"),
            )
            raise UpdateFailed(
                f"REST update failed completely; first failing group: {first_group}; error: {first_error}"
            ) from first_error

        return rest

    async def _async_fetch_modbus_data_internal(self) -> dict[str, Any]:
        """Fetch all Modbus data without timeout wrapper."""
        await self.modbus_api.async_connect()

        modbus_uint16_task = self.modbus_api.async_read_many_uint16_input(
            MODBUS_UINT16_INPUT_REGISTERS
        )
        modbus_float32_task = self.modbus_api.async_read_many_float32(
            MODBUS_FLOAT32_HOLDING_REGISTERS
        )
        modbus_float64_task = self.modbus_api.async_read_many_float64(
            MODBUS_FLOAT64_HOLDING_REGISTERS
        )

        modbus_uint16, modbus_float32, modbus_float64 = await asyncio.gather(
            modbus_uint16_task,
            modbus_float32_task,
            modbus_float64_task,
        )

        modbus: dict[str, Any] = {}
        modbus.update(modbus_uint16)
        modbus.update(modbus_float32)
        modbus.update(modbus_float64)
        return modbus

    async def _async_fetch_modbus_data(self) -> dict[str, Any]:
        """Fetch all Modbus data with timeout handling."""
        try:
            return await asyncio.wait_for(
                self._async_fetch_modbus_data_internal(),
                timeout=MODBUS_TIMEOUT,
            )
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Modbus update timed out") from err
        except UpdateFailed:
            raise
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Modbus update failed: {err}") from err
        finally:
            await self.modbus_api.async_close()

    async def _async_update_data(self) -> FemsData:
        """Fetch data from REST and Modbus."""
        rest: dict[str, Any] = {}
        modbus: dict[str, Any] = {}

        rest_error: Exception | None = None
        modbus_error: Exception | None = None

        try:
            rest = await self._async_fetch_rest_data()
        except Exception as err:  # noqa: BLE001
            rest_error = err
            _LOGGER.warning("REST update failed: %r", err)

        try:
            modbus = await self._async_fetch_modbus_data()
        except Exception as err:  # noqa: BLE001
            modbus_error = err
            _LOGGER.warning("Modbus update failed: %r", err)

        if rest_error and modbus_error:
            _LOGGER.warning(
                "FEMS update failed completely: REST=%s; Modbus=%s",
                rest_error,
                modbus_error,
            )
            raise UpdateFailed(
                f"REST and Modbus update failed: REST={rest_error}; Modbus={modbus_error}"
            ) from modbus_error

        if rest_error:
            _LOGGER.warning("Using partial data: REST unavailable, Modbus available")

        if modbus_error:
            _LOGGER.warning("Using partial data: Modbus unavailable, REST available")

        return FemsData(rest=rest, modbus=modbus)
