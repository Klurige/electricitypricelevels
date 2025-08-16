import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from custom_components.electricitypricelevels.sensor.compactlevels import CompactLevelsDataSensor, calculate_levels
import asyncio
import threading
from datetime import datetime

# Minimal mocks for State and Event to avoid Home Assistant dependency
class State:
    def __init__(self, entity_id, state, attributes=None):
        self.entity_id = entity_id
        self.state = state
        self.attributes = attributes or {}

class Event:
    def __init__(self, event_type, data=None):
        self.event_type = event_type
        self.data = data or {}

@pytest.fixture
def hass():
    hass = MagicMock()
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    hass.config = MagicMock()
    hass.config.time_zone = "UTC"
    hass.loop = asyncio.get_event_loop()
    hass.data = {"custom_components": {}}
    hass.loop_thread_id = threading.get_ident()
    return hass

@pytest.fixture
def entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    return entry

@pytest.fixture
def device_info():
    return MagicMock()

@pytest.fixture
def sensor(hass, entry, device_info):
    s = CompactLevelsDataSensor(hass, entry, device_info)
    s.hass = hass
    s.entity_id = "sensor.levels"
    return s

@patch("custom_components.electricitypricelevels.sensor.levels_array.async_track_state_change_event")
@patch("custom_components.electricitypricelevels.sensor.levels_array.LevelsSensor._start_levels_sensor", new_callable=AsyncMock)
async def test_async_added_to_hass_calls_start_on_available(mock_start, mock_track, sensor, hass):
    hass.states.get.return_value = State("sensor.electricitypricelevels", "normal")
    await sensor.async_added_to_hass()
    mock_start.assert_awaited_once()
    mock_track.assert_called_once()

@patch("custom_components.electricitypricelevels.sensor.levels_array.async_track_state_change_event")
@patch("custom_components.electricitypricelevels.sensor.levels_array.LevelsSensor._start_levels_sensor", new_callable=AsyncMock)
async def test_async_added_to_hass_does_not_call_start_on_unavailable(mock_start, mock_track, sensor, hass):
    hass.states.get.return_value = State("sensor.electricitypricelevels", "unavailable")
    await sensor.async_added_to_hass()
    mock_start.assert_not_awaited()
    mock_track.assert_called_once()

@pytest.mark.asyncio
async def test_handle_electricity_price_level_update_triggers_start(sensor):
    sensor._waiting_for_first_value = True
    event = Event("state_changed", data={"new_state": State("sensor.electricitypricelevels", "normal")})
    with patch.object(sensor, "_start_levels_sensor", new_callable=AsyncMock) as mock_start:
        await sensor._handle_electricity_price_level_update(event)
        mock_start.assert_awaited_once()

@pytest.mark.asyncio
async def test_handle_electricity_price_level_update_does_not_trigger_on_unavailable(sensor):
    sensor._waiting_for_first_value = True
    event = Event("state_changed", data={"new_state": State("sensor.electricitypricelevels", "unavailable")})
    with patch.object(sensor, "_start_levels_sensor", new_callable=AsyncMock) as mock_start:
        await sensor._handle_electricity_price_level_update(event)
        mock_start.assert_not_awaited()

@pytest.mark.asyncio
async def test_start_levels_sensor_idempotent(sensor):
    sensor._waiting_for_first_value = False
    await sensor._start_levels_sensor()
    assert sensor._waiting_for_first_value is False

@patch("custom_components.electricitypricelevels.sensor.levels_array.calculate_levels")
def test_fetch_service_value_normal(mock_calc, sensor, hass):
    mock_calc.return_value = {"level_length": 60, "levels": "ABCDEFGHIJKL" * 5}
    value, _ = sensor._fetch_service_value()
    assert isinstance(value["level_index"], int)
    assert isinstance(value["levels"], list)
    assert len(value["levels"]) == 60
    assert all(isinstance(l, str) for l in value["levels"])

@patch("custom_components.electricitypricelevels.sensor.levels_array.calculate_levels")
def test_fetch_service_value_edge_cases(mock_calc, sensor, hass):
    mock_calc.return_value = {"level_length": 0, "levels": ""}
    value, _ = sensor._fetch_service_value()
    assert value["level_index"] == -1
    assert value["levels"] == ["U"] * 60

@patch("custom_components.electricitypricelevels.sensor.levels_array.calculate_levels")
def test_fetch_service_value_all_unknown(mock_calc, sensor, hass):
    mock_calc.return_value = {"level_length": 0, "levels": "U"}
    value, next_update = sensor._fetch_service_value()
    assert next_update == 5
    assert value["levels"] == ["U"] * 60
    assert value["level_index"] == -1

@pytest.mark.asyncio
async def test_async_will_remove_from_hass(sensor):
    sensor._task = MagicMock()
    await sensor.async_will_remove_from_hass()
    sensor._task.cancel.assert_called_once()

@patch("custom_components.electricitypricelevels.sensor.levels_array.LevelsSensor._fetch_service_value")
@pytest.mark.asyncio
async def test_periodic_update(mock_fetch, sensor):
    mock_fetch.return_value = ("A", 0.01)
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        async def stop_after_one(*args, **kwargs):
            raise asyncio.CancelledError()
        mock_sleep.side_effect = stop_after_one
        with pytest.raises(asyncio.CancelledError):
            await sensor._periodic_update()
        mock_fetch.assert_called()
        mock_sleep.assert_called()


@patch("custom_components.electricitypricelevels.sensor.levels_array.calculate_levels")
@patch("custom_components.electricitypricelevels.sensor.levels_array.dt_util.get_time_zone")
@patch("custom_components.electricitypricelevels.sensor.levels_array.datetime")
def test_fetch_service_value_next_update_seconds(mock_dt, mock_tz, mock_calc, sensor, hass):
    # Mock the time zone to be something simple
    mock_tz.return_value = "UTC"

    # Mock the time to be 10:15:30
    mock_now = datetime(2023, 1, 1, 10, 15, 30)
    mock_dt.now.return_value = mock_now

    # Levels are 60 minutes long
    mock_calc.return_value = {"level_length": 60, "levels": ["A"] * 24}

    _, next_update = sensor._fetch_service_value()

    # At 10:15:30, the current 60-min level started at 10:00:00.
    # It ends at 11:00:00.
    # Seconds since midnight = 10 * 3600 + 15 * 60 + 30 = 36930
    # Period in seconds = 60 * 60 = 3600
    # Seconds into current period = 36930 % 3600 = 930
    # Expected sleep = 3600 - 930 = 2670
    assert next_update == 2670

    # Test with a different time
    # Mock the time to be 10:59:50
    mock_now = datetime(2023, 1, 1, 10, 59, 50)
    mock_dt.now.return_value = mock_now

    _, next_update = sensor._fetch_service_value()
    # At 10:59:50, next update is in 10 seconds
    assert next_update == 10

    # Test with a different period
    # Levels are 30 minutes long
    mock_calc.return_value = {"level_length": 30, "levels": ["A"] * 48}

    # Mock the time to be 10:15:30
    mock_now = datetime(2023, 1, 1, 10, 15, 30)
    mock_dt.now.return_value = mock_now
    _, next_update = sensor._fetch_service_value()
    # Period in seconds = 30 * 60 = 1800
    # Seconds since midnight = 36930
    # Seconds into current period = 36930 % 1800 = 930
    # Expected sleep = 1800 - 930 = 870
    assert next_update == 870

def test_calculate_levels_fill_unknown_false(hass):
    # Simulate a state with 2 rates, 30 min each, thresholds 1/2
    class FakeState:
        domain = "sensor"
        def __init__(self):
            self.attributes = {
                "rates": [
                    {"start": datetime(2023,1,1,0,0), "end": datetime(2023,1,1,0,30), "cost": 1},
                    {"start": datetime(2023,1,1,0,30), "end": datetime(2023,1,1,1,0), "cost": 3},
                ],
                "low_threshold": 1.5,
                "high_threshold": 2.5,
            }
    hass.states.async_all.return_value = [FakeState()]
    # Should not fill with 'U' if fill_unknown is False
    result = calculate_levels(hass, 30, fill_unknown=False)
    assert result["levels"] == "LH"


def test_calculate_levels_fill_unknown_true(hass):
    # Simulate a state with 2 rates, 30 min each, thresholds 1/2
    class FakeState:
        domain = "sensor"
        def __init__(self):
            self.attributes = {
                "rates": [
                    {"start": datetime(2023,1,1,0,0), "end": datetime(2023,1,1,0,30), "cost": 1},
                    {"start": datetime(2023,1,1,0,30), "end": datetime(2023,1,1,1,0), "cost": 3},
                ],
                "low_threshold": 1.5,
                "high_threshold": 2.5,
            }
    hass.states.async_all.return_value = [FakeState()]
    # Should fill with 'U' up to 96 chars (2 days, 30 min slots)
    result = calculate_levels(hass, 30, fill_unknown=True)
    assert result["levels"].startswith("LH")
    assert len(result["levels"]) == 96
    assert set(result["levels"][2:]) == {"U"}
