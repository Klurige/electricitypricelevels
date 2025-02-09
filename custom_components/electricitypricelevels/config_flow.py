"""Config flow for ElectricityPriceLevel integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from voluptuous_serialize import convert
from homeassistant.helpers.selector import selector
import homeassistant.helpers.config_validation as cv

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_NORDPOOL_SENSOR_ID,
    CONF_LOW_THRESHOLD,
    CONF_HIGH_THRESHOLD,
    CONF_SUPPLIER_NOTE,
    CONF_SUPPLIER_FIXED_FEE,
    CONF_SUPPLIER_VARIABLE_FEE,
    CONF_SUPPLIER_FIXED_CREDIT,
    CONF_SUPPLIER_VARIABLE_CREDIT,
    CONF_GRID_NOTE,
    CONF_GRID_FIXED_FEE,
    CONF_GRID_VARIABLE_FEE,
    CONF_GRID_FIXED_CREDIT,
    CONF_GRID_VARIABLE_CREDIT,
    CONF_GRID_ENERGY_TAX,
    CONF_ELECTRICITY_VAT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ElectricityPriceLevelFlowHandler(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.data = {}

    @staticmethod
    @callback
    def async_get_options_flow(
            config_entry: ConfigEntry,
    ) -> ElectricityPriceLevelOptionFlowHandler:
        return ElectricityPriceLevelOptionFlowHandler()

    async def async_step_user(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            self.data.update(user_input)
            nordpool_sensor_id = user_input[CONF_NORDPOOL_SENSOR_ID]
            state = self.hass.states.get(nordpool_sensor_id)
            if state:
                unit_of_measurement = state.attributes.get("unit_of_measurement", "")
                currency = state.attributes.get("currency", "")
                prices_in_cents = state.attributes.get("prices_in_cents", False)
                _price_divisor = 1 if prices_in_cents else 100
                self.data.update({
                    "unit_of_measurement": unit_of_measurement,
                    "currency": currency,
                    "price_divisor": _price_divisor,
                })
            return await self.async_step_supplier_fees_and_credits()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NORDPOOL_SENSOR_ID): selector({"entity": {"domain": "sensor"}}),
            }),
            errors=errors
        )

    async def async_step_supplier_fees_and_credits(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        unit_of_measurement = self.data.get("unit_of_measurement", "")
        if user_input is not None:
            self.data[CONF_SUPPLIER_NOTE] = user_input.get(CONF_SUPPLIER_NOTE, None)
            self.data[CONF_SUPPLIER_FIXED_FEE] = user_input.get(CONF_SUPPLIER_FIXED_FEE, None)
            self.data[CONF_SUPPLIER_VARIABLE_FEE] = user_input.get(CONF_SUPPLIER_VARIABLE_FEE, None)
            self.data[CONF_SUPPLIER_FIXED_CREDIT] = user_input.get(CONF_SUPPLIER_FIXED_CREDIT, None)
            self.data[CONF_SUPPLIER_VARIABLE_CREDIT] = user_input.get(CONF_SUPPLIER_VARIABLE_CREDIT, None)
            return await self.async_step_grid_fees_and_credits()

        return self.async_show_form(
            step_id="supplier_fees_and_credits",
            data_schema=vol.Schema({
                vol.Optional(CONF_SUPPLIER_NOTE): vol.Coerce(str),
                vol.Optional(CONF_SUPPLIER_FIXED_FEE, description={"suffix": unit_of_measurement}): vol.All(vol.Coerce(float), cv.positive_float),
                vol.Optional(CONF_SUPPLIER_VARIABLE_FEE, description={"suffix": "%"}): vol.All(vol.Coerce(float),cv.positive_float),
                vol.Optional(CONF_SUPPLIER_FIXED_CREDIT, description={"suffix": unit_of_measurement}): vol.All(vol.Coerce(float),cv.positive_float),
                vol.Optional(CONF_SUPPLIER_VARIABLE_CREDIT, description={"suffix": "%"}): vol.All(vol.Coerce(float),cv.positive_float),
            }),
            errors=errors
        )

    async def async_step_grid_fees_and_credits(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        unit_of_measurement = self.data.get("unit_of_measurement", "")
        if user_input is not None:
            self.data[CONF_GRID_NOTE] = user_input.get(CONF_GRID_NOTE, None)
            self.data[CONF_GRID_FIXED_FEE] = user_input.get(CONF_GRID_FIXED_FEE, None)
            self.data[CONF_GRID_VARIABLE_FEE] = user_input.get(CONF_GRID_VARIABLE_FEE, None)
            self.data[CONF_GRID_FIXED_CREDIT] = user_input.get(CONF_GRID_FIXED_CREDIT, None)
            self.data[CONF_GRID_VARIABLE_CREDIT] = user_input.get(CONF_GRID_VARIABLE_CREDIT, None)
            return await self.async_step_taxes_and_vat()

        return self.async_show_form(
            step_id="grid_fees_and_credits",
            data_schema=vol.Schema({
                vol.Optional(CONF_GRID_NOTE): vol.Coerce(str),
                vol.Optional(CONF_GRID_FIXED_FEE, description={"suffix": unit_of_measurement}): vol.All(vol.Coerce(float), cv.positive_float),
                vol.Optional(CONF_GRID_VARIABLE_FEE, description={"suffix": "%"}): vol.All(vol.Coerce(float),cv.positive_float),
                vol.Optional(CONF_GRID_FIXED_CREDIT, description={"suffix": unit_of_measurement}): vol.All(vol.Coerce(float),cv.positive_float),
                vol.Optional(CONF_GRID_VARIABLE_CREDIT, description={"suffix": "%"}): vol.All(vol.Coerce(float),cv.positive_float),
            }),
            errors=errors
        )

    async def async_step_taxes_and_vat(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        unit_of_measurement = self.data.get("unit_of_measurement", "")
        if user_input is not None:
            self.data[CONF_GRID_ENERGY_TAX] = user_input.get(CONF_GRID_ENERGY_TAX, None)
            self.data[CONF_ELECTRICITY_VAT] = user_input.get(CONF_ELECTRICITY_VAT, None)
            return await self.async_step_thresholds()

        return self.async_show_form(
            step_id="taxes_and_vat",
            data_schema=vol.Schema({
                vol.Optional(CONF_GRID_ENERGY_TAX, description={"suffix": unit_of_measurement}): vol.All(vol.Coerce(float), cv.positive_float),
                vol.Optional(CONF_ELECTRICITY_VAT, description={"suffix": "%"}): vol.All(vol.Coerce(float), cv.positive_float),
            }),
            errors=errors
        )

    async def async_step_thresholds(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        unit_of_measurement = self.data.get("unit_of_measurement", "")
        if user_input is not None:
            low_threshold = user_input.get(CONF_LOW_THRESHOLD)
            high_threshold = user_input.get(CONF_HIGH_THRESHOLD)

            if low_threshold is not None and high_threshold is not None and low_threshold > high_threshold:
                errors["base"] = "low_threshold_higher_than_high_threshold"
            else:
                self.data[CONF_LOW_THRESHOLD] = low_threshold
                self.data[CONF_HIGH_THRESHOLD] = high_threshold
                return self.async_create_entry(
                    title="ElectricityPriceLevel",
                    data=self.data,
                    options={
                        CONF_NORDPOOL_SENSOR_ID: self.data[CONF_NORDPOOL_SENSOR_ID],
                        CONF_SUPPLIER_NOTE: self.data[CONF_SUPPLIER_NOTE],
                        CONF_SUPPLIER_FIXED_FEE: self.data[CONF_SUPPLIER_FIXED_FEE],
                        CONF_SUPPLIER_VARIABLE_FEE: self.data[CONF_SUPPLIER_VARIABLE_FEE],
                        CONF_SUPPLIER_FIXED_CREDIT: self.data[CONF_SUPPLIER_FIXED_CREDIT],
                        CONF_SUPPLIER_VARIABLE_CREDIT: self.data[CONF_SUPPLIER_VARIABLE_CREDIT],
                        CONF_GRID_NOTE: self.data[CONF_GRID_NOTE],
                        CONF_GRID_FIXED_FEE: self.data[CONF_GRID_FIXED_FEE],
                        CONF_GRID_VARIABLE_FEE: self.data[CONF_GRID_VARIABLE_FEE],
                        CONF_GRID_FIXED_CREDIT: self.data[CONF_GRID_FIXED_CREDIT],
                        CONF_GRID_VARIABLE_CREDIT: self.data[CONF_GRID_VARIABLE_CREDIT],
                        CONF_ELECTRICITY_VAT: self.data[CONF_ELECTRICITY_VAT],
                        CONF_GRID_ENERGY_TAX: self.data[CONF_GRID_ENERGY_TAX],
                        CONF_LOW_THRESHOLD: self.data.get(CONF_LOW_THRESHOLD),
                        CONF_HIGH_THRESHOLD: self.data.get(CONF_HIGH_THRESHOLD),
                    },
                )

        return self.async_show_form(
            step_id="thresholds",
            data_schema=vol.Schema({
                vol.Optional(CONF_LOW_THRESHOLD, description={"suffix": unit_of_measurement}): vol.All(vol.Coerce(float), cv.positive_float),
                vol.Optional(CONF_HIGH_THRESHOLD, description={"suffix": unit_of_measurement}): vol.All(vol.Coerce(float), cv.positive_float),
            }),
            errors=errors
        )


class ElectricityPriceLevelOptionFlowHandler(OptionsFlow):
    async def async_step_init(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        unit_of_measurement = ""
        nordpool_sensor_id = self.config_entry.options.get(CONF_NORDPOOL_SENSOR_ID, "")
        if nordpool_sensor_id:
            state = self.hass.states.get(nordpool_sensor_id)
            if state:
                unit_of_measurement = state.attributes.get("unit_of_measurement", "")

        if user_input is not None:
            low_threshold = user_input.get(CONF_LOW_THRESHOLD)
            high_threshold = user_input.get(CONF_HIGH_THRESHOLD)

            if low_threshold is not None and high_threshold is not None and low_threshold > high_threshold:
                errors["base"] = "low_threshold_higher_than_high_threshold"
            else:
                return self.async_create_entry(title="ElectricityPriceLevel", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NORDPOOL_SENSOR_ID,
                                 default=self.config_entry.options.get(CONF_NORDPOOL_SENSOR_ID, "")): selector({"entity": {"domain": "sensor"}}),

                    vol.Optional(
                        CONF_LOW_THRESHOLD,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_LOW_THRESHOLD, None),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_HIGH_THRESHOLD,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_HIGH_THRESHOLD, None),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),

                    vol.Optional(
                        CONF_SUPPLIER_NOTE,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_SUPPLIER_NOTE, None)
                        },
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_SUPPLIER_FIXED_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_SUPPLIER_FIXED_FEE, None),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_SUPPLIER_VARIABLE_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_SUPPLIER_VARIABLE_FEE, None),
                            "suffix": "%"
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_SUPPLIER_FIXED_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_SUPPLIER_FIXED_CREDIT, None),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_SUPPLIER_VARIABLE_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_SUPPLIER_VARIABLE_CREDIT, None),
                            "suffix": "%"
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),

                    vol.Optional(
                        CONF_GRID_NOTE,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_GRID_NOTE, None)
                        },
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_GRID_FIXED_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_GRID_FIXED_FEE, None),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_GRID_VARIABLE_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_GRID_VARIABLE_FEE, None),
                            "suffix": "%"
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_GRID_FIXED_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_GRID_FIXED_CREDIT, None),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_GRID_VARIABLE_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_GRID_VARIABLE_CREDIT, None),
                            "suffix": "%"
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),

                    vol.Optional(
                        CONF_GRID_ENERGY_TAX,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_GRID_ENERGY_TAX, None),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_ELECTRICITY_VAT,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_ELECTRICITY_VAT, None),
                            "suffix": "%"}, ): vol.All(vol.Coerce(float), cv.positive_float),
                }
            ),
            errors=errors,
        )


def validate_float(value):
    try:
        float_value = float(value)
        _LOGGER.debug(f"Validated float value: {float_value}")
        return float_value
    except ValueError:
        _LOGGER.error("Invalid float value")
        raise vol.Invalid("Invalid float value")
