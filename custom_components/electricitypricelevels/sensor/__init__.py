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
from homeassistant.helpers.event import (
    async_call_later,
)
from homeassistant.util import dt as dt_util
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE


# Import your sensor classes
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
        configuration_url=None,
    )

    level_sensor = ElectricityPriceLevelSensor(hass, entry, device_info)
    time_sensor = TimeSensor(hass, entry, device_info, level_sensor)

    async_add_entities([level_sensor, time_sensor], True)

    nordpool_config_entry_id_to_use = None
    for cfg_entry in hass.config_entries.async_entries("nordpool"):
        nordpool_config_entry_id_to_use = cfg_entry.entry_id
        _LOGGER.info(f"Using Nordpool config entry: {nordpool_config_entry_id_to_use} (Title: {cfg_entry.title})")
        break

    if nordpool_config_entry_id_to_use is None:
        _LOGGER.error("No Nordpool config entry found! Cannot schedule Nordpool calls.")
        return

    nordpool_task_remover: list[Callable | None] = [None]
    collected_for_date: list[date | None] = [None]
    current_schedule_state: list[str] = ["INITIALIZING"]

    async def _execute_nordpool_call_logic(fetch_date: date) -> tuple[str, dict[str, Any] | None]:
        date_to_fetch_str = fetch_date.isoformat()
        service_data = {
            "config_entry": nordpool_config_entry_id_to_use,
            "date": date_to_fetch_str,
        }
        _LOGGER.info(
            f"Attempting Nordpool call (State: {current_schedule_state[0]}) for date: {date_to_fetch_str}"
        )
        try:
            service_response = await hass.services.async_call(
                "nordpool",
                "get_prices_for_date",
                service_data,
                blocking=True,
                return_response=True
            )
            _LOGGER.debug(f"Nordpool service call for {date_to_fetch_str} returned: {service_response}")

            if service_response and isinstance(service_response, dict):
                if len(service_response) == 1:
                    area_id = next(iter(service_response))
                    price_data_list = service_response[area_id]

                    if not isinstance(price_data_list, list):
                        _LOGGER.error(
                            f"Nordpool service response for area '{area_id}' is not a list as expected: {type(price_data_list)}"
                        )
                        return "ERROR_BAD_RESPONSE_STRUCTURE", None

                    _LOGGER.info(f"Extracted area '{area_id}' and price data list from service response.")

                    determined_currency = None
                    currency_entity_id = f"sensor.nord_pool_{area_id.lower()}_currency"
                    currency_state_obj = hass.states.get(currency_entity_id)

                    if currency_state_obj and currency_state_obj.state not in (None, STATE_UNKNOWN, STATE_UNAVAILABLE):
                        determined_currency = currency_state_obj.state
                        _LOGGER.info(f"Fetched currency '{determined_currency}' from entity '{currency_entity_id}'.")
                    else:
                        _LOGGER.warning(
                            f"Currency entity '{currency_entity_id}' not found or has invalid state "
                            f"({currency_state_obj.state if currency_state_obj else 'None'}). Currency will be None."
                        )

                    if not determined_currency:
                        _LOGGER.error(
                            "Currency could not be determined. "
                            "The 'currency' field in the data payload will be None. This might cause issues in the sensor."
                        )
                        # Consider if this should be a hard error:
                        # return "ERROR_MISSING_CURRENCY", None

                    final_payload = {
                        "currency": determined_currency,
                        "unit_of_measurement": "MWh",
                        "raw": price_data_list
                    }
                    return "SUCCESS_DATA", final_payload
                else:
                    _LOGGER.error(
                        f"Nordpool service response for {date_to_fetch_str} has unexpected structure "
                        f"(expected 1 area key, got {len(service_response)}): {service_response}"
                    )
                    return "ERROR_BAD_RESPONSE_STRUCTURE", None
            else:
                _LOGGER.warning(f"Nordpool call for {date_to_fetch_str} successful but returned no data or unexpected response: {service_response}")
                return "SUCCESS_NO_DATA", None
        except ServiceValidationError as e:
            if "entry_not_loaded" in str(e).lower() or "not loaded" in str(e).lower() or "did not set up" in str(e).lower():
                _LOGGER.warning(
                    f"Nordpool config entry '{nordpool_config_entry_id_to_use}' not ready for date {date_to_fetch_str}. Error: {e}"
                )
                return "ERROR_SERVICE_NOT_READY", None
            _LOGGER.error(f"Service validation error for {date_to_fetch_str}: {e}")
            return "ERROR_OTHER", None
        except Exception as e:
            _LOGGER.error(f"Unexpected error calling Nordpool service for {date_to_fetch_str}: {e}", exc_info=True)
            return "ERROR_OTHER", None

    @callback
    async def _trigger_and_reschedule_nordpool(utc_now_from_scheduler: datetime | None = None) -> None:
        hass_tz = dt_util.get_time_zone(hass.config.time_zone)
        hass_now = datetime.now(hass_tz)
        current_date = hass_now.date()

        target_fetch_date: date
        current_operation_type: str

        if collected_for_date[0] is None or collected_for_date[0] < current_date:
            target_fetch_date = current_date
            current_operation_type = "TODAY"
            _LOGGER.debug(f"Targeting today's data ({target_fetch_date}). Previously collected for: {collected_for_date[0]}")
        else:
            target_fetch_date = current_date + timedelta(days=1)
            current_operation_type = "TOMORROW"
            _LOGGER.debug(f"Targeting tomorrow's data ({target_fetch_date}). Today ({current_date}) collected for: {collected_for_date[0]}")

        call_status, nordpool_data = await _execute_nordpool_call_logic(target_fetch_date)
        next_delay_seconds = None
        new_log_state_name = current_schedule_state[0]

        if call_status == "SUCCESS_DATA":
            _LOGGER.info(f"Successfully fetched data for {target_fetch_date} (Operation: {current_operation_type}).")
            collected_for_date[0] = target_fetch_date

            if nordpool_data:
                await level_sensor.async_update_data(nordpool_data)
            else:
                _LOGGER.error(f"CRITICAL: SUCCESS_DATA status but no data received for {target_fetch_date}. This indicates an issue in _execute_nordpool_call_logic.")


            if current_operation_type == "TODAY":
                today_14h = hass_now.replace(hour=14, minute=0, second=0, microsecond=0)
                if hass_now < today_14h:
                    next_run_time_target = today_14h
                    new_log_state_name = "WAITING_FOR_14H_TO_FETCH_TOMORROW"
                else:
                    next_run_time_target = hass_now
                    new_log_state_name = "FETCHING_TOMORROW_POST_14H_AFTER_TODAY_SUCCESS"
                next_delay_seconds = max((next_run_time_target - hass_now).total_seconds(), 0)
            else:  # current_operation_type == "TOMORROW"
                next_day_14h = (hass_now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
                next_delay_seconds = (next_day_14h - hass_now).total_seconds()
                new_log_state_name = "DAILY_SCHEDULE_FOR_NEXT_TOMORROW_14H"

        elif call_status in ("SUCCESS_NO_DATA", "ERROR_OTHER", "ERROR_SERVICE_NOT_READY", "ERROR_MISSING_CURRENCY", "ERROR_BAD_RESPONSE_STRUCTURE"):
            _LOGGER.warning(f"Nordpool call for {target_fetch_date} (Op: {current_operation_type}) failed or no data/currency/bad_structure. Status: {call_status}.")
            if current_operation_type == "TODAY":
                next_delay_seconds = 10
                new_log_state_name = f"RETRYING_TODAY_10S ({call_status})"
            else:  # current_operation_type == "TOMORROW"
                if collected_for_date[0] == current_date and hass_now.time() < time(14, 0):
                    target_14h_datetime = hass_now.replace(hour=14, minute=0, second=0, microsecond=0)
                    if target_14h_datetime > hass_now:
                        next_delay_seconds = (target_14h_datetime - hass_now).total_seconds()
                        new_log_state_name = f"FAILED_TOMORROW_PRE_14H_WAITING_UNTIL_14H ({call_status})"
                    else:
                        next_delay_seconds = 15 * 60
                        new_log_state_name = f"RETRYING_TOMORROW_15M_AT_14H_TRANSITION ({call_status})"
                else:
                    next_delay_seconds = 15 * 60
                    new_log_state_name = f"RETRYING_TOMORROW_15M ({call_status})"
        else:
            _LOGGER.error(f"Unhandled call_status: {call_status} for {target_fetch_date}. Fallback retry in 5 mins.")
            next_delay_seconds = 5 * 60
            new_log_state_name = f"ERROR_UNHANDLED_STATUS_FALLBACK ({call_status})"


        if nordpool_task_remover[0]:
            try:
                nordpool_task_remover[0]()
                nordpool_task_remover[0] = None
            except Exception:
                _LOGGER.debug("Exception while trying to cancel previous Nordpool task.", exc_info=True)

        if next_delay_seconds is not None:
            if next_delay_seconds < 1:
                _LOGGER.warning(
                    f"Calculated next_delay_seconds was {next_delay_seconds:.2f}. Adjusting to 1 second. State: {new_log_state_name}"
                )
                next_delay_seconds = 1

            _LOGGER.info(f"Scheduling next Nordpool call in {next_delay_seconds:.0f} seconds (New State: {new_log_state_name}).")
            current_schedule_state[0] = new_log_state_name
            nordpool_task_remover[0] = async_call_later(
                hass,
                timedelta(seconds=next_delay_seconds),
                _trigger_and_reschedule_nordpool
            )
        else:
            _LOGGER.error(
                f"Critical: Nordpool scheduling logic failed to determine next_delay_seconds. "
                f"Call status: '{call_status}', Operation: {current_operation_type}, Target: {target_fetch_date}. "
                f"Last state: {current_schedule_state[0]}. Fallback scheduling in 5 mins."
            )
            current_schedule_state[0] = "ERROR_NO_DELAY_FALLBACK"
            nordpool_task_remover[0] = async_call_later(
                hass,
                timedelta(seconds=5*60),
                _trigger_and_reschedule_nordpool
            )

    current_schedule_state[0] = "INITIAL_CALL_SCHEDULED"
    _LOGGER.info(f"Scheduling initial Nordpool call attempt in 1 second. State: {current_schedule_state[0]}")
    nordpool_task_remover[0] = async_call_later(
        hass,
        timedelta(seconds=1),
        _trigger_and_reschedule_nordpool
    )

    @callback
    def _async_cleanup_nordpool_task(_event=None) -> None:
        if nordpool_task_remover[0]:
            _LOGGER.debug("Cleaning up Nordpool update task on unload.")
            try:
                nordpool_task_remover[0]()
                nordpool_task_remover[0] = None
            except Exception as e:
                _LOGGER.warning(f"Error while cleaning up Nordpool task listener: {e}", exc_info=True)

    entry.async_on_unload(_async_cleanup_nordpool_task)