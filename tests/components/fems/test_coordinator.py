"""Tests for FEMS coordinators."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.fems.coordinator import FemsDataUpdateCoordinator
from custom_components.fems.diagnostics_coordinator import (
    FemsDiagnosticsCoordinator,
)


async def test_data_coordinator_returns_combined_mock_data(hass, mock_config_entry) -> None:
    """Test main coordinator with mocked REST and Modbus data."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.fems.coordinator.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch("custom_components.fems.coordinator.FemsRestApi"),
        patch("custom_components.fems.coordinator.FemsModbusApi"),
    ):
        coordinator = FemsDataUpdateCoordinator(hass, mock_config_entry)

    rest_payload = {
        "battery0/Soc": 78,
        "battery0/Soh": 96,
        "battery0/MinCellVoltage": 3210,
        "battery0/MaxCellVoltage": 3290,
    }
    modbus_payload = {
        "ess_soc": 78,
        "ess_active_power": 1234.0,
        "grid_active_power": -456.0,
    }

    with (
        patch.object(
            coordinator,
            "_async_fetch_rest_data",
            new=AsyncMock(return_value=rest_payload),
        ),
        patch.object(
            coordinator,
            "_async_fetch_modbus_data",
            new=AsyncMock(return_value=modbus_payload),
        ),
    ):
        data = await coordinator._async_update_data()

    assert data.rest == rest_payload
    assert data.modbus == modbus_payload


async def test_data_coordinator_allows_partial_data_when_rest_fails(
    hass,
    mock_config_entry,
) -> None:
    """Test coordinator keeps Modbus data if REST fails."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.fems.coordinator.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch("custom_components.fems.coordinator.FemsRestApi"),
        patch("custom_components.fems.coordinator.FemsModbusApi"),
    ):
        coordinator = FemsDataUpdateCoordinator(hass, mock_config_entry)

    modbus_payload = {
        "ess_soc": 80,
        "ess_active_power": 1000.0,
    }

    with (
        patch.object(
            coordinator,
            "_async_fetch_rest_data",
            new=AsyncMock(side_effect=RuntimeError("REST failed")),
        ),
        patch.object(
            coordinator,
            "_async_fetch_modbus_data",
            new=AsyncMock(return_value=modbus_payload),
        ),
    ):
        data = await coordinator._async_update_data()

    assert data.rest == {}
    assert data.modbus == modbus_payload


async def test_diagnostics_coordinator_returns_mock_data(hass, mock_config_entry) -> None:
    """Test diagnostics coordinator with mocked cell voltage data."""
    mock_config_entry.add_to_hass(hass)

    fake_rest_api = AsyncMock()
    fake_rest_api.async_fetch_group.return_value = {
        "battery0/Tower0Module0Cell000Voltage": 3281,
        "battery0/Tower0Module0Cell001Voltage": 3283,
        "battery0/Tower0Module1Cell000Voltage": 3279,
    }

    coordinator = FemsDiagnosticsCoordinator(
        hass,
        mock_config_entry,
        fake_rest_api,
    )

    data = await coordinator._async_update_data()

    assert "battery0/Tower0Module0Cell000Voltage" in data.rest
    assert data.rest["battery0/Tower0Module0Cell001Voltage"] == 3283
    fake_rest_api.async_fetch_group.assert_awaited_once()

async def test_build_rest_groups_uses_detected_chargers(
    hass,
    mock_config_entry,
) -> None:
    """Test REST groups are built for all detected chargers."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.fems.coordinator.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch("custom_components.fems.coordinator.FemsRestApi"),
        patch("custom_components.fems.coordinator.FemsModbusApi"),
    ):
        coordinator = FemsDataUpdateCoordinator(hass, mock_config_entry)

    coordinator.charger_ids = (0, 1, 2)

    groups = coordinator._build_rest_groups()

    assert "charger0/(ActualPower|Voltage|Current)" in groups
    assert "charger1/(ActualPower|Voltage|Current)" in groups
    assert "charger2/(ActualPower|Voltage|Current)" in groups
    assert len(
        [group for group in groups if group.startswith("charger")]
    ) == 3

async def test_discover_chargers_detects_only_available_components(
    hass,
    mock_config_entry,
) -> None:
    """Test charger discovery detects only available charger components."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.fems.coordinator.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch("custom_components.fems.coordinator.FemsRestApi"),
        patch("custom_components.fems.coordinator.FemsModbusApi"),
    ):
        coordinator = FemsDataUpdateCoordinator(hass, mock_config_entry)

    async def _fake_fetch_group(group: str):
        if group == "charger0/ActualPower":
            return {"charger0/ActualPower": 100}
        if group == "charger1/ActualPower":
            return {"charger1/ActualPower": 200}
        if group == "charger2/ActualPower":
            return {"charger2/ActualPower": 300}
        raise RuntimeError("charger not available")

    coordinator.rest_api.async_fetch_group = AsyncMock(side_effect=_fake_fetch_group)

    charger_ids = await coordinator._async_discover_chargers()

    assert charger_ids == (0, 1, 2)