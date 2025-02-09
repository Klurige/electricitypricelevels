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
    CONF_LEVEL_LOW,
    CONF_LEVEL_HIGH,
    CONF_SUPPLIER_FIXED_FEE_COMMENT,
    CONF_SUPPLIER_FIXED_FEE,
    CONF_SUPPLIER_VARIABLE_FEE_COMMENT,
    CONF_SUPPLIER_VARIABLE_FEE,
    CONF_SUPPLIER_USAGE_CREDIT_COMMENT,
    CONF_SUPPLIER_USAGE_CREDIT,
    CONF_SUPPLIER_SPOTPRICE_CREDIT_COMMENT,
    CONF_SUPPLIER_SPOTPRICE_CREDIT,
    CONF_GRID_FIXED_FEE_COMMENT,
    CONF_GRID_FIXED_FEE,
    CONF_GRID_VARIABLE_FEE_COMMENT,
    CONF_GRID_VARIABLE_FEE,
    CONF_GRID_USAGE_CREDIT_COMMENT,
    CONF_GRID_USAGE_CREDIT,
    CONF_GRID_SPOTPRICE_CREDIT_COMMENT,
    CONF_GRID_SPOTPRICE_CREDIT,
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
            return await self.async_step_supplier_fixed_fee()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NORDPOOL_SENSOR_ID): selector({"entity": {"domain": "sensor"}}),
            }),
            errors=errors
        )

    async def async_step_supplier_fixed_fee(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        unit_of_measurement = self.data.get("unit_of_measurement", "")
        if user_input is not None:
            self.data[CONF_SUPPLIER_FIXED_FEE] = user_input.get(CONF_SUPPLIER_FIXED_FEE, None)
            return await self.async_step_electricity_vat()

        return self.async_show_form(
            step_id="supplier_fixed_fee",
            data_schema=vol.Schema({
                vol.Optional(CONF_SUPPLIER_FIXED_FEE, description={"suffix": unit_of_measurement}): vol.All(vol.Coerce(float), cv.positive_float),
            }),
            errors=errors
        )

    async def async_step_electricity_vat(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            self.data[CONF_ELECTRICITY_VAT] = user_input.get(CONF_ELECTRICITY_VAT, None)
            return await self.async_step_thresholds()

        return self.async_show_form(
            step_id="electricity_vat",
            data_schema=vol.Schema({
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
            level_low = user_input.get(CONF_LEVEL_LOW)
            level_high = user_input.get(CONF_LEVEL_HIGH)

            if level_low is not None and level_high is not None and level_low > level_high:
                errors["base"] = "level_low_higher_than_level_high"
            else:
                self.data[CONF_LEVEL_LOW] = level_low
                self.data[CONF_LEVEL_HIGH] = level_high
                return self.async_create_entry(
                    title="ElectricityPriceLevel",
                    data=self.data,
                    options={
                        CONF_NORDPOOL_SENSOR_ID: self.data[CONF_NORDPOOL_SENSOR_ID],
                        CONF_SUPPLIER_FIXED_FEE: self.data[CONF_SUPPLIER_FIXED_FEE],
                        CONF_ELECTRICITY_VAT: self.data[CONF_ELECTRICITY_VAT],
                        CONF_LEVEL_LOW: self.data.get(CONF_LEVEL_LOW),
                        CONF_LEVEL_HIGH: self.data.get(CONF_LEVEL_HIGH),
                    },
                )

        return self.async_show_form(
            step_id="thresholds",
            data_schema=vol.Schema({
                vol.Optional(CONF_LEVEL_LOW, description={"suffix": unit_of_measurement}): vol.All(vol.Coerce(float), cv.positive_float),
                vol.Optional(CONF_LEVEL_HIGH, description={"suffix": unit_of_measurement}): vol.All(vol.Coerce(float), cv.positive_float),
            }),
            errors=errors
        )


class ElectricityPriceLevelOptionFlowHandler(OptionsFlow):
    """Handle options."""

    async def async_step_init(
            self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors = {}
        unit_of_measurement = ""
        currency = ""
        _price_divisor = 1
        nordpool_sensor_id = self.config_entry.options.get(CONF_NORDPOOL_SENSOR_ID, "")
        if nordpool_sensor_id:
            state = self.hass.states.get(nordpool_sensor_id)
            if state:
                unit_of_measurement = state.attributes.get("unit_of_measurement", "")
                currency = state.attributes.get("currency", "")
                prices_in_cents = state.attributes.get("prices_in_cents", False)
                if prices_in_cents:
                    _LOGGER.debug("Prices in cents")
                    _price_divisor = 1
                else:
                    _LOGGER.debug("Prices in euros")
                    _price_divisor = 100

        if user_input is not None:
            return self.async_create_entry(title="ElectricityPriceLevel", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NORDPOOL_SENSOR_ID,
                                 default=self.config_entry.options.get(CONF_NORDPOOL_SENSOR_ID, "")): selector(
                        {"entity": {"domain": "sensor"}}),
                    vol.Optional(
                        CONF_LEVEL_LOW,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_LEVEL_LOW, None
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_LEVEL_HIGH,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_LEVEL_HIGH, None
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),

                    vol.Optional(
                        CONF_SUPPLIER_FIXED_FEE_COMMENT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_FIXED_FEE_COMMENT, ""
                            )
                        },
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_SUPPLIER_FIXED_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_FIXED_FEE, 0.0 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_SUPPLIER_VARIABLE_FEE_COMMENT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_VARIABLE_FEE_COMMENT, ""
                            )
                        },
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_SUPPLIER_VARIABLE_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_VARIABLE_FEE, 0.0 / _price_divisor
                            ),
                            "suffix": "%"
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),

                    vol.Optional(
                        CONF_SUPPLIER_USAGE_CREDIT_COMMENT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_USAGE_CREDIT_COMMENT, ""
                            )
                        },
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_SUPPLIER_USAGE_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_USAGE_CREDIT, 0.0 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_SUPPLIER_SPOTPRICE_CREDIT_COMMENT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_SPOTPRICE_CREDIT_COMMENT, ""
                            )
                        },
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_SUPPLIER_SPOTPRICE_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_SPOTPRICE_CREDIT, 0.0 / _price_divisor
                            ),
                            "suffix": "%"
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),

                    vol.Optional(
                        CONF_GRID_FIXED_FEE_COMMENT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_FIXED_FEE_COMMENT, ""
                            )
                        },
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_GRID_FIXED_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_FIXED_FEE, 0.0 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_GRID_VARIABLE_FEE_COMMENT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_VARIABLE_FEE_COMMENT, ""
                            )
                        },
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_GRID_VARIABLE_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_VARIABLE_FEE, 0.0 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),

                    vol.Optional(
                        CONF_GRID_USAGE_CREDIT_COMMENT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_USAGE_CREDIT_COMMENT, ""
                            )
                        },
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_GRID_USAGE_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_USAGE_CREDIT, 0.0 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_GRID_SPOTPRICE_CREDIT_COMMENT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_SPOTPRICE_CREDIT_COMMENT, ""
                            )
                        },
                    ): vol.All(vol.Coerce(str)),
                    vol.Optional(
                        CONF_GRID_SPOTPRICE_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_SPOTPRICE_CREDIT, 0.0 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),

                    vol.Optional(
                        CONF_GRID_ENERGY_TAX,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_GRID_ENERGY_TAX,
                                                                             43.90 / _price_divisor),
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
