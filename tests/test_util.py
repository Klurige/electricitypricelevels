"""Tests for the util module."""
import datetime
from unittest.mock import patch
import pytest
from homeassistant.util import dt as dt_util

from custom_components.electricitypricelevels.util import generate_level_pattern


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent test execution."""
    base_dt = datetime.datetime(2025, 8, 9, 10, 0, 0, tzinfo=datetime.timezone.utc)

    def mock_parse_datetime(date_str):
        return datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))

    with patch("homeassistant.util.dt.parse_datetime", side_effect=mock_parse_datetime):
        yield base_dt


def test_generate_level_pattern_empty_rates():
    """Test pattern generation with empty rates."""
    # With None rates
    pattern = generate_level_pattern(None)
    expected_length = 36 * 60 // 12  # 36 hours in 12-minute increments
    assert pattern == "U" * expected_length
    assert len(pattern) == expected_length

    # With empty rates list
    pattern = generate_level_pattern([])
    assert pattern == "U" * expected_length
    assert len(pattern) == expected_length


def test_generate_level_pattern_single_level():
    """Test pattern generation with single level."""
    # Create rates for 36 hours with single level
    start_time = datetime.datetime(2025, 8, 9, 10, 0, 0, tzinfo=datetime.timezone.utc)
    end_time = start_time + datetime.timedelta(hours=36)

    # Test with low level
    rates_low = [{
        "start": start_time,
        "end": end_time,
        "level": "Low"
    }]
    pattern_low = generate_level_pattern(rates_low)
    expected_length = 36 * 60 // 12  # 36 hours in 12-minute increments
    assert pattern_low == "L" * expected_length
    assert len(pattern_low) == expected_length

    # Test with medium level
    rates_medium = [{
        "start": start_time,
        "end": end_time,
        "level": "Medium"
    }]
    pattern_medium = generate_level_pattern(rates_medium)
    assert pattern_medium == "M" * expected_length

    # Test with high level
    rates_high = [{
        "start": start_time,
        "end": end_time,
        "level": "High"
    }]
    pattern_high = generate_level_pattern(rates_high)
    assert pattern_high == "H" * expected_length


def test_generate_level_pattern_mixed_levels():
    """Test pattern generation with mixed levels."""
    start_time = datetime.datetime(2025, 8, 9, 10, 0, 0, tzinfo=datetime.timezone.utc)

    rates = [
        # First 4 hours: Low
        {
            "start": start_time,
            "end": start_time + datetime.timedelta(hours=4),
            "level": "Low"
        },
        # Next 4 hours: Medium
        {
            "start": start_time + datetime.timedelta(hours=4),
            "end": start_time + datetime.timedelta(hours=8),
            "level": "Medium"
        },
        # Next 4 hours: High
        {
            "start": start_time + datetime.timedelta(hours=8),
            "end": start_time + datetime.timedelta(hours=12),
            "level": "High"
        },
        # Rest: Unknown (not covered)
    ]

    pattern = generate_level_pattern(rates)

    # Expected pattern:
    # 4 hours of Low = 4 * 60 / 12 = 20 L's
    # 4 hours of Medium = 4 * 60 / 12 = 20 M's
    # 4 hours of High = 4 * 60 / 12 = 20 H's
    # Rest (24 hours) = 24 * 60 / 12 = 120 U's
    expected_pattern = "L" * 20 + "M" * 20 + "H" * 20 + "U" * 120

    assert pattern == expected_pattern
    assert len(pattern) == 36 * 60 // 12


def test_generate_level_pattern_with_string_dates():
    """Test pattern generation with string dates instead of datetime objects."""
    start_time = "2025-08-09T10:00:00Z"
    end_time = "2025-08-09T14:00:00Z"  # 4 hours later

    rates = [{
        "start": start_time,
        "end": end_time,
        "level": "Low"
    }]

    pattern = generate_level_pattern(rates)

    # First 4 hours should be Low, rest should be Unknown
    expected_pattern = "L" * 20 + "U" * 160
    assert pattern == expected_pattern


def test_generate_level_pattern_overlapping_rates():
    """Test pattern generation with overlapping rates."""
    start_time = datetime.datetime(2025, 8, 9, 10, 0, 0, tzinfo=datetime.timezone.utc)

    rates = [
        # First 6 hours: Low
        {
            "start": start_time,
            "end": start_time + datetime.timedelta(hours=6),
            "level": "Low"
        },
        # 2-8 hours: Medium (overlaps with first)
        {
            "start": start_time + datetime.timedelta(hours=2),
            "end": start_time + datetime.timedelta(hours=8),
            "level": "Medium"
        },
        # 4-10 hours: High (overlaps with both)
        {
            "start": start_time + datetime.timedelta(hours=4),
            "end": start_time + datetime.timedelta(hours=10),
            "level": "High"
        }
    ]

    pattern = generate_level_pattern(rates)

    # Expected:
    # 0-2h: Pure Low = 10 L's
    # 2-4h: Low+Medium average = 10 M's (as (1+2)/2 = 1.5 rounds to M)
    # 4-6h: Low+Medium+High average = 10 H's (as (1+2+3)/3 = 2 rounds to M)
    # 6-8h: Medium+High average = 10 H's (as (2+3)/2 = 2.5 rounds to H)
    # 8-10h: Pure High = 10 H's
    # 10-46h: Unknown = 180 U's
    expected_pattern = "L" * 10 + "M" * 10 + "M" * 10 + "H" * 10 + "H" * 10 + "U" * 130

    assert pattern == expected_pattern


def test_generate_level_pattern_edge_cases():
    """Test edge cases for pattern generation."""
    start_time = datetime.datetime(2025, 8, 9, 10, 0, 0, tzinfo=datetime.timezone.utc)

    # Case 1: Level exactly between boundaries (average = 1.0 -> L, average = 2.0 -> M)
    rates = [
        {
            "start": start_time,
            "end": start_time + datetime.timedelta(hours=4),
            "level": "Low"  # 1
        },
        {
            "start": start_time,
            "end": start_time + datetime.timedelta(hours=4),
            "level": "Medium"  # 2
        }
    ]
    pattern = generate_level_pattern(rates)
    # Average = 1.5 -> M
    assert pattern.startswith("M" * 20)

    # Case 2: Unknown levels mixed with known levels
    rates = [
        {
            "start": start_time,
            "end": start_time + datetime.timedelta(hours=4),
            "level": "Low"  # 1
        },
        {
            "start": start_time,
            "end": start_time + datetime.timedelta(hours=4),
            "level": "Unknown"  # Should be ignored
        }
    ]
    pattern = generate_level_pattern(rates)
    # Only count the Low level
    assert pattern.startswith("L" * 20)
