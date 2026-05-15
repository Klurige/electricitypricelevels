"""Tests for config and options flow behavior."""

from unittest.mock import MagicMock

import pytest

from custom_components.electricitypricelevels.config_flow import (
    ElectricityPriceLevelFlowHandler,
    ElectricityPriceLevelOptionFlowHandler,
    _parse_unit_of_measurement,
    _validate_nordpool_prices_sensor,
)
from custom_components.electricitypricelevels.const import (
    CONF_EXCLUDE_FROM_RECORDING,
    CONF_HIGH_THRESHOLD,
    CONF_LOW_THRESHOLD,
    CONF_NORDPOOL_PRICES_SENSOR,
)


# --- Tests for _parse_unit_of_measurement ---

@pytest.mark.parametrize(
    "unit_str, expected",
    [
        ("SEK/kWh", ("SEK", "kWh")),
        ("EUR/MWh", ("EUR", "MWh")),
        ("SEK/kW", ("SEK", "kW")),
        ("EUR", ("EUR", None)),
        ("kWh", (None, "kWh")),
        ("MWh", (None, "MWh")),
        ("", (None, None)),
        (None, (None, None)),
        ("  SEK / kWh  ", ("SEK", "kWh")),
        ("/", (None, None)),
        ("a/b/c", (None, None)),
        ("NOK/Wh", ("NOK", "Wh")),
    ],
    ids=[
        "currency_slash_energy",
        "eur_slash_mwh",
        "currency_slash_kw",
        "currency_only",
        "energy_only_kwh",
        "energy_only_mwh",
        "empty_string",
        "none_input",
        "whitespace_around_parts",
        "slash_only",
        "triple_slash",
        "nok_slash_wh",
    ],
)
def test_parse_unit_of_measurement(unit_str, expected):
    """Test _parse_unit_of_measurement parses various formats correctly."""
    assert _parse_unit_of_measurement(unit_str) == expected


# --- Tests for _validate_nordpool_prices_sensor ---

@pytest.mark.asyncio
async def test_validate_nordpool_prices_sensor_valid():
    """Test validation succeeds for a valid sensor."""
    hass = MagicMock()
    state = MagicMock()
    state.state = "1.23"
    state.attributes = {
        "unit_of_measurement": "SEK/kWh",
        "currency": "SEK",
    }
    hass.states.get.return_value = state

    is_valid, attrs = await _validate_nordpool_prices_sensor(hass, "sensor.nordpool")

    assert is_valid is True
    assert attrs["currency"] == "SEK"
    assert attrs["energy_unit"] == "kWh"


@pytest.mark.asyncio
async def test_validate_nordpool_prices_sensor_empty_entity_id():
    """Test validation fails for empty entity id."""
    hass = MagicMock()
    is_valid, attrs = await _validate_nordpool_prices_sensor(hass, "")
    assert is_valid is False
    assert attrs is None


@pytest.mark.asyncio
async def test_validate_nordpool_prices_sensor_not_found():
    """Test validation fails when sensor entity does not exist."""
    hass = MagicMock()
    hass.states.get.return_value = None

    is_valid, attrs = await _validate_nordpool_prices_sensor(hass, "sensor.nonexistent")

    assert is_valid is False
    assert attrs is None


@pytest.mark.asyncio
async def test_validate_nordpool_prices_sensor_unavailable():
    """Test validation fails when sensor is unavailable."""
    hass = MagicMock()
    state = MagicMock()
    state.state = "unavailable"
    hass.states.get.return_value = state

    is_valid, attrs = await _validate_nordpool_prices_sensor(hass, "sensor.nordpool")

    assert is_valid is False
    assert attrs is None


@pytest.mark.asyncio
async def test_validate_nordpool_prices_sensor_defaults():
    """Test validation returns defaults when sensor has no unit attributes."""
    hass = MagicMock()
    state = MagicMock()
    state.state = "42.0"
    state.attributes = {}
    hass.states.get.return_value = state

    is_valid, attrs = await _validate_nordpool_prices_sensor(hass, "sensor.nordpool")

    assert is_valid is True
    assert attrs["currency"] == "EUR"
    assert attrs["energy_unit"] == "MWh"


# --- Original tests ---

@pytest.mark.asyncio
async def test_options_flow_default_exclude_from_recording_true() -> None:
    """Test options flow defaults exclude_from_recording to true."""
    config_entry = MagicMock()
    config_entry.options = {CONF_NORDPOOL_PRICES_SENSOR: "sensor.nordpool_prices"}

    handler = ElectricityPriceLevelOptionFlowHandler()
    handler._config_entry = config_entry
    hass = MagicMock()
    hass.states.get.return_value = None
    handler.hass = hass

    result = await handler.async_step_init()
    schema = result["data_schema"].schema
    exclude_key = next(
        key for key in schema if getattr(key, "schema", None) == CONF_EXCLUDE_FROM_RECORDING
    )

    assert exclude_key.default() is True


@pytest.mark.asyncio
async def test_options_flow_threshold_validation_error() -> None:
    """Test options flow returns validation error when low >= high."""
    config_entry = MagicMock()
    config_entry.options = {CONF_NORDPOOL_PRICES_SENSOR: "sensor.nordpool_prices"}

    handler = ElectricityPriceLevelOptionFlowHandler()
    handler._config_entry = config_entry
    state = MagicMock()
    state.state = "1.23"
    state.attributes = {
        "unit_of_measurement": "EUR/kWh",
        "currency": "EUR",
    }
    hass = MagicMock()
    hass.states.get.return_value = state
    handler.hass = hass

    result = await handler.async_step_init(
        {
            CONF_NORDPOOL_PRICES_SENSOR: "sensor.nordpool_prices",
            CONF_LOW_THRESHOLD: 2.0,
            CONF_HIGH_THRESHOLD: 1.0,
            CONF_EXCLUDE_FROM_RECORDING: True,
        }
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "low_threshold_higher_than_high_threshold"


@pytest.mark.asyncio
async def test_main_flow_entry_options_include_exclude_from_recording_true() -> None:
    """Test initial entry options include exclude_from_recording true."""
    handler = ElectricityPriceLevelFlowHandler()
    handler.hass = MagicMock()
    handler.data = {
        CONF_NORDPOOL_PRICES_SENSOR: "sensor.nordpool_prices",
    }

    result = await handler.async_step_thresholds(
        {
            CONF_LOW_THRESHOLD: 0.10,
            CONF_HIGH_THRESHOLD: 0.20,
        }
    )

    assert result["type"] == "create_entry"
    assert result["options"][CONF_EXCLUDE_FROM_RECORDING] is True


