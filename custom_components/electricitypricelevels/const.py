"""Constants for the electricitypricelevels integration."""

from __future__ import annotations

import logging

DOMAIN = "electricitypricelevels"
LOGGER = logging.getLogger(__package__)

CONF_NORDPOOL_SENSOR_ID = "nordpool_sensor_id"
CONF_SUPPLIER_BALANCING_FEE = "supplier_balancing_fee"
CONF_SUPPLIER_ENVIRONMENT_FEE = "supplier_environment_fee"
CONF_SUPPLIER_CERTIFICATE_FEE = "supplier_certificate_fee"
CONF_SUPPLIER_FIXED_FEE = "supplier_fixed_fee"
CONF_SUPPLIER_CREDIT = "supplier_credit"
CONF_GRID_FIXED_FEE = "grid_fixed_fee"
CONF_GRID_VARIABLE_FEE = "grid_variable_fee"
CONF_GRID_ENERGY_TAX = "grid_energy_tax"
CONF_ELECTRICITY_VAT = "electricity_vat"
CONF_GRID_FIXED_CREDIT = "grid_fixed_credit"
CONF_GRID_VARIABLE_CREDIT = "grid_variable_credit"
CONF_LEVEL_LOW = "level_low"
CONF_LEVEL_HIGH = "level_high"
