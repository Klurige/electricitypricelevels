from __future__ import annotations

import datetime
import logging
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


def generate_level_pattern(rates):
    pattern = ""
    step_in_minutes = 12
    pattern_length_in_hours = 36
    if rates is None or len(rates) == 0:
        return "U" * (pattern_length_in_hours * 60 // step_in_minutes)
    start_time = rates[0]["start"]
    if isinstance(start_time, str):
        start_time = dt_util.parse_datetime(start_time)

    end_time = start_time + datetime.timedelta(hours=pattern_length_in_hours)

    current_start = start_time
    current_end = current_start + datetime.timedelta(minutes=step_in_minutes,microseconds=-1)

    while current_end <= end_time:
        level = "U"
        # For every minute in time slot (current_start, current_end) find the level for corresponding rate.
        # Summarise the levels: Low -> 1, Medium -> 2, High -> 3 and also count the number of levels. Disregard Unknown.
        # Finally calculate the average level and set level accordingly.
        # The average should be rounded up to the nearest integer and translated back to low, medium or high.
        level_sum = 0
        level_count = 0
        for rate in rates:
            rate_start = rate["start"]
            if isinstance(rate_start, str):
                rate_start = datetime.datetime.fromisoformat(rate_start)
            rate_end = rate["end"]
            if isinstance(rate_end, str):
                rate_end = datetime.datetime.fromisoformat(rate_end)

            if current_start >= rate_start and current_end <= rate_end:
                if rate["level"] == "Low":
                    level_sum += 1
                    level_count += 1
                elif rate["level"] == "Medium":
                    level_sum += 2
                    level_count += 1
                elif rate["level"] == "High":
                    level_sum += 3
                    level_count += 1

        if level_count > 0:
            average_level = level_sum / level_count
            if average_level > 2:
                level = "H"
            elif average_level > 1:
                level = "M"
            else:
                level = "L"

        pattern += level

        current_start += datetime.timedelta(minutes=step_in_minutes)
        current_end += datetime.timedelta(minutes=step_in_minutes)

    _LOGGER.debug("Pattern: %s", pattern)
    return pattern