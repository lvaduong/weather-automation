from services.temperature_validator import build_temperature_validation
from utils.converter import fahrenheit_to_celsius, validate_temperature


def test_fahrenheit_to_celsius_rounds_to_one_decimal():
    assert fahrenheit_to_celsius(88) == 31.1


def test_validate_temperature_with_tolerance():
    assert validate_temperature(88, 31, tolerance=1.0)
    assert not validate_temperature(88, 28, tolerance=1.0)


def test_build_temperature_validation_marks_calculated_only_when_celsius_missing():
    calculated, status = build_temperature_validation(77, None)

    assert calculated == 25.0
    assert status == "CALCULATED_ONLY"


def test_build_temperature_validation_marks_missing_temperature_when_fahrenheit_missing():
    calculated, status = build_temperature_validation(None, 25)

    assert calculated is None
    assert status == "MISSING_TEMPERATURE"


def test_build_temperature_validation_marks_failed_when_temperatures_disagree():
    calculated, status = build_temperature_validation(88, 20)

    assert calculated == 31.1
    assert status == "FAILED"
