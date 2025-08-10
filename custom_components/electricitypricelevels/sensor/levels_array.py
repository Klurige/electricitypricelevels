from homeassistant.core import HomeAssistant, callback, Event, State
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from datetime import datetime
from homeassistant.util import dt as dt_util
import asyncio
from custom_components.electricitypricelevels.services import calculate_levels
import logging

_LOGGER = logging.getLogger(__name__)

class LevelsSensor(SensorEntity):
    """
    Entity that exposes the latest electricity price levels as an attribute.
    Always hidden from the UI.
    """
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False  # Hidden by default
    _attr_entity_category = EntityCategory.DIAGNOSTIC  # Mark as diagnostic to discourage UI display
    _attr_should_poll = False
    _attr_visible = False  # Always hidden from UI (Home Assistant ignores this, but included for clarity)

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device_info: DeviceInfo) -> None:
        self._state_attrs = None
        self._entry = entry
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_levels"
        self._attr_name = "Levels"
        self._task = None
        self._service_value = None
        self._electricity_price_level_entity_id = f"sensor.electricitypricelevels"
        self._waiting_for_first_value = True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Wait for ElectricityPriceLevelSensor to emit its first value
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._electricity_price_level_entity_id], self._handle_electricity_price_level_update
            )
        )
        # Check if already available
        initial_state = self.hass.states.get(self._electricity_price_level_entity_id)
        if initial_state and initial_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "unknown"):
            await self._start_levels_sensor()

    @callback
    async def _handle_electricity_price_level_update(self, event: Event) -> None:
        new_state: State | None = event.data.get("new_state")
        if new_state and new_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "unknown") and self._waiting_for_first_value:
            await self._start_levels_sensor()

    async def _start_levels_sensor(self):
        if not self._waiting_for_first_value:
            return
        self._waiting_for_first_value = False
        self._service_value, _ = self._fetch_service_value()
        self.async_write_ha_state()
        self._task = self.hass.loop.create_task(self._periodic_update())

    async def async_will_remove_from_hass(self) -> None:
        if self._task:
            self._task.cancel()
        await super().async_will_remove_from_hass()

    async def _periodic_update(self):
        while True:
            self._service_value, next_update = self._fetch_service_value()
            if self.hass:  # Check if hass is available
                self.async_write_ha_state()
            await asyncio.sleep(next_update)

    def _fetch_service_value(self):
        # Call the global calculate_levels function with requested_length=60 (example)
        result = calculate_levels(self.hass, 0)
        period = result.get("level_length")
        levels = result.get("levels", [])

        local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        now_local = datetime.now(local_tz)
        seconds_since_midnight = (now_local - now_local.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
        current_level_index = int(seconds_since_midnight // (period * 60)) if period > 0 else -1
        current_level = levels[current_level_index] if 0 <= current_level_index < len(levels) else 'U'

        next_update_seconds = period * 60 - (seconds_since_midnight % (period * 60)) if period > 0 else 5

        _LOGGER.debug(f"LevelsSensor: Seconds since midnight: {seconds_since_midnight}")
        _LOGGER.debug(f"LevelsSensor _fetch_service_value result: {levels}")
        _LOGGER.debug(f"LevelsSensor current level: {current_level}, seconds to next level: {next_update_seconds}")
        value = {
            "current_level": current_level,
            "level_length": period,
            "levels": levels,
            "seconds_since_midnight": int(seconds_since_midnight),
        }
        return value, next_update_seconds

    @property
    def state(self):
        if self._service_value is not None and isinstance(self._service_value, dict):
            levels = self._service_value.get("levels", [])
            state_value = len([c for c in levels if c != 'U'])
            # Add all fields in value as attributes to the result
            self._state_attrs = dict(self._service_value)
            return state_value
        self._state_attrs = {}
        return "Unknown"

    @property
    def extra_state_attributes(self):
        return getattr(self, '_state_attrs', {})
