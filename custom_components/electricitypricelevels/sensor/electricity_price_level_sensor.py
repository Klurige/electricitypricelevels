"""Support for the ElectricityPriceLevel sensor service."""

from __future__ import annotations

import logging
import json
import datetime
# cmath.inf is not used, can be removed if not needed elsewhere.
# from cmath import inf

# import pytz # Replaced with dt_util
from homeassistant.util import dt as dt_util # Added for timezone handling
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass, # Not explicitly used in this class, but kept for context
    SensorEntity,
    SensorEntityDescription,
)
# from homeassistant.const import EVENT_STATE_CHANGED # No longer needed

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
from homeassistant.config_entries import ConfigEntry # Added type hint

_LOGGER = logging.getLogger(__name__)


class ElectricityPriceLevelSensor(SensorEntity):
    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(self, hass, entry: ConfigEntry, device_info) -> None:
        self._nordpool_area_id = entry.options.get(CONF_NORDPOOL_AREA_ID, "").upper()
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

        self._state = 0
        self._raw = 0
        self._cost = 0
        self._credit = 0
        self._level = "Unknown"
        self._unit_of_measurement = None
        self._device_class = SensorDeviceClass.MONETARY
        self._icon = "mdi:flash"
        self._unit = None # e.g. "EUR/kWh"
        self._currency = None # e.g. "EUR"
        self._price_in_cents = False
        self._price_divisor = 1
        self._rates = []
        self._rank = 0
        self._max_rank = 0

        self._hass = hass
        self._attr_device_info = device_info
        _LOGGER.debug("ElectricityPriceLevelSensor initialized")

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {
            "raw": self._raw,
            "cost": self._cost,
            "credit": self._credit,
            "unit": self._unit,
            "currency": self._currency,
            "price_in_cents": self._price_in_cents,
            "level": self._level,
            "rank": self._rank,
            "max_rank": self._max_rank,
            "low_threshold": self._low_threshold,
            "high_threshold": self._high_threshold,
            "rates": self._rates,
        }

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    @property
    def device_class(self):
        return self._device_class

    @property
    def icon(self):
        return self._icon

    async def async_update_data(self, nordpool_attributes: dict):
        """Process new Nordpool data and update sensor state."""
        _LOGGER.debug("Processing new Nordpool data: %s", json.dumps(nordpool_attributes, indent=4, default=str))
        try:
            self._price_in_cents = nordpool_attributes.get("price_in_cents", False)
            self._price_divisor = 100 if self._price_in_cents else 1

            self._unit_of_measurement = nordpool_attributes.get("unit_of_measurement")
            # self._device_class = nordpool_attributes.get("device_class") # Or set statically
            self._icon = nordpool_attributes.get("icon") # Or set statically
            self._unit = nordpool_attributes.get("unit")
            self._currency = nordpool_attributes.get("currency")
            self._rates = []

            # Process today's rates
            if "raw_today" in nordpool_attributes and nordpool_attributes["raw_today"]:
                raw_today_ranked = sorted(nordpool_attributes["raw_today"], key=lambda x: x["value"])
                for entry in nordpool_attributes["raw_today"]:
                    self._process_entry(entry, raw_today_ranked)

            # Process tomorrow's rates
            if "raw_tomorrow" in nordpool_attributes and nordpool_attributes["raw_tomorrow"]:
                raw_tomorrow_ranked = sorted(nordpool_attributes["raw_tomorrow"], key=lambda x: x["value"])
                for entry in nordpool_attributes["raw_tomorrow"]:
                    self._process_entry(entry, raw_tomorrow_ranked)

        except Exception as e: # pylint: disable=broad-except
            _LOGGER.error("Error processing Nordpool attributes: %s. Attributes: %s", e, nordpool_attributes, exc_info=True)
            # Reset to safe defaults or previous state if possible
            self._level = "Unknown"
            self.async_write_ha_state()
            return

        _LOGGER.debug("Processed %s rates", len(self._rates))
        current_rate = None
        if self._rates:
            try:
                local_tz_str = self._hass.config.time_zone
                local_tz = dt_util.get_time_zone(local_tz_str)
                now = datetime.datetime.now(local_tz)
                current_rate = next((rate for rate in self._rates if rate["start"] <= now < rate["end"]), None)
            except Exception as e: # pylint: disable=broad-except
                _LOGGER.error("Error finding current rate: %s", e, exc_info=True)


        if current_rate:
            self._raw = current_rate["original_spot_price"] / self._price_divisor
            self._cost = current_rate["cost"]
            self._credit = current_rate["credit"]
            self._level = current_rate["level"]
            self._rank = current_rate["rank"]
            self._max_rank = len([r for r in self._rates if r["start"].date() == current_rate["start"].date()]) -1

        else:
            _LOGGER.warning("No current rate found for now. Checking for 'current_price' in attributes.")
            current_price_from_attrs = nordpool_attributes.get("current_price")
            if current_price_from_attrs is not None:
                try:
                    spot_price_val = float(current_price_from_attrs)
                    self._raw = spot_price_val / self._price_divisor
                    self._cost, self._credit = self.calculate_cost_and_credit(self._raw) # Pass the already divided value
                    self._level = self.calculate_level(self._cost)
                    self._rank = 0 # Rank is unknown in this fallback
                    self._max_rank = 0 # Max rank is unknown
                    _LOGGER.info("Using 'current_price' attribute fallback: raw=%s, cost=%s", self._raw, self._cost)
                except ValueError:
                    _LOGGER.error("Invalid 'current_price' in attributes: %s", current_price_from_attrs)
                    self._level = "Unknown" # Fallback
            else:
                _LOGGER.error("No current rate found and 'current_price' not in attributes. State is uncertain.")
                self._level = "Unknown" # Fallback
                # Consider setting raw/cost to 0 or a special value
                self._raw = 0
                self._cost = 0
                self._credit = 0
                self._rank = 0
                self._max_rank = 0


        self._state = self._cost
        self.async_write_ha_state()

    def _process_entry(self, entry, raw_ranked):
        start = entry["start"] # Assuming this is already a datetime object
        end = entry["end"]     # Assuming this is already a datetime object
        value = entry["value"] # This is the raw spot price, possibly in cents

        # Cost and credit calculations expect spot price in the main currency unit (not cents)
        spot_price_main_unit = float(value) / self._price_divisor
        cost, credit = self.calculate_cost_and_credit(spot_price_main_unit)
        level = self.calculate_level(cost)
        try:
            # Rank within its own day
            daily_raw_ranked = [r for r in raw_ranked if r["start"].date() == start.date()]
            rank = next(i for i, ranked_entry in enumerate(daily_raw_ranked) if ranked_entry["start"] == start)

            self._rates.append({
                "start": start,
                "end": end,
                "original_spot_price": float(value), # Store the original value as is (e.g. in cents if price_in_cents)
                "cost": cost,
                "credit": credit,
                "level": level,
                "rank": rank
            })
        except StopIteration:
            _LOGGER.warning(f"Could not determine rank for entry starting at {start}. Appending without rank.")
            self._rates.append({
                "start": start,
                "end": end,
                "original_spot_price": float(value),
                "cost": cost,
                "credit": credit,
                "level": level
                # "rank" will be missing
            })
        except TypeError as e:
            _LOGGER.error(f"TypeError during rank calculation for entry {entry}: {e}. raw_ranked: {raw_ranked}")


    def calculate_cost_and_credit(self, spot_price_main_unit):
        # Fees are configured as main unit / 100 for percentages, or main unit for fixed.
        # Price divisor is already handled for spot_price_main_unit.
        # Configured fees (e.g., _supplier_fixed_fee) are assumed to be in the main currency unit.

        supplier_fixed_fee = float(self._supplier_fixed_fee) # Already in main unit
        supplier_variable_fee_pct = float(self._supplier_variable_fee) / 100
        supplier_fixed_credit = float(self._supplier_fixed_credit) # Already in main unit
        supplier_variable_credit_pct = float(self._supplier_variable_credit) / 100
        grid_fixed_fee = float(self._grid_fixed_fee) # Already in main unit
        grid_variable_fee_pct = float(self._grid_variable_fee) / 100
        grid_fixed_credit = float(self._grid_fixed_credit) # Already in main unit
        grid_variable_credit_pct = float(self._grid_variable_credit) / 100
        grid_energy_tax = float(self._grid_energy_tax) # Already in main unit
        electricity_vat_pct = float(self._electricity_vat) / 100

        # Calculate cost
        # Cost = (BaseSpot + SupplierFeeFixed + GridFeeFixed + Spot*(SupplierVarFee + GridVarFee) + EnergyTax) * (1+VAT)
        cost_before_vat = (
            spot_price_main_unit * (1 + supplier_variable_fee_pct + grid_variable_fee_pct) +
            supplier_fixed_fee +
            grid_fixed_fee +
            grid_energy_tax
        )
        cost = cost_before_vat * (1 + electricity_vat_pct)
        cost = round(cost, 5)

        # Calculate credit
        # Credit = (BaseSpot + SupplierCreditFixed + GridCreditFixed + Spot*(SupplierVarCredit + GridVarCredit))
        # Assuming credit is not subject to VAT or energy tax in this calculation structure.
        credit = (
            spot_price_main_unit * (1 + supplier_variable_credit_pct + grid_variable_credit_pct) +
            supplier_fixed_credit +
            grid_fixed_credit
        )
        credit = round(credit, 5)

        return cost, credit

    def calculate_level(self, cost):
        cost_val = float(cost)
        low = float(self._low_threshold)
        high = float(self._high_threshold)
        level = "Unknown"
        if cost_val < low:
            level = "Low"
        elif cost_val > high:
            level = "High"
        else:
            level = "Medium"
        # _LOGGER.debug("Cost: %s, Low: %s, High: %s, Level: %s", cost_val, low, high, level) # Can be verbose
        return level