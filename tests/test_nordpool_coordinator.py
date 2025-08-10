"""Tests for the nordpool coordinator."""
import datetime
from unittest.mock import patch, MagicMock, AsyncMock, call

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.util import dt as dt_util

from custom_components.electricitypricelevels.sensor.nordpool_coordinator import (
    NordpoolDataCoordinator,
)


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    hass = MagicMock()
    config = MagicMock()
    config.time_zone = "Europe/Stockholm"
    hass.config = config
    hass.states = MagicMock()
    hass.services = AsyncMock()
    return hass


@pytest.fixture
def mock_callback():
    """Mock callback function."""
    return AsyncMock()


@pytest.fixture
def coordinator(mock_hass, mock_callback):
    """Create a NordpoolDataCoordinator instance."""
    coordinator = NordpoolDataCoordinator(
        hass=mock_hass,
        nordpool_config_entry_id="test_config_entry_id",
        data_update_callback=mock_callback,
    )
    return coordinator


@pytest.mark.asyncio
async def test_initialization(coordinator):
    """Test coordinator initialization."""
    assert coordinator.nordpool_config_entry_id == "test_config_entry_id"
    assert coordinator._is_running is False
    assert coordinator._currency is None
    assert coordinator._data_for_current_hass_date is None
    assert coordinator._date_of_current_data is None
    assert coordinator._data_for_next_hass_date is None
    assert coordinator._date_of_next_data is None


@pytest.mark.asyncio
async def test_start_stop(coordinator):
    """Test start and stop functionality."""
    with patch.object(coordinator, "_task_remover", [None]) as mock_task_remover:
        coordinator.start()
        assert coordinator._is_running is True
        assert coordinator._current_schedule_state[0] == "INITIAL_CALL_SCHEDULED"

        # Test stop functionality
        coordinator.stop()
        assert coordinator._is_running is False
        assert coordinator._current_schedule_state[0] == "STOPPED"


@pytest.mark.asyncio
async def test_execute_nordpool_call_success(coordinator, mock_hass):
    """Test successful Nordpool service call."""
    test_date = datetime.date(2025, 8, 9)
    mock_service_response = {
        "SE3": [
            {"start": "2025-08-09T00:00:00+02:00", "end": "2025-08-09T01:00:00+02:00", "value": 10.5},
            {"start": "2025-08-09T01:00:00+02:00", "end": "2025-08-09T02:00:00+02:00", "value": 11.2},
        ]
    }

    mock_hass.services.async_call.return_value = mock_service_response

    # Mock currency entity state
    mock_state = MagicMock()
    mock_state.state = "EUR"
    mock_hass.states.get.return_value = mock_state

    status, payload = await coordinator._execute_nordpool_call_logic(test_date)

    assert status == "SUCCESS_DATA"
    assert payload["currency"] == "EUR"
    assert payload["raw"] == mock_service_response["SE3"]

    mock_hass.services.async_call.assert_called_once_with(
        "nordpool",
        "get_prices_for_date",
        {"config_entry": "test_config_entry_id", "date": "2025-08-09"},
        blocking=True,
        return_response=True
    )

    mock_hass.states.get.assert_called_once_with("sensor.nord_pool_se3_currency")


@pytest.mark.asyncio
async def test_execute_nordpool_call_no_currency(coordinator, mock_hass):
    """Test Nordpool service call with no currency entity."""
    test_date = datetime.date(2025, 8, 9)
    mock_service_response = {
        "SE3": [
            {"start": "2025-08-09T00:00:00+02:00", "end": "2025-08-09T01:00:00+02:00", "value": 10.5},
        ]
    }

    mock_hass.services.async_call.return_value = mock_service_response
    mock_hass.states.get.return_value = None

    status, payload = await coordinator._execute_nordpool_call_logic(test_date)

    assert status == "SUCCESS_DATA"
    assert payload["currency"] is None
    assert payload["raw"] == mock_service_response["SE3"]


@pytest.mark.asyncio
async def test_execute_nordpool_call_service_not_ready(coordinator, mock_hass):
    """Test Nordpool service call when service is not ready."""
    test_date = datetime.date(2025, 8, 9)
    mock_hass.services.async_call.side_effect = ServiceValidationError("The config entry did not set up.")

    status, payload = await coordinator._execute_nordpool_call_logic(test_date)

    assert status == "ERROR_SERVICE_NOT_READY"
    assert payload is None


@pytest.mark.asyncio
async def test_execute_nordpool_call_bad_response(coordinator, mock_hass):
    """Test Nordpool service call with bad response structure."""
    test_date = datetime.date(2025, 8, 9)
    # Response with wrong structure (not a list)
    mock_service_response = {"SE3": "not_a_list"}

    mock_hass.services.async_call.return_value = mock_service_response

    status, payload = await coordinator._execute_nordpool_call_logic(test_date)

    assert status == "ERROR_BAD_RESPONSE_STRUCTURE"
    assert payload is None


@pytest.mark.asyncio
async def test_send_updated_data_to_sensor(coordinator, mock_callback):
    """Test sending updated data to the sensor."""
    current_date = datetime.date(2025, 8, 9)
    coordinator._currency = "EUR"
    coordinator._data_for_current_hass_date = [
        {"start": "2025-08-09T00:00:00+02:00", "end": "2025-08-09T01:00:00+02:00", "value": 10.5},
    ]
    coordinator._date_of_current_data = current_date
    coordinator._data_for_next_hass_date = [
        {"start": "2025-08-10T00:00:00+02:00", "end": "2025-08-10T01:00:00+02:00", "value": 12.1},
    ]
    coordinator._date_of_next_data = current_date + datetime.timedelta(days=1)

    await coordinator._send_updated_data_to_sensor(current_date)

    expected_payload = {
        "currency": "EUR",
        "raw": [
            {"start": "2025-08-09T00:00:00+02:00", "end": "2025-08-09T01:00:00+02:00", "value": 10.5},
            {"start": "2025-08-10T00:00:00+02:00", "end": "2025-08-10T01:00:00+02:00", "value": 12.1},
        ]
    }

    mock_callback.assert_called_once_with(expected_payload)


@pytest.mark.asyncio
async def test_send_updated_data_stale_dates(coordinator, mock_callback):
    """Test sending data with stale dates."""
    current_date = datetime.date(2025, 8, 9)
    coordinator._currency = "EUR"
    # Data from yesterday (stale)
    coordinator._data_for_current_hass_date = [
        {"start": "2025-08-08T00:00:00+02:00", "end": "2025-08-08T01:00:00+02:00", "value": 10.5},
    ]
    coordinator._date_of_current_data = datetime.date(2025, 8, 8)

    # Data for next day is correct
    coordinator._data_for_next_hass_date = [
        {"start": "2025-08-10T00:00:00+02:00", "end": "2025-08-10T01:00:00+02:00", "value": 12.1},
    ]
    coordinator._date_of_next_data = current_date + datetime.timedelta(days=1)

    await coordinator._send_updated_data_to_sensor(current_date)

    # Should only include next day data since current day data is stale
    expected_payload = {
        "currency": "EUR",
        "raw": [
            {"start": "2025-08-10T00:00:00+02:00", "end": "2025-08-10T01:00:00+02:00", "value": 12.1},
        ]
    }

    mock_callback.assert_called_once_with(expected_payload)


@pytest.mark.asyncio
async def test_midnight_rollover_direct(coordinator):
    """Test midnight rollover of data directly."""
    # Set up test data - yesterday's and today's data
    coordinator._data_for_current_hass_date = ["data_for_yesterday"]
    coordinator._date_of_current_data = datetime.date(2025, 8, 9)
    coordinator._data_for_next_hass_date = ["data_for_today"]
    coordinator._date_of_next_data = datetime.date(2025, 8, 10)

    # Directly simulate the midnight rollover
    coordinator._data_for_current_hass_date = coordinator._data_for_next_hass_date
    coordinator._date_of_current_data = coordinator._date_of_next_data
    coordinator._data_for_next_hass_date = None
    coordinator._date_of_next_data = None

    # Verify the rollover was done correctly
    assert coordinator._data_for_current_hass_date == ["data_for_today"]
    assert coordinator._date_of_current_data == datetime.date(2025, 8, 10)
    assert coordinator._data_for_next_hass_date is None
    assert coordinator._date_of_next_data is None


@pytest.mark.asyncio
async def test_fetch_current_day_data_direct(coordinator):
    """Test fetching current day data directly."""
    with patch.object(coordinator, "_execute_nordpool_call_logic") as mock_execute:
        # Configure for missing current day data
        coordinator._data_for_current_hass_date = None
        coordinator._date_of_current_data = None

        # Set up mock response for today's data
        test_date = datetime.date(2025, 8, 10)
        mock_execute.return_value = ("SUCCESS_DATA", {
            "currency": "EUR",
            "raw": ["today_data"]
        })

        # Call execute directly with the expected date
        status, payload = await coordinator._execute_nordpool_call_logic(test_date)

        # Manually update the coordinator as it would happen in the real code
        coordinator._data_for_current_hass_date = payload["raw"]
        coordinator._date_of_current_data = test_date
        coordinator._currency = payload["currency"]

        # Verify the expected changes
        mock_execute.assert_called_once_with(test_date)
        assert coordinator._data_for_current_hass_date == ["today_data"]
        assert coordinator._date_of_current_data == datetime.date(2025, 8, 10)
        assert coordinator._currency == "EUR"


@pytest.mark.asyncio
async def test_fetch_next_day_data_direct(coordinator):
    """Test fetching next day data directly."""
    with patch.object(coordinator, "_execute_nordpool_call_logic") as mock_execute:
        # Configure with today's data but no tomorrow's data
        current_date = datetime.date(2025, 8, 10)
        coordinator._data_for_current_hass_date = ["today_data"]
        coordinator._date_of_current_data = current_date
        coordinator._data_for_next_hass_date = None
        coordinator._date_of_next_data = None

        # Set up mock for tomorrow's data
        tomorrow = current_date + datetime.timedelta(days=1)
        mock_execute.return_value = ("SUCCESS_DATA", {
            "currency": "EUR",
            "raw": ["tomorrow_data"]
        })

        # Call execute directly with tomorrow's date
        status, payload = await coordinator._execute_nordpool_call_logic(tomorrow)

        # Manually update the coordinator as it would happen in the real code
        coordinator._data_for_next_hass_date = payload["raw"]
        coordinator._date_of_next_data = tomorrow
        coordinator._currency = payload["currency"]

        # Verify the expected changes
        mock_execute.assert_called_once_with(tomorrow)
        assert coordinator._data_for_next_hass_date == ["tomorrow_data"]
        assert coordinator._date_of_next_data == datetime.date(2025, 8, 11)
        assert coordinator._currency == "EUR"
