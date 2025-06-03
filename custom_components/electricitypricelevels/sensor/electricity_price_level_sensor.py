"""
This module provides the ElectricityPriceLevel sensor for Home Assistant.

The sensor calculates the current electricity price level (Low, Medium, High)
based on Nord Pool spot prices and user-defined thresholds and fees.
It also provides the calculated cost and credit per kWh. The sensor
updates its state when the underlying Nord Pool sensor for the configured
area updates its price, or when new data is pushed to it.
"""

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
    """
    Representation of an Electricity Price Level sensor.

    This sensor entity monitors electricity prices from Nord Pool,
    calculates costs and credits including various fees and taxes,
    and determines if the current price is 'Low', 'Medium', or 'High'
    based on user-defined thresholds.
    """
    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device_info: DeviceInfo) -> None:
        """
        Initialize the ElectricityPriceLevel sensor.

        Args:
            hass: The Home Assistant instance.
            entry: The config entry for this sensor.
            device_info: Device information for the entity.
        """
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

        self._attr_device_info = device_info

        self._nordpool_trigger_entity_id = f"sensor.nord_pool_{self._nordpool_area_id.lower()}_current_price"
        self._remove_nordpool_listener: Callable | None = None

        _LOGGER.debug("ElectricityPriceLevelSensor initialized for area %s, trigger: %s", self._nordpool_area_id, self._nordpool_trigger_entity_id)

    async def async_added_to_hass(self) -> None:
        """
        Run when entity about to be added to Home Assistant.

        This method sets up a listener for state changes of the
        Nord Pool sensor that provides the raw electricity price.
        It also triggers an initial refresh of the sensor state if
        the Nord Pool sensor already has a valid state.
        """
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
        """
        Handle state changes of the tracked Nordpool sensor.

        This callback is triggered when the Nord Pool sensor, which this
        sensor depends on, updates its state. If the new state is valid,
        this method will refresh the ElectricityPriceLevelSensor's state.

        Args:
            event: The event object containing data about the state change.
                   The new state of the Nord Pool sensor is expected in
                   `event.data.get("new_state")`.
        """
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
        """
        Refreshes the sensor's state based on current rates.

        This method updates the internal state values (_state, _cost, _level, etc.)
        by calling `_update_sensor_state_from_current_rate` and then
        schedules an update to Home Assistant to reflect these changes.
        """
        self._update_sensor_state_from_current_rate()
        self._state = round(self._cost, 5)
        self.async_write_ha_state()
        _LOGGER.info(
            f"Sensor state refreshed: Cost={self._state} {self._currency}/{self._unit}, Level={self._level}, RawSpot={self._spot_price}, Rank={self._rank}/100"
        )

    @property
    def state(self):
        """
        Return the state of the sensor.

        The state represents the calculated cost of electricity per unit (e.g., kWh),
        rounded to 5 decimal places.
        """
        return self._state

    @property
    def extra_state_attributes(self):
        """
        Return the extra state attributes of the sensor.

        These attributes provide detailed information related to the electricity price,
        including spot price, cost, credit, unit, currency, price level, rank,
        thresholds, and the full list of rates.
        """
        return {
            "spot_price": self._spot_price,
            "cost": self._cost,
            "credit": self._credit,
            "unit": self._unit,
            "currency": self._currency,
            "level": self._level,
            "rank": self._rank,
            "low_threshold": self._low_threshold,
            "high_threshold": self._high_threshold,
            "rates": self._rates,
        }

    @property
    def unit_of_measurement(self):
        """
        Return the unit of measurement of the sensor.

        Combines the currency and unit (e.g., "EUR/kWh").
        Returns the base unit_of_measurement if currency or unit is not set.
        """
        if self._currency and self._unit:
            return f"{self._currency}/{self._unit}"
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def icon(self):
        """
        Return the icon of the sensor based on the current price level.

        - "mdi:arrow-expand-down" for "Low" level.
        - "mdi:arrow-expand-up" for "High" level.
        - "mdi:arrow-expand-vertical" for "Medium" level.
        - Default icon if level is "Unknown" or not set.
        """
        if self._level == "Low":
            return "mdi:arrow-expand-down"
        if self._level == "High":
            return "mdi:arrow-expand-up"
        if self._level == "Medium":
            return "mdi:arrow-expand-vertical"
        return self._icon

    def _update_sensor_state_from_current_rate(self) -> datetime.datetime | None:
        """
        Update sensor's state attributes from the current hourly rate.

        This method iterates through the stored rates to find the one
        that corresponds to the current time. If a current rate is found,
        it updates the sensor's `_spot_price`, `_cost`, `_credit`, `_level`,
        and `_rank` attributes. It also purges old rates from the `_rates` list.

        Returns:
            The end time of the current rate slot if a current rate is found,
            otherwise None.
        """
        current_rate_details = None
        current_rate_end_time_local = None

        if self._rates:
            try:
                local_tz_str = self._hass.config.time_zone
                local_tz = dt_util.get_time_zone(local_tz_str)
                now_local = datetime.datetime.now(local_tz)
                today_local = now_local.date()

                # Purge old rates
                original_rate_count = len(self._rates)
                self._rates = [rate for rate in self._rates if rate["start"].date() >= today_local]
                purged_count = original_rate_count - len(self._rates)
                if purged_count > 0:
                    _LOGGER.debug(f"Purged {purged_count} old entries from self._rates. Current count: {len(self._rates)}")

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

            processed_rank = current_rate_details.get("rank")

            if isinstance(processed_rank, (int, float)):
                self._rank = processed_rank
            else:
                self._rank = processed_rank if processed_rank == "N/A" else 0

            current_rate_end_time_local = current_rate_details["end"]
            _LOGGER.debug(
                f"Sensor state updated from current_rate: spot_price={self._spot_price}, cost={self._cost}, level={self._level}, rank={self._rank}/100. Slot ends at {current_rate_end_time_local}"
            )
        else:
            _LOGGER.warning("No current rate found in self._rates for the current time. Sensor state will be 'Unknown'.")
            self._level = "Unknown"
            self._spot_price = 0.0
            self._cost = 0.0
            self._credit = 0.0
            self._rank = 0

        return current_rate_end_time_local

    async def async_update_data(self, nordpool_data: dict):
        """
        Process new Nordpool data and update sensor state.

        This method is called when new data is available from the Nord Pool
        coordinator. It parses the raw price entries, calculates costs,
        credits, levels, and ranks for each hourly slot, and stores them.
        Finally, it updates the sensor's current state based on this new data.

        Args:
            nordpool_data: A dictionary containing the new Nord Pool data.
                           Expected keys include "currency" and "raw" (a list
                           of price entries).
        """
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
            f"Sensor state updated via async_update_data: Cost={self._state} {self._currency}/{self._unit}, Level={self._level}, RawSpot={self._spot_price}, Rank={self._rank}/100"
        )


    async def async_will_remove_from_hass(self) -> None:
        """
        Execute when entity is about to be removed from Home Assistant.

        Performs cleanup tasks, such as logging the removal.
        """
        _LOGGER.debug("Removing ElectricityPriceLevelSensor.")
        await super().async_will_remove_from_hass()

    def _process_entry(self, entry_to_process: dict, daily_ranked_list: list[dict]):
        """
        Process a single price entry to calculate its cost, credit, level, and rank.

        This method takes a single entry (representing an hour's price data)
        and a list of all entries for that day (ranked by price). It calculates
        the final cost and credit including all fees and taxes, determines the
        price level (Low, Medium, High), and calculates a percentile rank
        for the price within that day. The processed data is then appended
        to the sensor's `_rates` list.

        Args:
            entry_to_process: A dictionary containing the price entry to process.
                              Expected keys: "start" (datetime), "end" (datetime),
                              "value" (float, spot price in main unit/kWh).
            daily_ranked_list: A list of all price entries for the same day as
                               `entry_to_process`, sorted by price value. This is
                               used to determine the rank.
        """
        start_local = entry_to_process["start"]
        end_local = entry_to_process["end"]
        spot_price_kwh_main_unit = entry_to_process["value"]

        cost, credit = self.calculate_cost_and_credit(spot_price_kwh_main_unit)
        level = self.calculate_level(cost)

        rank_value = "N/A"
        num_entries_today = len(daily_ranked_list)

        try:
            if num_entries_today == 0:
                pass
            else:
                current_0_indexed_rank = next(i for i, ranked_entry in enumerate(daily_ranked_list) if ranked_entry["start"] == start_local and ranked_entry["value"] == spot_price_kwh_main_unit)

                if num_entries_today == 1:
                    rank_value = 1
                else:
                    rank_value = math.floor((current_0_indexed_rank / (num_entries_today - 1)) * 99) + 1

        except StopIteration:
            _LOGGER.warning(f"Could not determine rank for entry starting at {start_local} with value {spot_price_kwh_main_unit}. Appending with rank 'N/A'.")
        except Exception as e:
            _LOGGER.error(f"Error determining rank for {start_local}: {e}", exc_info=True)
            rank_value = "N/A"

        self._rates.append({
            "start": start_local,
            "end": end_local,
            "spot_price": spot_price_kwh_main_unit,
            "cost": cost,
            "credit": credit,
            "level": level,
            "rank": rank_value
        })

    def calculate_cost_and_credit(self, spot_price_main_unit_kwh: float) -> tuple[float, float]:
        """
        Calculate the total cost and credit per kWh based on the spot price and configured fees.

        This method applies various fixed and variable fees (supplier, grid),
        energy tax, and VAT to the spot price to determine the final cost.
        It also calculates the potential credit based on configured credit rates.

        Args:
            spot_price_main_unit_kwh: The raw spot price in the main currency unit per kWh.

        Returns:
            A tuple containing:
                - cost (float): The calculated total cost per kWh, rounded to 5 decimal places.
                - credit (float): The calculated total credit per kWh, rounded to 5 decimal places.
        """
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
        """
        Determine the price level (Low, Medium, High) based on the calculated cost.

        Compares the provided cost against the user-configured low and high
        thresholds to categorize the price.

        Args:
            cost: The calculated cost of electricity per kWh.

        Returns:
            A string representing the price level: "Low", "Medium", or "High".
        """
        cost_val = float(cost)
        low = float(self._low_threshold)
        high = float(self._high_threshold)

        _LOGGER.debug(f"Calculating level for cost: {cost_val}, low: {low}, high: {high}")
        if cost_val < low:
            return "Low"
        if cost_val > high:
            return "High"
        return "Medium"

