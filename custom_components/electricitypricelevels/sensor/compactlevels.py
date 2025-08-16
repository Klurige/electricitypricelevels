import math

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
import logging

_LOGGER = logging.getLogger(__name__)

simulationLevelIndex = -1

class CompactLevelsDataSensor(SensorEntity):
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
        self._entry = entry
        self._state_attrs = None
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry.entry_id}_levels"
        # Use translated name from entity description
        self._attr_name = self._get_translated_name(hass)
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
        global simulationLevelIndex
        next_update_seconds = None
        compact = None
        seconds_since_midnight = 0

        if simulationLevelIndex >= 0:
            simulated_levels = "LMHM" * 40  # 160 values, repeating LMHM
            seconds_since_midnight = simulationLevelIndex * 12 * 60
            start = simulationLevelIndex
            end = start + 60
            if end <= len(simulated_levels):
                levels = simulated_levels[start:end]
            else:
                levels = simulated_levels[start:] + simulated_levels[:end - len(simulated_levels)]
            simulationLevelIndex = (simulationLevelIndex + 1) % len(simulated_levels)
            next_update_seconds = 10
            compact = f"{int(seconds_since_midnight)}:{12}:{levels}"

        else:
            # Use real values
            required_level_length = 12
            result = calculate_levels(self.hass, required_level_length)
            period = float(result.get("level_length", 1))
            levels_str = result.get("levels", "")
            local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
            now_local = datetime.now(local_tz)
            seconds_since_midnight = (now_local - now_local.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()
            current_level_index = int(seconds_since_midnight // (period * 60)) if period > 0 else -1
            intervals_in_12h = (12 * 60) // required_level_length
            next_levels = levels_str[current_level_index:current_level_index + intervals_in_12h]
            if len(next_levels) < intervals_in_12h:
                next_levels += 'U' * (intervals_in_12h - len(next_levels))
            interval_seconds = period * 60
            seconds_into_period = seconds_since_midnight % interval_seconds if period > 0 else 0
            next_update_seconds = interval_seconds - seconds_into_period if period > 0 else 5
            compact = f"{int(seconds_since_midnight)}:{int(period) if period > 0 else 0}:{next_levels}"

        value = {
            "compact": compact,
            "seconds_since_midnight": int(seconds_since_midnight),
        }

        _LOGGER.debug(f"Fetched service value: {value} ({len(value)}), next update in seconds: {next_update_seconds}")
        return value, next_update_seconds

    @property
    def state(self):
        if isinstance(self._service_value, str):
            levels = self._service_value.get("seconds_since_midnight", [])
            state_value = len([c for c in levels if c != 'U'])
            self._state_attrs = dict(self._service_value)
            return state_value

        self._state_attrs = {}
        return "Unknown"

    @property
    def extra_state_attributes(self):
        return getattr(self, '_state_attrs', {})

    def _get_translated_name(self, hass: HomeAssistant) -> str:
        # Try to get the friendly name from translations
        translations = hass.data.get('custom_components.electricitypricelevels.translations', {})
        lang = hass.config.language if hasattr(hass.config, 'language') else 'en'
        name = (
            translations.get(lang, {})
            .get('entity', {})
            .get('sensor', {})
            .get('compactlevels', {})
            .get('name')
        )
        return name or "Levels"

def calculate_levels(hass, requested_length, fill_unknown: bool = False):
    levels_str = ""
    low_threshold = None
    high_threshold = None
    level_length = 0
    _LOGGER.debug("Calculating levels with requested length: %d, fill_unknown: %s", requested_length, fill_unknown)
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

    if levels_str and fill_unknown and level_length > 0:
        two_days = int(2 * 24 * 60 / level_length)
        if len(levels_str) < two_days:
            levels_str += "U" * (two_days - len(levels_str))

    _LOGGER.debug(f"Low threshold: {low_threshold}, High threshold: {high_threshold}")
    _LOGGER.debug(f"Level length: {level_length}, Levels: {len(levels_str)}, Levels string: {levels_str}")

    result: dict[str, str] = { "level_length": level_length, "levels": levels_str, "low_threshold": low_threshold, "high_threshold": high_threshold }
    return result
