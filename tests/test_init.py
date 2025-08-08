"""Test component setup."""
from homeassistant.setup import async_setup_component

from custom_components.electricitypricelevels.const import DOMAIN


async def test_async_setup(hass):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


import pytest


@pytest.fixture(autouse=True)
def mock_pynordpool():
    import sys
    import types

    sys.modules["pynordpool"] = types.ModuleType("pynordpool")
    # Patch Currency to be an iterable of objects with a 'value' attribute
    class MockCurrency:
        def __init__(self, value):
            self.value = value

    sys.modules["pynordpool"].Currency = [MockCurrency("SEK"), MockCurrency("NOK"), MockCurrency("DKK"), MockCurrency("EUR")]
    sys.modules["pynordpool"].Area = object
    sys.modules["pynordpool"].HourPrice = object
    sys.modules["pynordpool"].DeliveryPeriodData = object
    sys.modules["pynordpool"].DeliveryPeriodEntry = object
    sys.modules["pynordpool"].DeliveryPeriodsData = object
    sys.modules["pynordpool"].NordPoolClient = object
    sys.modules["pynordpool"].NordPoolEmptyResponseError = type("NordPoolEmptyResponseError", (Exception,), {})
    sys.modules["pynordpool"].NordPoolError = type("NordPoolError", (Exception,), {})
    sys.modules["pynordpool"].NordPoolResponseError = type("NordPoolResponseError", (Exception,), {})
    sys.modules["pynordpool"].NordPoolAuthenticationError = type("NordPoolAuthenticationError", (Exception,), {})
    sys.modules["pynordpool"].AREAS = {}
    yield
    import sys
    sys.modules.pop("pynordpool", None)
