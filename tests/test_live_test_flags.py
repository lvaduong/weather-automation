from tests.test_weather_forecast_live import (
    env_flag_enabled,
    positive_int_env_set,
    random_city_live_test_enabled,
)


def test_env_flag_enabled_accepts_true_values(monkeypatch):
    for value in ["true", "TRUE", "1", "yes", "on"]:
        monkeypatch.setenv("RUN_RANDOM_CITY_WEATHER_TESTS", value)

        assert env_flag_enabled("RUN_RANDOM_CITY_WEATHER_TESTS")


def test_env_flag_enabled_rejects_false_values(monkeypatch):
    for value in ["false", "FALSE", "0", "no", "off", ""]:
        monkeypatch.setenv("RUN_RANDOM_CITY_WEATHER_TESTS", value)

        assert not env_flag_enabled("RUN_RANDOM_CITY_WEATHER_TESTS")


def test_positive_int_env_set_accepts_positive_numbers(monkeypatch):
    monkeypatch.setenv("RANDOM_CITY_COUNT", "5")

    assert positive_int_env_set("RANDOM_CITY_COUNT")


def test_positive_int_env_set_rejects_zero_missing_and_invalid_values(monkeypatch):
    for value in ["0", "-1", "abc", ""]:
        monkeypatch.setenv("RANDOM_CITY_COUNT", value)

        assert not positive_int_env_set("RANDOM_CITY_COUNT")


def test_random_city_live_test_enabled_by_city_count(monkeypatch):
    monkeypatch.delenv("RUN_RANDOM_CITY_WEATHER_TESTS", raising=False)
    monkeypatch.setenv("RANDOM_CITY_COUNT", "2")

    assert random_city_live_test_enabled()
