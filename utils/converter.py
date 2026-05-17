from typing import Optional


def fahrenheit_to_celsius(fahrenheit: Optional[float]) -> Optional[float]:
    if fahrenheit is None:
        return None
    return round((fahrenheit - 32) * 5 / 9, 1)


def celsius_to_fahrenheit(celsius: Optional[float]) -> Optional[float]:
    if celsius is None:
        return None
    return round((celsius * 9 / 5) + 32, 1)


def validate_temperature(
    fahrenheit: Optional[float],
    displayed_celsius: Optional[float],
    tolerance: float = 1.0,
) -> bool:
    if fahrenheit is None or displayed_celsius is None:
        return False
    calculated_celsius = fahrenheit_to_celsius(fahrenheit)
    return abs(calculated_celsius - displayed_celsius) <= tolerance
