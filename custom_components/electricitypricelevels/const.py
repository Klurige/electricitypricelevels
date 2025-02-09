"""Constants for the electricitypricelevels integration."""

from __future__ import annotations

import logging

DOMAIN = "electricitypricelevels"
LOGGER = logging.getLogger(__package__)

CONF_NORDPOOL_SENSOR_ID = "nordpool_sensor_id"
CONF_LEVEL_LOW = "level_low"
CONF_LEVEL_HIGH = "level_high"
CONF_SUPPLIER_FIXED_FEE = "supplier_fixed_fee"
CONF_SUPPLIER_FIXED_FEE_COMMENT = "supplier_fixed_fee_comment"
CONF_SUPPLIER_VARIABLE_FEE_COMMENT = "supplier_variable_fee_comment"
CONF_SUPPLIER_VARIABLE_FEE = "supplier_variable_fee"
CONF_SUPPLIER_USAGE_CREDIT_COMMENT = "supplier_usage_credit_comment"
CONF_SUPPLIER_USAGE_CREDIT = "supplier_usage_credit"
CONF_SUPPLIER_SPOTPRICE_CREDIT_COMMENT = "supplier_spotprice_credit_comment"
CONF_SUPPLIER_SPOTPRICE_CREDIT = "supplier_spotprice_credit"
CONF_GRID_FIXED_FEE_COMMENT = "grid_fixed_fee_comment"
CONF_GRID_FIXED_FEE = "grid_fixed_fee"
CONF_GRID_VARIABLE_FEE_COMMENT = "grid_variable_fee_comment"
CONF_GRID_VARIABLE_FEE = "grid_variable_fee"
CONF_GRID_USAGE_CREDIT_COMMENT = "grid_usage_credit_comment"
CONF_GRID_USAGE_CREDIT = "grid_usage_credit"
CONF_GRID_SPOTPRICE_CREDIT_COMMENT = "grid_spotprice_credit_comment"
CONF_GRID_SPOTPRICE_CREDIT = "grid_spotprice_credit"
CONF_GRID_ENERGY_TAX = "grid_energy_tax"
CONF_ELECTRICITY_VAT = "electricity_vat"

