"""Support for the ElectricityPriceLevel sensor service."""

from __future__ import annotations

import logging
import json
import datetime
import math
from typing import Callable

from homeassistant.core import HomeAssistant, callback, Event, State
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.util import dt as dt_util
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)

from ..const import (
    CONF_NORDPOOL_AREA_ID,
    CONF_LOW_THRESHOLD,
    CONF_HIGH_THRESHOLD,
    CONF_SUPPLIER_FIXED_FEE,
    CONF_SUPPLIER_VARIABLE_FEE,
    CONF_SUPPLIER_FIXED_CREDIT,
    CONF_SUPPLIER_VARIABLE_CREDIT,
    CONF_GRID_FIXED_FEE,
    CONF_GRID_VARIABLE_FEE,
    CONF_GRID_FIXED_CREDIT,
    CONF_GRID_VARIABLE_CREDIT,
    CONF_GRID_ENERGY_TAX,
    CONF_ELECTRICITY_VAT,
)


_LOGGER = logging.getLogger(__name__)


class ElectricityPriceLevelSensor(SensorEntity):
    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device_info: DeviceInfo) -> None:
        self._hass = hass
        self._entry = entry

        self._nordpool_area_id = entry.options.get(CONF_NORDPOOL_AREA_ID, "")
        self._high_threshold = entry.options.get(CONF_HIGH_THRESHOLD, 0.0) or 1000000000.0
        self._low_threshold = entry.options.get(CONF_LOW_THRESHOLD, 0.0) or -1000000000.0
        self._supplier_fixed_fee = entry.options.get(CONF_SUPPLIER_FIXED_FEE, 0.0) or 0.0
        self._supplier_variable_fee = entry.options.get(CONF_SUPPLIER_VARIABLE_FEE, 0.0) or 0.0
        self._supplier_fixed_credit = entry.options.get(CONF_SUPPLIER_FIXED_CREDIT, 0.0) or 0.0
        self._supplier_variable_credit = entry.options.get(CONF_SUPPLIER_VARIABLE_CREDIT, 0.0) or 0.0
        self._grid_fixed_fee = entry.options.get(CONF_GRID_FIXED_FEE, 0.0) or 0.0
        self._grid_variable_fee = entry.options.get(CONF_GRID_VARIABLE_FEE, 0.0) or 0.0
        self._grid_fixed_credit = entry.options.get(CONF_GRID_FIXED_CREDIT, 0.0) or 0.0
        self._grid_variable_credit = entry.options.get(CONF_GRID_VARIABLE_CREDIT, 0.0) or 0.0
        self._grid_energy_tax = entry.options.get(CONF_GRID_ENERGY_TAX, 0.0) or 0.0
        self._electricity_vat = entry.options.get(CONF_ELECTRICITY_VAT, 0.0) or 0.0

        description = SensorEntityDescription(
            key="electricity_price",
            translation_key="electricity_price",
        )
        self.entity_description = description
        self.entity_id = f"{SENSOR_DOMAIN}.{description.key}"
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self._state = 0.0
        self._spot_price = 0.0
        self._cost = 0.0
        self._credit = 0.0
        self._level = "Unknown"
        self._unit_of_measurement = None
        self._device_class = SensorDeviceClass.MONETARY
        self._icon = "mdi:flash"
        self._unit = None
        self._currency = None
        self._rates = []
        self._rank = 0
        self._max_rank = 0

        self._attr_device_info = device_info

        self._nordpool_trigger_entity_id = f"sensor.nord_pool_{self._nordpool_area_id.lower()}_current_price"
        self._remove_nordpool_listener: Callable | None = None

        _LOGGER.debug("ElectricityPriceLevelSensor initialized for area %s, trigger: %s", self._nordpool_area_id, self._nordpool_trigger_entity_id)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        if self._nordpool_trigger_entity_id:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._nordpool_trigger_entity_id], self._handle_nordpool_trigger_update
                )
            )
            _LOGGER.debug(f"Registered listener for {self._nordpool_trigger_entity_id}")

            # Optionally, trigger an initial update based on the current state of the tracked sensor
            initial_trigger_state = self.hass.states.get(self._nordpool_trigger_entity_id)
            if initial_trigger_state and initial_trigger_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                _LOGGER.debug(f"Initial state of {self._nordpool_trigger_entity_id} is {initial_trigger_state.state}, triggering initial refresh.")
                await self._refresh_sensor_state()
            elif not initial_trigger_state:
                _LOGGER.warning(f"Initial state for {self._nordpool_trigger_entity_id} not found. Waiting for first update.")

    @callback
    async def _handle_nordpool_trigger_update(self, event: Event) -> None:
        """Handle state changes of the tracked Nordpool sensor."""
        new_state: State | None = event.data.get("new_state")

        if not new_state or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.debug(
                f"Tracked Nordpool sensor {self._nordpool_trigger_entity_id} is now {new_state.state if new_state else 'None'}. "
                "Sensor state will not be refreshed by this trigger."
            )
            return

        _LOGGER.debug(
            f"Tracked Nordpool sensor {self._nordpool_trigger_entity_id} changed to {new_state.state}. "
            "Refreshing ElectricityPriceLevelSensor state."
        )
        await self._refresh_sensor_state()

    async def _refresh_sensor_state(self) -> None:
        """Refreshes the sensor's state based on current rates."""
        self._update_sensor_state_from_current_rate()
        self._state = round(self._cost, 5)
        self.async_write_ha_state()
        _LOGGER.info(
            f"Sensor state refreshed: Cost={self._state} {self._currency}/{self._unit}, Level={self._level}, RawSpot={self._spot_price}, Rank={self._rank}/{self._max_rank}"
        )

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {
            "spot_price": self._spot_price,
            "cost": self._cost,
            "credit": self._credit,
            "unit": self._unit,
            "currency": self._currency,
            "level": self._level,
            "rank": self._rank,
            "max_rank": self._max_rank,
            "low_threshold": self._low_threshold,
            "high_threshold": self._high_threshold,
            "rates": self._rates,
        }

    @property
    def unit_of_measurement(self):
        if self._currency and self._unit:
            return f"{self._currency}/{self._unit}"
        return self._unit_of_measurement

    @property
    def device_class(self):
        return self._device_class

    @property
    def icon(self):
        if self._level == "Low":
            return "mdi:arrow-expand-down"
        if self._level == "High":
            return "mdi:arrow-expand-up"
        if self._level == "Medium":
            return "mdi:arrow-expand-vertical"
        return self._icon

    def _update_sensor_state_from_current_rate(self) -> datetime.datetime | None:
        current_rate_details = None
        current_rate_end_time_local = None

        if self._rates:
            try:
                local_tz_str = self._hass.config.time_zone
                local_tz = dt_util.get_time_zone(local_tz_str)
                now_local = datetime.datetime.now(local_tz)
                _LOGGER.debug("Finding current rate for time: %s in timezone %s", now_local, local_tz_str)

                current_rate_details = next((rate for rate in self._rates if rate["start"] <= now_local < rate["end"]), None)

                if current_rate_details:
                    _LOGGER.debug("Current rate details found: %s", current_rate_details["start"])
                else:
                    _LOGGER.debug("No current rate details found for %s in self._rates (%s entries)", now_local, len(self._rates))

            except Exception as e:
                _LOGGER.error("Error finding current rate during state update: %s", e, exc_info=True)

        if current_rate_details:
            self._spot_price = current_rate_details["spot_price"]
            self._cost = current_rate_details["cost"]
            self._credit = current_rate_details["credit"]
            self._level = current_rate_details["level"]
            self._rank = current_rate_details.get("rank", 0)

            current_rate_date = current_rate_details["start"].date()
            rates_for_current_day = [r for r in self._rates if r["start"].date() == current_rate_date]
            self._max_rank = len(rates_for_current_day) - 1 if rates_for_current_day else 0
            if self._max_rank < 0: self._max_rank = 0

            current_rate_end_time_local = current_rate_details["end"]
            _LOGGER.debug(
                f"Sensor state updated from current_rate: spot_price={self._spot_price}, cost={self._cost}, level={self._level}, rank={self._rank}/{self._max_rank}. Slot ends at {current_rate_end_time_local}"
            )
        else:
            _LOGGER.warning("No current rate found in self._rates for the current time. Sensor state will be 'Unknown'/0.")
            self._level = "Unknown"
            self._spot_price = 0.0
            self._cost = 0.0
            self._credit = 0.0
            self._rank = 0
            self._max_rank = 0

        return current_rate_end_time_local

    async def async_update_data(self, nordpool_data: dict):
        """Process new Nordpool data and update sensor state."""
        _LOGGER.debug("async_update_data called with new Nordpool data: %s", json.dumps(nordpool_data, indent=2, default=str))
        try:
            self._unit = "kWh"
            new_currency = nordpool_data.get("currency")
            if new_currency and self._currency != new_currency:
                self._currency = new_currency
                self._unit_of_measurement = f"{self._currency}/{self._unit}" if self._currency and self._unit else None

            self._rates = []
            raw_price_entries = nordpool_data.get("raw", [])

            if raw_price_entries:
                processed_for_ranking = []
                local_tz = dt_util.get_time_zone(self._hass.config.time_zone)

                for entry_data in raw_price_entries:
                    start_local = dt_util.parse_datetime(entry_data["start"]).astimezone(local_tz)
                    end_local = dt_util.parse_datetime(entry_data["end"]).astimezone(local_tz)
                    if end_local:
                        end_local = end_local - datetime.timedelta(microseconds=1)

                    price_mwh = entry_data["price"]

                    if start_local and end_local and price_mwh is not None:
                        price_kwh = price_mwh / 1000.0

                        _LOGGER.debug(f"Processing entry: start={start_local}, end={end_local}, price_mwh={price_mwh}, price_kwh={price_kwh}")
                        processed_for_ranking.append({
                            "start": start_local,
                            "end": end_local,
                            "value": price_kwh
                        })

                entries_by_day = {}
                for entry in processed_for_ranking:
                    day = entry["start"].date()
                    if day not in entries_by_day:
                        entries_by_day[day] = []
                    entries_by_day[day].append(entry)

                for day_entries in entries_by_day.values():
                    ranked_day_entries = sorted(day_entries, key=lambda x: x["value"])
                    for entry_to_process in day_entries:
                        self._process_entry(entry_to_process, ranked_day_entries)

                self._rates.sort(key=lambda x: x["start"])

            _LOGGER.debug("Processed %s rates into self._rates", len(self._rates))

        except Exception as e:
            _LOGGER.error("Error processing Nordpool data structure: %s. Data: %s", e, nordpool_data, exc_info=True)
            self._level = "Error Processing Data"
            self._cost = 0.0
            self._spot_price = 0.0
            self._state = round(self._cost, 5)
            self.async_write_ha_state()
            return

        self._update_sensor_state_from_current_rate()
        self._state = round(self._cost, 5)
        self.async_write_ha_state()
        _LOGGER.info(
            f"Sensor state updated via async_update_data: Cost={self._state} {self._currency}/{self._unit}, Level={self._level}, RawSpot={self._spot_price}, Rank={self._rank}/{self._max_rank}"
        )


    async def async_will_remove_from_hass(self) -> None:
        _LOGGER.debug("Removing ElectricityPriceLevelSensor.")
        await super().async_will_remove_from_hass()

    def _process_entry(self, entry_to_process, daily_ranked_list):
        start_local = entry_to_process["start"]
        end_local = entry_to_process["end"]
        spot_price_kwh_main_unit = entry_to_process["value"]

        cost, credit = self.calculate_cost_and_credit(spot_price_kwh_main_unit)
        level = self.calculate_level(cost)
        rank = "N/A"

        try:
            rank = next(i for i, ranked_entry in enumerate(daily_ranked_list) if ranked_entry["start"] == start_local and ranked_entry["value"] == spot_price_kwh_main_unit)
        except StopIteration:
            _LOGGER.warning(f"Could not determine rank for entry starting at {start_local} with value {spot_price_kwh_main_unit}. Appending with rank 'N/A'.")
        except Exception as e:
            _LOGGER.error(f"Error determining rank for {start_local}: {e}", exc_info=True)

        self._rates.append({
            "start": start_local,
            "end": end_local,
            "spot_price": spot_price_kwh_main_unit,
            "cost": cost,
            "credit": credit,
            "level": level,
            "rank": rank
        })

    def calculate_cost_and_credit(self, spot_price_main_unit_kwh: float):
        supplier_fixed_fee = float(self._supplier_fixed_fee)
        supplier_variable_fee_pct = float(self._supplier_variable_fee) / 100
        supplier_fixed_credit = float(self._supplier_fixed_credit)
        supplier_variable_credit_pct = float(self._supplier_variable_credit) / 100
        grid_fixed_fee = float(self._grid_fixed_fee)
        grid_variable_fee_pct = float(self._grid_variable_fee) / 100
        grid_fixed_credit = float(self._grid_fixed_credit)
        grid_variable_credit_pct = float(self._grid_variable_credit) / 100
        grid_energy_tax = float(self._grid_energy_tax)
        electricity_vat_pct = float(self._electricity_vat) / 100

        cost_before_vat = (
            spot_price_main_unit_kwh * (1 + supplier_variable_fee_pct + grid_variable_fee_pct) +
            supplier_fixed_fee +
            grid_fixed_fee +
            grid_energy_tax
        )
        cost = cost_before_vat * (1 + electricity_vat_pct)

        credit = (
            spot_price_main_unit_kwh * (1 + supplier_variable_credit_pct + grid_variable_credit_pct) +
            supplier_fixed_credit +
            grid_fixed_credit
        )
        return round(cost, 5), round(credit, 5)

    def calculate_level(self, cost: float) -> str:
        cost_val = float(cost)
        low = float(self._low_threshold)
        high = float(self._high_threshold)

        if cost_val < low:
            return "Low"
        if cost_val > high:
            return "High"
        return "Medium"