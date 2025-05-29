"""Support for the ElectricityPriceLevel time sensor service."""

from __future__ import annotations

import asyncio
import datetime
import logging

# Remove pytz import if it's no longer used elsewhere
# import pytz
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util # Import dt_util

from ..util import generate_level_pattern

_LOGGER = logging.getLogger(__name__)


class TimeSensor(SensorEntity):
    """Representation of a Sensor."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, hass, entry: ConfigEntry, device_info, level_sensor) -> None:
        description = SensorEntityDescription(
        key="iso_formatted_time",
        translation_key="iso_formatted_time",
    )
        self.entity_description = description
        self.entity_id = f"{SENSOR_DOMAIN}.{description.key}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self._state = None
        self._hass = hass
        self._attr_device_info = device_info
        self._level_sensor = level_sensor

        self._level_clock_pattern = ""

        _LOGGER.debug("TimeSensor initialized")
        # Schedule the first update
        async_track_time_change(hass, self._update_time, second=0)
        # Send the initial value as soon as possible
        hass.loop.create_task(self._send_initial_value())

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            "level_clock_pattern": self._level_clock_pattern
        }


    async def _send_initial_value(self):
        """Send the initial value with current time, seconds and ms set to 0."""
        local_tz = dt_util.get_time_zone(self._hass.config.time_zone)  # Get the time zone from Home Assistant
        now = datetime.datetime.now(local_tz)
        await self._update_time(now)

    async def _update_time(self, now):
        """Update the sensor state with the current time."""
        rates = None
        async def wait_for_rates():
            nonlocal rates
            while not (rates := self._level_sensor.extra_state_attributes.get("rates")):
                await asyncio.sleep(0.1)  # Check every 100ms
        try:
            await asyncio.wait_for(wait_for_rates(), timeout=10)
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout waiting for rates to be available")
        timestamp = now.replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S%z")
        self._state = timestamp
        await self._generate_level_clock_pattern(timestamp, rates)


    async def _generate_level_clock_pattern(self, timestamp, rates ):
        _LOGGER.debug("Generating level clock pattern")
        _LOGGER.debug(f"Timestamp: {timestamp}")
        #_LOGGER.debug("Rates: %s", json.dumps(rates, indent=4, default=str))
        self._level_clock_pattern = generate_level_pattern(rates)
        _LOGGER.debug(f"Level clock pattern: {self._level_clock_pattern}")
        self.async_write_ha_state()