"""Services for Nord Pool integration."""

from __future__ import annotations

import logging
import math

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)

from .const import DOMAIN
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
        levels_str = ""
        level_length = 0
        low_threshold = None
        high_threshold = None
        try:
            for state in hass.states.async_all():
                if state.domain == "sensor" and "rates" in state.attributes:
                    rates = state.attributes.get("rates", [])
                    low_threshold = state.attributes.get("low_threshold", None)
                    high_threshold = state.attributes.get("high_threshold", None)
                    if rates and low_threshold is not None and high_threshold is not None:
                        if requested_length == 0:
                            rate_start = rates[0].get("start", "")
                            rate_end = rates[0].get("end", "")
                            level_length = math.ceil((rate_end - rate_start).total_seconds() / 60)
                        else:
                            level_length = requested_length
                        levels = []
                        for rate in rates:
                            rate_start = rate.get("start", "")
                            rate_end = rate.get("end", "")
                            rate_cost = rate.get("cost", 0)
                            if rate_start and rate_end:
                                rate_length = math.ceil((rate_end - rate_start).total_seconds() / 60)
                                for i in range(0, rate_length):
                                    levels.append(rate_cost)
                        _LOGGER.debug(f"Levels found: {len(levels)}")
                        # Split levels into chunks of length level_length
                        levels_str = ""
                        if level_length > 0:
                            for i in range(0, len(levels), level_length):
                                chunk = levels[i:i+level_length]
                                if all(val <= low_threshold for val in chunk):
                                    levels_str += "L"
                                elif all(val < high_threshold for val in chunk):
                                    levels_str += "M"
                                else:
                                    levels_str += "H"
                    break
        except Exception as e:
            _LOGGER.error(f"Error processing rates: {e}")
            levels_str = ""
            level_length = 0
            low_threshold = None
            high_threshold = None

        if levels_str:
            two_days = int(2 * 24 * 60 / level_length)
            if len(levels_str) < two_days:
                levels_str += "U" * (two_days - len(levels_str))

        _LOGGER.debug(f"Low threshold: {low_threshold}, High threshold: {high_threshold}")
        _LOGGER.debug(f"Level length: {level_length}, Levels: {len(levels_str)}, Levels string: {levels_str}")

        result: dict[str, str] = { "level_length": level_length, "levels": levels_str, "low_threshold": low_threshold, "high_threshold": high_threshold }
        return result

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_LEVELS,
        get_levels,
        schema=SERVICE_GET_LEVELS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
