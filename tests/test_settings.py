import pytest

from config import settings
from config.settings import parse_bool, parse_forecast_days, parse_positive_int


def test_parse_forecast_days_accepts_ten_day_default():
    assert parse_forecast_days("10") == 10


def test_parse_forecast_days_defaults_to_ten_when_not_provided():
    assert parse_forecast_days(None) == 10
    assert parse_forecast_days("") == 10
    assert parse_forecast_days("   ") == 10


def test_parse_forecast_days_rejects_more_than_ten_days():
    with pytest.raises(ValueError, match="FORECAST_DAYS=11 exceeds the supported 10-day forecast limit"):
        parse_forecast_days("11")


def test_parse_forecast_days_rejects_zero_days():
    with pytest.raises(ValueError, match="FORECAST_DAYS must be a positive integer"):
        parse_forecast_days("0")


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", " TRUE "])
def test_parse_bool_accepts_enabled_values(value):
    assert parse_bool(value)


@pytest.mark.parametrize("value", ["0", "false", "no", "off", " FALSE "])
def test_parse_bool_accepts_disabled_values(value):
    assert not parse_bool(value, default=True)


def test_parse_bool_uses_default_for_blank_values():
    assert parse_bool(None, default=True)
    assert not parse_bool("", default=False)


def test_strict_automation_failures_defaults_to_resilient_mode():
    assert settings.STRICT_AUTOMATION_FAILURES is False


def test_browser_channel_defaults_to_system_chrome():
    assert settings.BROWSER_CHANNEL == "chrome"


def test_parse_bool_rejects_unknown_values():
    with pytest.raises(ValueError, match="Invalid boolean value"):
        parse_bool("maybe")


def test_parse_positive_int_defaults_and_rejects_negative_values():
    assert parse_positive_int(None, 0, "RANDOM_CITY_COUNT") == 0
    assert parse_positive_int("3", 0, "RANDOM_CITY_COUNT") == 3
    with pytest.raises(ValueError, match="RANDOM_CITY_COUNT must be zero or a positive integer"):
        parse_positive_int("-1", 0, "RANDOM_CITY_COUNT")
