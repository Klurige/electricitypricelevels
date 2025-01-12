from __future__ import annotations
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription

@dataclass(frozen=True)
class ElectricityPriceLevelSensorEntityDescription(SensorEntityDescription):
    """Describes an Electricity Price Level Sensor."""
