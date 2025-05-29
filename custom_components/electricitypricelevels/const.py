"""Constants for the electricitypricelevels integration."""

from __future__ import annotations

import logging

DOMAIN = "electricitypricelevels"
LOGGER = logging.getLogger(__package__)

CONF_NORDPOOL_AREA_ID = "nordpool_area_id"
CONF_LOW_THRESHOLD = "low_threshold"
CONF_HIGH_THRESHOLD = "high_threshold"
CONF_SUPPLIER_NOTE = "supplier_note"
CONF_SUPPLIER_FIXED_FEE = "supplier_fixed_fee"
CONF_SUPPLIER_VARIABLE_FEE = "supplier_variable_fee"
CONF_SUPPLIER_FIXED_CREDIT = "supplier_fixed_credit"
CONF_SUPPLIER_VARIABLE_CREDIT = "supplier_variable_credit"
CONF_GRID_NOTE = "grid_note"
CONF_GRID_FIXED_FEE = "grid_fixed_fee"
CONF_GRID_VARIABLE_FEE = "grid_variable_fee"
CONF_GRID_FIXED_CREDIT = "grid_fixed_credit"
CONF_GRID_VARIABLE_CREDIT = "grid_variable_credit"
CONF_GRID_ENERGY_TAX = "grid_energy_tax"
CONF_ELECTRICITY_VAT = "electricity_vat"

