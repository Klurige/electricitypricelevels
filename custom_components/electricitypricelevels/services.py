"""Services for Nord Pool integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)

from .const import DOMAIN
from .sensor.compactlevels import calculate_levels
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTR_LEVEL_LENGTH = "level_length"
SERVICE_GET_LEVELS = "get_levels"
SERVICE_GET_LEVELS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_LEVEL_LENGTH, default=0): vol.All(
            cv.positive_int, vol.All(vol.Coerce(int))
        )
    }
)

@callback
def async_setup_services(hass: HomeAssistant) -> None:

    def get_service_params(
        call: ServiceCall,
    ) -> tuple[int]:
        level_length = call.data.get(ATTR_LEVEL_LENGTH, 0)
        return level_length


    async def get_levels(call: ServiceCall) -> ServiceResponse:
        _LOGGER.debug("Received service call to get levels")
        requested_length = get_service_params(call)
        _LOGGER.debug(f"Requested level length: {requested_length} minutes")
        result = calculate_levels(hass, requested_length)
        return result

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_LEVELS,
        get_levels,
        schema=SERVICE_GET_LEVELS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
