import pytest
from custom_components.electricitypricelevels.sensor.electricitypricelevels import ElectricityPriceLevelSensor

class DummyEntry:
    def __init__(self, low, high):
        self.options = {
            'nordpool_area_id': 'se3',
            'low_threshold': low,
            'high_threshold': high,
            'supplier_fixed_fee': 0,
            'supplier_variable_fee': 0,
            'supplier_fixed_credit': 0,
            'supplier_variable_credit': 0,
            'grid_fixed_fee': 0,
            'grid_variable_fee': 0,
            'grid_fixed_credit': 0,
            'grid_variable_credit': 0,
            'grid_energy_tax': 0,
            'electricity_vat': 0,
        }
        self.entry_id = "dummy_entry_id"

@pytest.fixture
def sensor():
    hass = None
    entry = DummyEntry(low=1.0, high=2.0)
    device_info = {}
    return ElectricityPriceLevelSensor(hass, entry, device_info)

def test_calculate_level_low(sensor):
    assert sensor.calculate_level(0.5) == "Low"

def test_calculate_level_medium(sensor):
    assert sensor.calculate_level(1.5) == "Medium"

def test_calculate_level_high(sensor):
    assert sensor.calculate_level(2.5) == "High"
