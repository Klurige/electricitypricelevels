# custom_components/electricitypricelevels/sensor/nordpool_coordinator.py
import logging
from datetime import timedelta, date, datetime, time
from typing import Callable, Any, Coroutine

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE

_LOGGER = logging.getLogger(__name__)

class NordpoolDataCoordinator:
    def __init__(self, hass: HomeAssistant, nordpool_config_entry_id: str, data_update_callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]]):
        self.hass = hass
        self.nordpool_config_entry_id = nordpool_config_entry_id
        self.data_update_callback = data_update_callback
        self._task_remover: list[Callable | None] = [None]
        self._collected_for_date: list[date | None] = [None]
        self._current_schedule_state: list[str] = ["INITIALIZING"]
        self._is_running = False

    async def _execute_nordpool_call_logic(self, fetch_date: date) -> tuple[str, dict[str, Any] | None]:
        date_to_fetch_str = fetch_date.isoformat()
        service_data = {
            "config_entry": self.nordpool_config_entry_id,
            "date": date_to_fetch_str,
        }
        _LOGGER.info(
            f"Attempting Nordpool call (State: {self._current_schedule_state[0]}) for date: {date_to_fetch_str}"
        )
        try:
            service_response = await self.hass.services.async_call(
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
                    currency_state_obj = self.hass.states.get(currency_entity_id)

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
                    f"Nordpool config entry '{self.nordpool_config_entry_id}' not ready for date {date_to_fetch_str}. Error: {e}"
                )
                return "ERROR_SERVICE_NOT_READY", None
            _LOGGER.error(f"Service validation error for {date_to_fetch_str}: {e}")
            return "ERROR_OTHER", None
        except Exception as e:
            _LOGGER.error(f"Unexpected error calling Nordpool service for {date_to_fetch_str}: {e}", exc_info=True)
            return "ERROR_OTHER", None


    @callback
    async def _trigger_and_reschedule_nordpool(self, utc_now_from_scheduler: datetime | None = None) -> None:
        if not self._is_running:
            _LOGGER.debug("Coordinator is stopped, not rescheduling.")
            return

        hass_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        hass_now = datetime.now(hass_tz)
        current_date = hass_now.date()

        target_fetch_date: date
        current_operation_type: str

        if self._collected_for_date[0] is None or self._collected_for_date[0] < current_date:
            target_fetch_date = current_date
            current_operation_type = "TODAY"
            _LOGGER.debug(f"Targeting today's data ({target_fetch_date}). Previously collected for: {self._collected_for_date[0]}")
        else:
            target_fetch_date = current_date + timedelta(days=1)
            current_operation_type = "TOMORROW"
            _LOGGER.debug(f"Targeting tomorrow's data ({target_fetch_date}). Today ({current_date}) collected for: {self._collected_for_date[0]}")

        call_status, nordpool_data = await self._execute_nordpool_call_logic(target_fetch_date)
        next_delay_seconds = None
        new_log_state_name = self._current_schedule_state[0]

        if call_status == "SUCCESS_DATA":
            _LOGGER.info(f"Successfully fetched data for {target_fetch_date} (Operation: {current_operation_type}).")
            self._collected_for_date[0] = target_fetch_date

            if nordpool_data:
                await self.data_update_callback(nordpool_data)
            else:
                _LOGGER.error(f"CRITICAL: SUCCESS_DATA status but no data received for {target_fetch_date}. This indicates an issue in _execute_nordpool_call_logic.")

            if current_operation_type == "TODAY":
                today_14h = hass_now.replace(hour=14, minute=0, second=0, microsecond=0)
                if hass_now < today_14h:
                    next_run_time_target = today_14h
                    new_log_state_name = "WAITING_FOR_14H_TO_FETCH_TOMORROW"
                else: # Post 14:00 or exactly at 14:00
                    next_run_time_target = hass_now # Effectively schedule immediately for tomorrow
                    new_log_state_name = "FETCHING_TOMORROW_POST_14H_AFTER_TODAY_SUCCESS"

                next_delay_seconds = (next_run_time_target - hass_now).total_seconds()
                if next_delay_seconds <= 0 and new_log_state_name == "FETCHING_TOMORROW_POST_14H_AFTER_TODAY_SUCCESS":
                    next_delay_seconds = 0.1 # Small delay to ensure next task is scheduled
                elif next_delay_seconds < 0: # Should not happen if logic is correct
                     next_delay_seconds = 0

            else:  # current_operation_type == "TOMORROW"
                # Schedule for next day's 14:00 to check for the day after's prices
                next_day_14h = (hass_now + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
                next_delay_seconds = (next_day_14h - hass_now).total_seconds()
                new_log_state_name = "DAILY_SCHEDULE_FOR_NEXT_TOMORROW_14H"

        elif call_status in ("SUCCESS_NO_DATA", "ERROR_OTHER", "ERROR_SERVICE_NOT_READY", "ERROR_MISSING_CURRENCY", "ERROR_BAD_RESPONSE_STRUCTURE"):
            _LOGGER.warning(f"Nordpool call for {target_fetch_date} (Op: {current_operation_type}) failed or no data/currency/bad_structure. Status: {call_status}.")
            if current_operation_type == "TODAY":
                next_delay_seconds = 10
                new_log_state_name = f"RETRYING_TODAY_10S ({call_status})"
            else:  # current_operation_type == "TOMORROW"
                if self._collected_for_date[0] == current_date and hass_now.time() < time(14, 0): # Failed before 14:00 for tomorrow
                    target_14h_datetime = hass_now.replace(hour=14, minute=0, second=0, microsecond=0)
                    if target_14h_datetime > hass_now:
                        next_delay_seconds = (target_14h_datetime - hass_now).total_seconds()
                        new_log_state_name = f"FAILED_TOMORROW_PRE_14H_WAITING_UNTIL_14H ({call_status})"
                    else: # Exactly at 14:00 or slightly past due to execution time
                        next_delay_seconds = 15 * 60
                        new_log_state_name = f"RETRYING_TOMORROW_15M_AT_14H_TRANSITION ({call_status})"
                else: # Failed after 14:00 for tomorrow, or today's data not yet collected
                    next_delay_seconds = 15 * 60
                    new_log_state_name = f"RETRYING_TOMORROW_15M ({call_status})"
        else: # Unhandled status
            _LOGGER.error(f"Unhandled call_status: {call_status} for {target_fetch_date}. Fallback retry in 5 mins.")
            next_delay_seconds = 5 * 60
            new_log_state_name = f"ERROR_UNHANDLED_STATUS_FALLBACK ({call_status})"

        if self._task_remover[0]:
            try:
                self._task_remover[0]()
                self._task_remover[0] = None
            except Exception:
                _LOGGER.debug("Exception while trying to cancel previous Nordpool task.", exc_info=True)

        if not self._is_running:
            _LOGGER.info("Coordinator stopped before scheduling next call.")
            return

        if next_delay_seconds is not None:
            if next_delay_seconds < 1 and next_delay_seconds != 0.1 : # Allow 0.1 for immediate reschedule
                _LOGGER.warning(
                    f"Calculated next_delay_seconds was {next_delay_seconds:.2f}. Adjusting to 1 second. State: {new_log_state_name}"
                )
                next_delay_seconds = 1

            if next_delay_seconds == 0.1:
                 _LOGGER.info(f"Scheduling next Nordpool call almost immediately (0.1s) (New State: {new_log_state_name}).")
            else:
                _LOGGER.info(f"Scheduling next Nordpool call in {next_delay_seconds:.0f} seconds (New State: {new_log_state_name}).")

            self._current_schedule_state[0] = new_log_state_name
            self._task_remover[0] = async_call_later(
                self.hass,
                timedelta(seconds=next_delay_seconds),
                self._trigger_and_reschedule_nordpool
            )
        else: # Should not happen if all paths set next_delay_seconds
            _LOGGER.error(
                f"Critical: Nordpool scheduling logic failed to determine next_delay_seconds. "
                f"Call status: '{call_status}', Operation: {current_operation_type}, Target: {target_fetch_date}. "
                f"Last state: {self._current_schedule_state[0]}. Fallback scheduling in 5 mins."
            )
            self._current_schedule_state[0] = "ERROR_NO_DELAY_FALLBACK"
            self._task_remover[0] = async_call_later(
                self.hass,
                timedelta(seconds=5*60), # 5 minutes
                self._trigger_and_reschedule_nordpool
            )

    def start(self) -> None:
        if self._is_running:
            _LOGGER.warning("Coordinator already running.")
            return
        self._is_running = True
        self._current_schedule_state[0] = "INITIAL_CALL_SCHEDULED"
        _LOGGER.info(f"Scheduling initial Nordpool call attempt in 1 second. State: {self._current_schedule_state[0]}")

        if self._task_remover[0]: # Ensure no old timer is lingering
            try:
                self._task_remover[0]()
            except Exception:
                _LOGGER.debug("Exception during pre-start cancel of existing task.", exc_info=True)
            self._task_remover[0] = None

        self._task_remover[0] = async_call_later(
            self.hass,
            timedelta(seconds=1),
            self._trigger_and_reschedule_nordpool
        )

    def stop(self) -> None:
        self._is_running = False
        if self._task_remover[0]:
            _LOGGER.info("Stopping Nordpool data coordinator and cancelling scheduled tasks.")
            try:
                self._task_remover[0]()
                self._task_remover[0] = None
            except Exception as e:
                _LOGGER.warning(f"Error while cancelling Nordpool task on stop: {e}", exc_info=True)
        else:
            _LOGGER.info("Nordpool data coordinator stopped. No active task to cancel.")
        self._current_schedule_state[0] = "STOPPED"

