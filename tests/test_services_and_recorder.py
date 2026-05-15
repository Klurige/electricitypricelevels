"""Tests for service registration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.electricitypricelevels.services import async_setup_services


@pytest.mark.asyncio
async def test_get_levels_service_handler_uses_requested_level_length() -> None:
    """Test service handler forwards level_length to calculate_levels."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service.return_value = False

    expected = {"level_length": 60, "levels": "LMH"}
    with patch(
        "custom_components.electricitypricelevels.services.calculate_levels",
        return_value=expected,
    ) as mock_calculate:
        async_setup_services(hass)
        handler = hass.services.async_register.call_args.args[2]

        call = MagicMock()
        call.data = {"level_length": 60}
        response = await handler(call)

    assert response == expected
    mock_calculate.assert_called_once_with(hass, 60)


@pytest.mark.asyncio
async def test_get_levels_service_handler_defaults_level_length_to_zero() -> None:
    """Test service handler defaults level_length to 0 when omitted."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.has_service.return_value = False

    expected = {"level_length": 0, "levels": "U"}
    with patch(
        "custom_components.electricitypricelevels.services.calculate_levels",
        return_value=expected,
    ) as mock_calculate:
        async_setup_services(hass)
        handler = hass.services.async_register.call_args.args[2]

        call = MagicMock()
        call.data = {}
        response = await handler(call)

    assert response == expected
    mock_calculate.assert_called_once_with(hass, 0)

