"""Support for the ElectricityPriceLevel sensor service."""

from __future__ import annotations

import datetime
import logging

import pytz
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_change

from .electricity_price_level_sensor_entity_description import ElectricityPriceLevelSensorEntityDescription

_LOGGER = logging.getLogger(__name__)

class TimeSensor(SensorEntity):
    """Representation of a Sensor."""

    entity_description: ElectricityPriceLevelSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, hass, entry: ConfigEntry, device_info) -> None:
        description = ElectricityPriceLevelSensorEntityDescription(
        key="iso_formatted_time",
        translation_key="iso_formatted_time",
    )
        self.entity_description = description
        self.entity_id = f"{SENSOR_DOMAIN}.{description.key}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self._state = None
        self._hass = hass
        self._attr_device_info = device_info

        _LOGGER.debug("TimeSensor initialized")
        # Schedule the first update
        async_track_time_change(hass, self._update_time, second=0)
        # Send the initial value as soon as possible
        hass.loop.create_task(self._send_initial_value())

    @property
    def state(self):
        return self._state

    async def _send_initial_value(self):
        """Send the initial value with current time but minutes set to 00."""
        local_tz = pytz.timezone(self._hass.config.time_zone)  # Get the time zone from Home Assistant
        now = datetime.datetime.now(local_tz)
        initial_time = now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%S%z")
        self._state = initial_time
        self.async_write_ha_state()

    async def _update_time(self, now):
        """Update the sensor state with the current time."""
        local_tz = pytz.timezone(self._hass.config.time_zone)  # Get the time zone from Home Assistant
        local_time = datetime.datetime.now(local_tz).strftime("%Y-%m-%dT%H:%M:%S%z")
        self._state = local_time
        self.async_write_ha_state()
