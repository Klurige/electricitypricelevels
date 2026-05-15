"""Test component setup."""

import sys
import types
from unittest.mock import patch

import pytest

from homeassistant.setup import async_setup_component

from custom_components.electricitypricelevels.const import DOMAIN

from pytest_homeassistant_custom_component.common import MockConfigEntry


class MockCurrency:
    """Mock for pynordpool Currency enum member."""

    def __init__(self, value):
        self.value = value


@pytest.fixture(autouse=True)
def mock_pynordpool():
    """Provide a function-scoped mock of the pynordpool package."""
    mod = types.ModuleType("pynordpool")
    mod.Currency = [
        MockCurrency("SEK"),
        MockCurrency("NOK"),
        MockCurrency("DKK"),
        MockCurrency("EUR"),
    ]
    mod.Area = object
    mod.HourPrice = object
    mod.DeliveryPeriodData = object
    mod.DeliveryPeriodEntry = object
    mod.DeliveryPeriodsData = object
    mod.NordPoolClient = object
    mod.NordPoolEmptyResponseError = type("NordPoolEmptyResponseError", (Exception,), {})
    mod.NordPoolError = type("NordPoolError", (Exception,), {})
    mod.NordPoolResponseError = type("NordPoolResponseError", (Exception,), {})
    mod.NordPoolAuthenticationError = type("NordPoolAuthenticationError", (Exception,), {})
    mod.AREAS = {}
    sys.modules["pynordpool"] = mod
    yield
    sys.modules.pop("pynordpool", None)


async def test_async_setup(hass):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


async def test_async_unload_entry(hass):
    """Test that unloading a config entry forwards to platform unload."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    # Set up first so there's something to unload
    assert await async_setup_component(hass, DOMAIN, {}) is True

    result = await hass.config_entries.async_unload(entry.entry_id)
    assert result is True


async def test_async_update_options_triggers_reload(hass):
    """Test that updating options triggers a config entry reload."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {}) is True

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        hass.config_entries.async_update_entry(entry, options={"new_key": "new_val"})
        await hass.async_block_till_done()
        mock_reload.assert_called_once_with(entry.entry_id)


async def test_migrate_v1_to_v2_renames_area_id(hass):
    """Test migration renames nordpool_area_id to nordpool_prices_sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={"nordpool_area_id": "se3"},
        options={
            "nordpool_area_id": "se3",
            "price_divisor": 100,
            "low_threshold": 0.1,
        },
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {}) is True

    assert entry.version == 2
    assert "nordpool_area_id" not in entry.options
    assert "nordpool_area_id" not in entry.data
    assert entry.options["nordpool_prices_sensor"] == "sensor.nord_pool_se3_current_price"
    assert entry.data["nordpool_prices_sensor"] == "sensor.nord_pool_se3_current_price"
    assert entry.options["price_divisor"] == 1


async def test_migrate_v1_to_v2_preserves_existing_new_key(hass):
    """Test migration preserves nordpool_prices_sensor if already present."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={"nordpool_prices_sensor": "sensor.my_custom_sensor"},
        options={
            "nordpool_prices_sensor": "sensor.my_custom_sensor",
            "price_divisor": 100,
        },
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {}) is True

    assert entry.version == 2
    assert entry.options["nordpool_prices_sensor"] == "sensor.my_custom_sensor"
    assert entry.options["price_divisor"] == 1


async def test_migrate_v2_entry_not_modified(hass):
    """Test that v2 entries are not modified by migration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={"nordpool_prices_sensor": "sensor.test"},
        options={
            "nordpool_prices_sensor": "sensor.test",
            "price_divisor": 1,
        },
    )
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {}) is True

    assert entry.version == 2
    assert entry.options["nordpool_prices_sensor"] == "sensor.test"
    assert entry.options["price_divisor"] == 1
