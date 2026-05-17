from models.city_target import CityTarget
from models.weather_record import WeatherRecord
from services.weather_scraper import RandomCityWeatherScraper, WeatherScraper


def freeze_weather_scraper_time(monkeypatch, timestamp="20260515_185449_123456"):
    monkeypatch.setattr(
        "services.weather_scraper.datetime",
        type(
            "FixedDateTime",
            (),
            {"now": staticmethod(lambda: type("FixedNow", (), {"strftime": lambda self, fmt: timestamp})())},
        ),
    )


def freeze_weather_scraper_datetime(monkeypatch, month=5, day=15, hour=19):
    class FixedDateTime:
        @staticmethod
        def now():
            return type("FixedNow", (), {"month": month, "day": day, "hour": hour})()

        @staticmethod
        def strptime(value, fmt):
            from datetime import datetime

            return datetime.strptime(value, fmt)

    monkeypatch.setattr("services.weather_scraper.datetime", FixedDateTime)


def test_random_city_selection_returns_requested_count():
    targets = [
        CityTarget("City A", "Country", "https://example.com/a"),
        CityTarget("City B", "Country", "https://example.com/b"),
        CityTarget("City C", "Country", "https://example.com/c"),
        CityTarget("City D", "Country", "https://example.com/d"),
    ]

    scraper = RandomCityWeatherScraper(
        page=None,
        city_targets=targets,
        city_count=3,
        random_seed="debug",
    )

    selected = scraper.select_cities()

    assert len(selected) == 3
    assert len(set(selected)) == 3


def test_random_city_selection_allows_exact_pool_size():
    targets = [
        CityTarget("City A", "Country", "https://example.com/a"),
        CityTarget("City B", "Country", "https://example.com/b"),
    ]

    scraper = RandomCityWeatherScraper(
        page=None,
        city_targets=targets,
        city_count=2,
        random_seed="debug",
    )

    selected = scraper.select_cities()

    assert len(selected) == 2
    assert set(selected) == set(targets)


def test_random_city_selection_allows_zero_cities():
    targets = [
        CityTarget("City A", "Country", "https://example.com/a"),
        CityTarget("City B", "Country", "https://example.com/b"),
    ]

    scraper = RandomCityWeatherScraper(
        page=None,
        city_targets=targets,
        city_count=0,
        random_seed="debug",
    )

    assert scraper.select_cities() == []


def test_city_target_slug_is_file_safe():
    target = CityTarget("Ho Chi Minh City", "Vietnam", "https://example.com")

    assert target.slug == "ho-chi-minh-city-vietnam"


def test_weather_scraper_can_be_forced_to_search_instead_of_direct_url(monkeypatch):
    monkeypatch.setattr("config.settings.LOCATION_URL", "https://example.com/direct")

    scraper = WeatherScraper(
        page=None,
        city="Tokyo",
        country="Japan",
        location_url="",
    )

    assert scraper.location_url == ""


def test_weather_scraper_finds_configured_city_url(monkeypatch):
    targets = [
        CityTarget("Ho Chi Minh City", "Vietnam", "https://example.com/hcm"),
        CityTarget("Tokyo", "Japan", "https://example.com/tokyo"),
    ]
    monkeypatch.setattr("config.settings.CITY_TARGETS", targets)

    scraper = WeatherScraper(
        page=None,
        city="Tokyo",
        country="Japan",
        location_url="",
    )

    assert scraper._configured_location_url() == "https://example.com/tokyo"


def test_failure_screenshot_path_includes_city_and_timestamp(monkeypatch):
    freeze_weather_scraper_time(monkeypatch)

    scraper = WeatherScraper(page=None, city="Ho Chi Minh City", country="Vietnam")
    screenshot_path = scraper._failure_screenshot_path()

    assert screenshot_path.name == "failure_ho-chi-minh-city-vietnam_20260515_185449_123456.png"


def test_summary_report_path_includes_city_and_timestamp(monkeypatch):
    freeze_weather_scraper_time(monkeypatch)

    scraper = WeatherScraper(page=None, city="Ho Chi Minh City", country="Vietnam")
    report_path = scraper._summary_report_path()

    assert report_path.name == "summary_report_ho-chi-minh-city-vietnam_20260515_185449_123456.html"


def test_weather_scraper_continues_when_open_daily_forecast_fails(monkeypatch, tmp_path):
    written_records = {}

    class FakeDailyForecastPage:
        def __init__(self, page):
            self.page = type("FakePage", (), {"url": ""})()

        def open_location_url(self, location_url: str) -> None:
            self.page.url = location_url

        def open_daily_forecast(self):
            raise RuntimeError("open 10-day forecast failed after retries")

        def ensure_ten_day_forecast_range(self):
            return "May 15 - May 24"

        def extract_all_available_weather_records(self, max_days):
            return [
                WeatherRecord(
                    date="5/15",
                    period="Day",
                    temperature_f=80.0,
                    temperature_c_calculated=26.7,
                    temperature_c_displayed=27.0,
                    weather="Sunny",
                    realfeel_f=82.0,
                    humidity=45,
                    validation_status="PASSED",
                )
            ]

        def _is_ten_day_url(self, url: str) -> bool:
            return "/10-day-weather-forecast/" in url

        def take_screenshot(self, path):
            return path

    monkeypatch.setattr("services.weather_scraper.DailyForecastPage", FakeDailyForecastPage)
    def fake_write_csv(records, path):
        written_records["csv"] = records
        return tmp_path / "weather_data.csv"

    def fake_write_json(records, path):
        written_records["json"] = records
        return tmp_path / "weather_data.json"

    monkeypatch.setattr("services.weather_scraper.write_csv", fake_write_csv)
    monkeypatch.setattr("services.weather_scraper.write_json", fake_write_json)
    monkeypatch.setattr(
        "services.weather_scraper.ReportService.generate_summary",
        lambda self, records, city, forecast_range, missing_dates, missing_sections, output_path: output_path,
    )

    scraper = WeatherScraper(page=None, location_url="https://example.com")
    result = scraper.run()

    assert result["record_count"] == 1
    assert result["forecast_range"] == "May 15 - May 24"
    assert result["date_range_valid"] is True
    assert result["csv_path"].name == "weather_data.csv"
    assert result["json_path"].name == "weather_data.json"
    assert result["report_path"].name.startswith("summary_report_ho-chi-minh-city-vietnam_")
    assert result["report_path"].suffix == ".html"
    assert written_records["csv"][0].city == "Ho Chi Minh City, Vietnam"
    assert written_records["csv"][0].extracted_at
    assert written_records["json"][0].city == "Ho Chi Minh City, Vietnam"
    assert written_records["json"][0].extracted_at == written_records["csv"][0].extracted_at


def test_weather_scraper_opens_configured_city_url_without_homepage_search(monkeypatch, tmp_path):
    opened_urls = []

    class FakeDailyForecastPage:
        def __init__(self, page):
            self.page = type("FakePage", (), {"url": ""})()

        def open_homepage(self):
            raise AssertionError("homepage should be skipped for configured cities")

        def search_location(self, city, country):
            raise AssertionError("search should be skipped for configured cities")

        def open_location_url(self, location_url: str) -> None:
            opened_urls.append(location_url)
            self.page.url = location_url

        def open_daily_forecast(self):
            pass

        def ensure_ten_day_forecast_range(self):
            return "May 15 - May 24"

        def _is_ten_day_url(self, url: str) -> bool:
            return False

        def extract_all_available_weather_records(self, max_days):
            return [
                WeatherRecord(
                    date="5/15",
                    period="Evening",
                    temperature_f=80.0,
                    temperature_c_calculated=26.7,
                    temperature_c_displayed=27.0,
                    weather="Cloudy",
                    realfeel_f=82.0,
                    humidity=84,
                    validation_status="PASSED",
                ),
                WeatherRecord(
                    date="5/15",
                    period="Overnight",
                    temperature_f=80.0,
                    temperature_c_calculated=26.7,
                    temperature_c_displayed=27.0,
                    weather="Cloudy",
                    realfeel_f=82.0,
                    humidity=91,
                    validation_status="PASSED",
                ),
            ]

        def take_screenshot(self, path):
            return path

    monkeypatch.setattr("services.weather_scraper.DailyForecastPage", FakeDailyForecastPage)
    monkeypatch.setattr("config.settings.CITY_TARGETS", [
        CityTarget("Ho Chi Minh City", "Vietnam", "https://example.com/hcm")
    ])
    monkeypatch.setattr("services.weather_scraper.write_csv", lambda records, path: tmp_path / "weather_data.csv")
    monkeypatch.setattr("services.weather_scraper.write_json", lambda records, path: tmp_path / "weather_data.json")
    monkeypatch.setattr(
        "services.weather_scraper.ReportService.generate_summary",
        lambda self, records, city, forecast_range, missing_dates, missing_sections, output_path: output_path,
    )

    WeatherScraper(page=None, city="Ho Chi Minh City", country="Vietnam", location_url="").run()

    assert opened_urls == ["https://example.com/hcm"]


def test_weather_scraper_falls_back_to_configured_url_after_search_failure(monkeypatch, tmp_path):
    opened_urls = []

    class FakeDailyForecastPage:
        def __init__(self, page):
            self.page = type("FakePage", (), {"url": ""})()

        def open_homepage(self):
            raise RuntimeError("homepage timed out")

        def search_location(self, city, country):
            raise AssertionError("search should not run after homepage failure")

        def open_location_url(self, location_url: str) -> None:
            opened_urls.append(location_url)
            self.page.url = location_url

        def open_daily_forecast(self):
            pass

        def ensure_ten_day_forecast_range(self):
            return "May 15 - May 24"

        def _is_ten_day_url(self, url: str) -> bool:
            return False

        def extract_all_available_weather_records(self, max_days):
            return [
                WeatherRecord(
                    date="5/15",
                    period="Evening",
                    temperature_f=80.0,
                    temperature_c_calculated=26.7,
                    temperature_c_displayed=27.0,
                    weather="Cloudy",
                    realfeel_f=82.0,
                    humidity=84,
                    validation_status="PASSED",
                )
            ]

        def take_screenshot(self, path):
            return path

    configured_urls = iter([None, "https://example.com/hcm"])
    monkeypatch.setattr("services.weather_scraper.DailyForecastPage", FakeDailyForecastPage)
    monkeypatch.setattr(WeatherScraper, "_configured_location_url", lambda self: next(configured_urls))
    monkeypatch.setattr("config.settings.CITY_TARGETS", [
        CityTarget("Other City", "Vietnam", "https://example.com/other")
    ])
    monkeypatch.setattr("services.weather_scraper.write_csv", lambda records, path: tmp_path / "weather_data.csv")
    monkeypatch.setattr("services.weather_scraper.write_json", lambda records, path: tmp_path / "weather_data.json")
    monkeypatch.setattr(
        "services.weather_scraper.ReportService.generate_summary",
        lambda self, records, city, forecast_range, missing_dates, missing_sections, output_path: output_path,
    )

    WeatherScraper(page=None, city="Ho Chi Minh City", country="Vietnam", location_url="").run()

    assert opened_urls == ["https://example.com/hcm"]


def test_expected_dates_are_built_from_forecast_range():
    expected_dates = WeatherScraper._expected_dates_from_forecast_range("May 15 - May 29", 10)

    assert expected_dates == [
        "5/15",
        "5/16",
        "5/17",
        "5/18",
        "5/19",
        "5/20",
        "5/21",
        "5/22",
        "5/23",
        "5/24",
    ]


def test_missing_forecast_dates_are_reported():
    records = [
        type("Record", (), {"date": "FRI 5/15"})(),
        type("Record", (), {"date": "SUN 5/17"})(),
    ]

    missing_dates = WeatherScraper._missing_forecast_dates(records, ["5/15", "5/16", "5/17"])

    assert missing_dates == ["5/16"]


def test_missing_forecast_sections_are_reported():
    records = [
        type("Record", (), {"date": "Saturday, May 16", "period": "Morning"})(),
        type("Record", (), {"date": "Saturday, May 16", "period": "Evening"})(),
    ]

    missing_sections = WeatherScraper._missing_forecast_sections(records, ["5/16"])

    assert missing_sections == ["5/16 Afternoon", "5/16 Overnight"]


def test_missing_forecast_sections_require_all_sections_for_today_evening(monkeypatch):
    freeze_weather_scraper_datetime(monkeypatch, month=5, day=15, hour=19)
    records = [
        type("Record", (), {"date": "Friday, May 15", "period": "Evening"})(),
        type("Record", (), {"date": "Friday, May 15", "period": "Overnight"})(),
    ]

    missing_sections = WeatherScraper._missing_forecast_sections(records, ["5/15"])

    assert missing_sections == ["5/15 Morning", "5/15 Afternoon"]


def test_missing_forecast_sections_require_all_sections_for_future_dates(monkeypatch):
    freeze_weather_scraper_datetime(monkeypatch, month=5, day=15, hour=19)
    records = [
        type("Record", (), {"date": "Saturday, May 16", "period": "Evening"})(),
        type("Record", (), {"date": "Saturday, May 16", "period": "Overnight"})(),
    ]

    missing_sections = WeatherScraper._missing_forecast_sections(records, ["5/16"])

    assert missing_sections == ["5/16 Morning", "5/16 Afternoon"]


def test_search_results_url_is_detected():
    assert WeatherScraper._is_search_results_url(
        "https://www.accuweather.com/en/search-locations?query=Ho+Chi+Minh+City"
    )
    assert not WeatherScraper._is_search_results_url(
        "https://www.accuweather.com/en/vn/ho-chi-minh-city/353981/weather-forecast/353981"
    )


def test_detail_urls_are_chunked_across_parallel_workers():
    urls = [f"https://example.com/day-{index}" for index in range(1, 8)]

    chunks = WeatherScraper._chunk_urls(urls, 3)

    assert chunks == [
        ["https://example.com/day-1", "https://example.com/day-4", "https://example.com/day-7"],
        ["https://example.com/day-2", "https://example.com/day-5"],
        ["https://example.com/day-3", "https://example.com/day-6"],
    ]


def test_detect_local_city_sets_city_and_country_from_ip_geolocation(monkeypatch):
    import json

    mock_response = {
        "city": "New York",
        "country_name": "United States"
    }

    def mock_get(url, timeout=None):
        class MockResponse:
            def raise_for_status(self):
                pass
            def json(self):
                return mock_response
        return MockResponse()

    monkeypatch.setattr("services.weather_scraper.requests.get", mock_get)

    scraper = WeatherScraper(page=None)
    scraper._detect_local_city()

    assert scraper.city == "New York"
    assert scraper.country == "United States"


def test_detect_local_city_falls_back_on_failure(monkeypatch):
    def mock_get(url, timeout=None):
        raise Exception("Network error")

    monkeypatch.setattr("services.weather_scraper.requests.get", mock_get)

    scraper = WeatherScraper(page=None, city="Default City", country="Default Country")
    scraper._detect_local_city()

    # Should keep the original values
    assert scraper.city == "Default City"
    assert scraper.country == "Default Country"
