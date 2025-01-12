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
    CONF_SUPPLIER_BALANCING_FEE,
    CONF_SUPPLIER_ENVIRONMENT_FEE,
    CONF_SUPPLIER_CERTIFICATE_FEE,
    CONF_SUPPLIER_FIXED_FEE,
    CONF_SUPPLIER_CREDIT,
    CONF_GRID_FIXED_FEE,
    CONF_GRID_VARIABLE_FEE,
    CONF_GRID_ENERGY_TAX,
    CONF_ELECTRICITY_VAT,
    CONF_GRID_FIXED_CREDIT,
    CONF_GRID_VARIABLE_CREDIT,
    CONF_LEVEL_LOW,
    CONF_LEVEL_HIGH,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ElectricityPriceLevelFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ElectricityPriceLevel."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ElectricityPriceLevelOptionFlowHandler:
        """Get the options flow for this handler."""
        return ElectricityPriceLevelOptionFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="ElectricityPriceLevel",
                data=user_input,
                options={
                    CONF_NORDPOOL_SENSOR_ID: user_input[CONF_NORDPOOL_SENSOR_ID],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
            vol.Required(CONF_NORDPOOL_SENSOR_ID): selector({"entity": {"domain": "sensor"}}),
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
        _price_divisor = 1
        nordpool_sensor_id = self.config_entry.options.get(CONF_NORDPOOL_SENSOR_ID, "")
        if nordpool_sensor_id:
            state = self.hass.states.get(nordpool_sensor_id)
            if state:
                unit_of_measurement = state.attributes.get("unit_of_measurement", "")
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
                    vol.Required(
                        CONF_LEVEL_LOW,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_LEVEL_LOW, 200 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Required(
                        CONF_LEVEL_HIGH,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_LEVEL_HIGH, 300 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_SUPPLIER_BALANCING_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_BALANCING_FEE, 2.92 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_SUPPLIER_ENVIRONMENT_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_ENVIRONMENT_FEE, 3.00 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_SUPPLIER_CERTIFICATE_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_CERTIFICATE_FEE, 0.51 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_SUPPLIER_FIXED_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_FIXED_FEE, 3.63 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_SUPPLIER_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SUPPLIER_CREDIT, 2.00 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_GRID_FIXED_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_FIXED_FEE, 7.33 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_GRID_VARIABLE_FEE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_VARIABLE_FEE, 5.11
                            ),
                            "suffix": "%"
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_GRID_ENERGY_TAX,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_ENERGY_TAX, 43.90 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_ELECTRICITY_VAT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_ELECTRICITY_VAT, 25.00
                            ),
                            "suffix": "%"
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_GRID_FIXED_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_FIXED_CREDIT, 4.53 / _price_divisor
                            ),
                            "suffix": unit_of_measurement
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
                    vol.Optional(
                        CONF_GRID_VARIABLE_CREDIT,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GRID_VARIABLE_CREDIT, 5.00
                            ),
                            "suffix": "%"
                        },
                    ): vol.All(vol.Coerce(float), cv.positive_float),
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
