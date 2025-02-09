"""Support for the ElectricityPriceLevel sensor service."""

from __future__ import annotations

import logging
import json

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EVENT_STATE_CHANGED

from ..const import (
    CONF_NORDPOOL_SENSOR_ID,
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

    def __init__(self, hass, entry: ConfigEntry, device_info) -> None:
        self._nordpool_sensor_id = entry.options.get(CONF_NORDPOOL_SENSOR_ID, "")
        self._high_threshold = entry.options.get(CONF_HIGH_THRESHOLD, 0.0)
        self._low_threshold = entry.options.get(CONF_LOW_THRESHOLD, 0.0)
        self._supplier_fixed_fee = entry.options.get(CONF_SUPPLIER_FIXED_FEE, 0.0)
        self._supplier_variable_fee = entry.options.get(CONF_SUPPLIER_VARIABLE_FEE, 0.0)
        self._supplier_fixed_credit = entry.options.get(CONF_SUPPLIER_FIXED_CREDIT, 0.0)
        self._supplier_variable_credit = entry.options.get(CONF_SUPPLIER_VARIABLE_CREDIT, 0.0)
        self._grid_fixed_fee = entry.options.get(CONF_GRID_FIXED_FEE, 0.0)
        self._grid_variable_fee = entry.options.get(CONF_GRID_VARIABLE_FEE, 0.0)
        self._grid_fixed_credit = entry.options.get(CONF_GRID_FIXED_CREDIT, 0.0)
        self._grid_variable_credit = entry.options.get(CONF_GRID_VARIABLE_CREDIT, 0.0)
        self._grid_energy_tax = entry.options.get(CONF_GRID_ENERGY_TAX, 0.0)
        self._electricity_vat = entry.options.get(CONF_ELECTRICITY_VAT, 0.0)

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
        self._device_class = None
        self._icon = None
        self._unit = None
        self._currency = None
        self._price_in_cents = False
        self._price_divisor = 1
        self._rates = []

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

    async def async_added_to_hass(self):
        if self._hass:
            self._hass.bus.async_listen(EVENT_STATE_CHANGED, self._handle_event)
            initial_state = self._hass.states.get(self._nordpool_sensor_id)
            if initial_state:
                await self._process_incoming_value(initial_state.state, initial_state.attributes)
        else:
            _LOGGER.error("Home Assistant instance is not available")

    async def _handle_event(self, event):
        if event.data.get("entity_id") == self._nordpool_sensor_id:
            new_state = event.data.get("new_state")
            if new_state:
                await self._process_incoming_value(new_state.state, new_state.attributes)

    async def _process_incoming_value(self, incoming_value, incoming_attributes):
        _LOGGER.debug("Nordpool value: %s", incoming_value)
        _LOGGER.debug("Nordpool attributes: %s", json.dumps(incoming_attributes, indent=4, default=str))
        try:
            self._price_in_cents = incoming_attributes.get("price_in_cents")
            if self._price_in_cents:
                self._price_divisor = 100
            else:
                self._price_divisor = 1
            incoming_value = float(incoming_value) / self._price_divisor
            self._raw = incoming_value
            self._cost, self._credit = self.calculate_cost_and_credit(incoming_value)
            self._level = self.calculate_level(self._cost)
            self._state = self._cost
            self._unit_of_measurement = incoming_attributes.get("unit_of_measurement")
            self._device_class = incoming_attributes.get("device_class")
            self._icon = incoming_attributes.get("icon")
            self._unit = incoming_attributes.get("unit")
            self._currency = incoming_attributes.get("currency")
            self._rates = []

            if "raw_today" in incoming_attributes:
                raw_ranked = incoming_attributes["raw_today"].copy()
                raw_ranked.sort(key=lambda x: x["value"])
                for entry in incoming_attributes["raw_today"]:
                    self._process_entry(entry, raw_ranked)

            if "raw_tomorrow" in incoming_attributes:
                raw_ranked = incoming_attributes["raw_tomorrow"].copy()
                raw_ranked.sort(key=lambda x: x["value"])
                for entry in incoming_attributes["raw_tomorrow"]:
                    self._process_entry(entry, raw_ranked)

        except ValueError:
            _LOGGER.error("Invalid nordpool value: %s", incoming_value)
        _LOGGER.debug("Got rates %s", len(self._rates))
        self.async_write_ha_state()

    def _process_entry(self, entry, raw_ranked):
        start = entry["start"]
        end = entry["end"]
        value = entry["value"]
        cost, credit = self.calculate_cost_and_credit(value)
        level = self.calculate_level(cost)
        try:
            rank = next(i for i, ranked_entry in enumerate(raw_ranked) if ranked_entry["start"] == start)
            self._rates.append(
                {"start": start, "end": end, "cost": cost, "credit": credit, "level": level, "rank": rank})
        except StopIteration:
            self._rates.append(
                {"start": start, "end": end, "cost": cost, "credit": credit, "level": level})

    def calculate_cost_and_credit(self, nordpool_value):
        spot = float(nordpool_value)
        supplier_fixed_fee = float(self._supplier_fixed_fee) / self._price_divisor
        supplier_variable_fee = float(self._supplier_variable_fee) / 100
        supplier_fixed_credit = float(self._supplier_fixed_credit) / self._price_divisor
        supplier_variable_credit = float(self._supplier_variable_credit) / 100
        grid_fixed_fee = float(self._grid_fixed_fee) / self._price_divisor
        grid_variable_fee = float(self._grid_variable_fee) / 100
        grid_fixed_credit = float(self._grid_fixed_credit) / self._price_divisor
        grid_variable_credit = float(self._grid_variable_credit) / 100
        grid_energy_tax = float(self._grid_energy_tax) / self._price_divisor
        electricity_vat = float(self._electricity_vat) / 100

        # Calculate cost
        cost = (supplier_fixed_fee + grid_fixed_fee + spot * (1 + supplier_variable_fee + grid_variable_fee) + grid_energy_tax) * (1 + electricity_vat)
        cost = round(cost, 5)

        # Calculate credit
        credit = (supplier_fixed_credit + grid_fixed_credit + spot * (1 + supplier_variable_credit + grid_variable_credit))
        credit = round(credit, 5)

        return cost, credit

    def calculate_level(self, cost):
        cost = float(cost)
        low = float(self._low_threshold)
        high = float(self._high_threshold)
        level = "Unknown"
        if cost < low:
            level = "Low"
        elif cost > high:
            level = "High"
        else:
            level = "Medium"
        _LOGGER.debug("Cost: %s, Low: %s, High: %s, Level: %s", cost, low, high, level)
        return level
