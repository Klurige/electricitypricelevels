"""Support for the ElectricityPriceLevel sensor service."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.translation import async_get_translations

from .electricity_price_level_sensor import ElectricityPriceLevelSensor
from .time_sensor import TimeSensor
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
        configuration_url="https://forecast.solar",
    )

    entities = [
        ElectricityPriceLevelSensor(hass, entry, device_info),
        TimeSensor(hass, entry, device_info)
    ]
    async_add_entities(entities)


