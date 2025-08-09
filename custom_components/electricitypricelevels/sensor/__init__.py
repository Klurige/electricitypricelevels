"""Support for the ElectricityPriceLevel sensor service."""

from __future__ import annotations

import logging
from datetime import timedelta, date, datetime, time
from typing import Callable, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.translation import async_get_translations

# Import your sensor classes
from .electricitypricelevels import ElectricityPriceLevelSensor
from .levels_array import LevelsSensor
from .nordpool_coordinator import NordpoolDataCoordinator

from ..const import DOMAIN
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    user_language = hass.config.language
    translations = await async_get_translations(hass, user_language, "device_info", [DOMAIN])
    device_name = translations.get(f"component.{DOMAIN}.device_info.device_name", "Untranslated device name")
    manufacturer = translations.get(f"component.{DOMAIN}.device_info.manufacturer", "Untranslated manufacturer")
    model = translations.get(f"component.{DOMAIN}.device_info.model", "Untranslated model")

    device_info = DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry.entry_id)},
        name=device_name,
        manufacturer=manufacturer,
        model=model,
        sw_version="1.0",
        configuration_url=None,
    )

    level_sensor = ElectricityPriceLevelSensor(hass, entry, device_info)
    levels_sensor = LevelsSensor(hass, entry, device_info)

    async_add_entities([level_sensor, levels_sensor], True)

    nordpool_config_entry_id_to_use = None
    for cfg_entry in hass.config_entries.async_entries("nordpool"):
        nordpool_config_entry_id_to_use = cfg_entry.entry_id
        _LOGGER.info(f"Using Nordpool config entry: {nordpool_config_entry_id_to_use} (Title: {cfg_entry.title})")
        break

    if nordpool_config_entry_id_to_use is None:
        _LOGGER.error("No Nordpool config entry found! Cannot schedule Nordpool calls.")
        return

    # Create and start the coordinator
    coordinator = NordpoolDataCoordinator(hass, nordpool_config_entry_id_to_use, level_sensor.async_update_data)
    coordinator.start()

    @callback
    def _async_cleanup_nordpool_task(_event=None) -> None:
        _LOGGER.debug("Cleaning up Nordpool coordinator on unload.")
        coordinator.stop()

    entry.async_on_unload(_async_cleanup_nordpool_task)
