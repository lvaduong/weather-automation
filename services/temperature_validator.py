from __future__ import annotations

from typing import Optional

from config import settings
from utils.converter import fahrenheit_to_celsius, validate_temperature


def build_temperature_validation(
    fahrenheit: Optional[float],
    displayed_celsius: Optional[float],
) -> tuple[Optional[float], str]:
    calculated_celsius = fahrenheit_to_celsius(fahrenheit)
    if fahrenheit is None:
        return calculated_celsius, "MISSING_TEMPERATURE"
    if displayed_celsius is None:
        return calculated_celsius, "CALCULATED_ONLY"
    if validate_temperature(fahrenheit, displayed_celsius, settings.TEMPERATURE_TOLERANCE):
        return calculated_celsius, "PASSED"
    return calculated_celsius, "FAILED"
