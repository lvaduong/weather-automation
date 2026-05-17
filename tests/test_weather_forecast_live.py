import os

import pytest

from config import settings
from services.weather_scraper import RandomCityWeatherScraper, WeatherScraper


pytestmark = pytest.mark.live


def env_flag_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def positive_int_env_set(name: str) -> bool:
    try:
        return int(os.getenv(name, "").strip()) > 0
    except ValueError:
        return False


def random_city_live_test_enabled() -> bool:
    return env_flag_enabled("RUN_RANDOM_CITY_WEATHER_TESTS") or positive_int_env_set("RANDOM_CITY_COUNT")


@pytest.mark.skipif(
    not env_flag_enabled("RUN_LIVE_WEATHER_TESTS"),
    reason="Set RUN_LIVE_WEATHER_TESTS=true to run live AccuWeather browser extraction.",
)
def test_weather_forecast_extraction_live(page):
    result = WeatherScraper(page).run()

    assert result["record_count"] > 0
    assert result["date_range_valid"], f"Forecast range was not parseable: {result['forecast_range']}"
    assert len(result["expected_dates"]) == settings.FORECAST_DAYS
    assert result["missing_dates"] == [], f"Missing forecast dates: {result['missing_dates']}"
    assert result["missing_sections"] == [], f"Missing forecast sections: {result['missing_sections']}"
    expected_section_count = sum(
        len(WeatherScraper._expected_sections_for_date(expected_date))
        for expected_date in result["expected_dates"]
    )
    assert result["record_count"] >= expected_section_count
    assert result["csv_path"].exists()
    assert result["json_path"].exists()
    assert result["report_path"].exists()


@pytest.mark.skipif(
    not random_city_live_test_enabled(),
    reason="Set RANDOM_CITY_COUNT to a positive number to run random-city live tests.",
)
def test_random_city_weather_extraction_live(page):
    results = RandomCityWeatherScraper(page).run()

    assert len(results) > 0
    for result in results:
        assert result["record_count"] > 0
        assert result["csv_path"].exists()
        assert result["json_path"].exists()
        assert result["report_path"].exists()
