import pytest

from models.weather_record import WeatherRecord
from pages.daily_forecast_page import DailyForecastPage


def test_card_text_is_converted_to_day_and_night_records():
    page = DailyForecastPage.__new__(DailyForecastPage)
    text = (
        "Thursday, November 8 Day 88°F 31°C Cloudy RealFeel 101°F "
        "Humidity 70% Night 72°F 22°C Clear RealFeel 75°F Humidity 80%"
    )

    records = page._records_from_card_text(text)

    assert len(records) == 2
    assert records[0].period == "Day"
    assert records[0].temperature_f == 88
    assert records[0].temperature_c_calculated == 31.1
    assert records[0].validation_status == "PASSED"
    assert records[0].error_message is None
    assert records[0].realfeel_f == 101
    assert records[0].humidity == 70
    assert records[1].period == "Night"
    assert records[1].temperature_f == 72
    assert records[1].realfeel_f == 75
    assert records[1].humidity == 80
    assert records[1].error_message is None


def test_card_text_marks_missing_temperature_without_crashing():
    page = DailyForecastPage.__new__(DailyForecastPage)
    text = "Thursday, November 8 Day Cloudy Humidity 70% Night Clear"

    records = page._records_from_card_text(text)

    assert records[0].validation_status == "MISSING_TEMPERATURE"
    assert records[0].error_message == "Missing fields: temperature_f, realfeel_f"
    assert records[1].validation_status == "MISSING_TEMPERATURE"
    assert records[1].error_message == "Missing fields: temperature_f, realfeel_f, humidity"


def test_card_text_marks_failed_when_displayed_celsius_is_outside_tolerance():
    page = DailyForecastPage.__new__(DailyForecastPage)
    text = "Thursday, November 8 Day 88Â°F 20Â°C Cloudy Night 72Â°F 22Â°C Clear"

    records = page._records_from_card_text(text)

    assert records[0].temperature_c_calculated == 31.1
    assert records[0].validation_status == "FAILED"


def test_card_text_supports_negative_temperatures():
    page = DailyForecastPage.__new__(DailyForecastPage)
    text = "Monday, January 12 Day -4Â°F -20Â°C Cloudy Night -13Â°F -25Â°C Clear"

    records = page._records_from_card_text(text)

    assert records[0].temperature_f == -4
    assert records[0].temperature_c_calculated == -20.0
    assert records[0].validation_status == "PASSED"
    assert records[1].temperature_f == -13
    assert records[1].temperature_c_calculated == -25.0
    assert records[1].validation_status == "PASSED"


def test_half_day_card_text_is_converted_to_single_record():
    page = DailyForecastPage.__new__(DailyForecastPage)
    text = (
        "Day 5/15 37°Hi RealFeel® 43° RealFeel Shade™ 40° "
        "Cloudy and remaining very warm; a thunderstorm in spots in the afternoon "
        "Max UV Index 3.0 (Moderate) Wind SSW 11 km/h Cloud Cover 98%"
    )

    record = page._record_from_half_day_text(text)

    assert record.date == "5/15"
    assert record.period == "Day"
    assert record.temperature_f == 98.6
    assert record.temperature_c_displayed == 37
    assert record.temperature_c_calculated == 37.0
    assert record.validation_status == "PASSED"
    assert record.realfeel_f == 109.4
    assert record.weather == "Cloudy and remaining very warm; a thunderstorm in spots in the afternoon"
    assert record.realfeel_shade_f == 104.0
    assert record.max_uv_index == "3.0 (Moderate)"
    assert record.wind == "SSW 11 km/h"


def test_half_day_card_uses_celsius_when_fahrenheit_is_absent():
    page = DailyForecastPage.__new__(DailyForecastPage)
    text = (
        "Night 5/15 22Â°Lo RealFeelÂ® 20Â° "
        "Clear and mild Wind SSW 11 km/h Cloud Cover 10%"
    )

    record = page._record_from_half_day_text(text)

    assert record.period == "Night"
    assert record.temperature_f == 71.6
    assert record.temperature_c_displayed == 22
    assert record.temperature_c_calculated == 22.0
    assert record.validation_status == "PASSED"
    assert record.realfeel_f == 68.0
    assert record.humidity is None


def test_detail_half_day_card_extracts_expanded_humidity_and_full_date():
    page = DailyForecastPage.__new__(DailyForecastPage)
    text = (
        "Day 5/15 37° Hi RealFeel® 46° RealFeel Shade™ 41° "
        "Hot with some sun, then turning cloudy; an afternoon thunderstorm in spots; "
        "caution advised if outside for extended periods of time "
        "Max UV Index 12.0 (Extreme) Wind SW 13 km/h "
        "MORNING Humidity 70% AFTERNOON Humidity 75%"
    )

    record = page._record_from_half_day_text(text)
    record.date = page._full_date_from_numeric_date(record.date)

    assert record.date == "Friday, May 15"
    assert record.period == "Day"
    assert record.temperature_f == 98.6
    assert record.realfeel_f == 114.8
    assert record.humidity == 70
    assert record.weather == (
        "Hot with some sun, then turning cloudy; an afternoon thunderstorm in spots; "
        "caution advised if outside for extended periods of time"
    )


def test_detail_half_day_card_creates_morning_and_afternoon_records():
    page = DailyForecastPage.__new__(DailyForecastPage)
    base_record = page._record_from_half_day_text(
        "Day 5/15 37° Hi RealFeel® 46° "
        "Hot with some sun, then turning cloudy Max UV Index 12.0 (Extreme)"
    )
    base_record.date = page._full_date_from_numeric_date(base_record.date)
    text = "MORNING Humidity 70% Cloud Cover 61% AFTERNOON Humidity 75% Cloud Cover 68%"

    records = page._records_from_time_of_day_sections(base_record, text)

    assert [record.period for record in records] == ["Morning", "Afternoon"]
    assert [record.humidity for record in records] == [70, 75]
    assert all(record.date == "Friday, May 15" for record in records)
    assert all(record.temperature_f == 98.6 for record in records)
    assert all(record.max_uv_index == "12.0 (Extreme)" for record in records)


def test_detail_half_day_card_carries_daily_details_to_time_of_day_records():
    page = DailyForecastPage.__new__(DailyForecastPage)
    base_record = page._record_from_half_day_text(
        "Day 5/15 37Â° Hi RealFeelÂ® 46Â° RealFeel Shadeâ„¢ 41Â° "
        "Hot with some sun Max UV Index 12.0 (Extreme) Wind SW 13 km/h "
        "Precipitation 55% Hours of Precipitation 1.5 Hours of Rain 1.0"
    )
    text = "MORNING Humidity 70% Cloud Cover 61% AFTERNOON Humidity 75% Cloud Cover 68%"

    records = page._records_from_time_of_day_sections(base_record, text)

    assert [record.period for record in records] == ["Morning", "Afternoon"]
    assert all(record.realfeel_shade_f == 105.8 for record in records)
    assert all(record.max_uv_index == "12.0 (Extreme)" for record in records)
    assert all(record.wind == "SW 13 km/h" for record in records)
    assert all(record.precipitation_probability == 55 for record in records)
    assert all(record.hours_of_precipitation == 1.5 for record in records)
    assert all(record.hours_of_rain == 1.0 for record in records)


def test_labeled_value_stops_before_acculumen_detail():
    text = "Max UV Index 12.0 (Extreme) AccuLumen Brightness Index™ 5 (Medium) Wind SW 11 km/h"

    assert DailyForecastPage._extract_labeled_value(text, "Max UV Index") == "12.0 (Extreme)"


def test_time_of_day_sections_are_clicked_one_by_one():
    page = DailyForecastPage.__new__(DailyForecastPage)
    clicked = []

    class FakeTextLocator:
        def __init__(self, label):
            self.label = label
            self.first = self

        def wait_for(self, state, timeout):
            return None

        def click(self):
            clicked.append(self.label)

    class FakeBodyLocator:
        def inner_text(self, timeout):
            return "MORNING Humidity 70% Cloud Cover 61% AFTERNOON Humidity 75% Cloud Cover 68%"

    class FakePage:
        frames = []

        def get_by_role(self, role, name):
            return FakeTextLocator(name.pattern.strip("^$\\"))

        def get_by_label(self, pattern):
            return FakeEmptyLocator()

        def wait_for_timeout(self, timeout):
            return None

        def locator(self, selector):
            return FakeBodyLocator()

    class FakeEmptyLocator:
        first = None

        def count(self):
            return 0

    class FakeLogger:
        def warning(self, *args):
            return None

    page.page = FakePage()
    page.logger = FakeLogger()
    base_record = page._record_from_half_day_text(
        "Day 5/15 37° Hi RealFeel® 46° "
        "Hot with some sun, then turning cloudy Max UV Index 12.0 (Extreme)"
    )

    records = page._click_and_extract_time_of_day_records(base_record)

    assert clicked == ["Morning", "Afternoon"]
    assert [record.period for record in records] == ["Morning", "Afternoon"]
    assert [record.humidity for record in records] == [70, 75]


def test_missing_morning_and_afternoon_are_backfilled_after_night_sections():
    page = DailyForecastPage.__new__(DailyForecastPage)
    clicked = []
    night_base = WeatherRecord(
        date="Friday, May 15",
        period="Night",
        temperature_f=80.6,
        temperature_c_calculated=27.0,
        temperature_c_displayed=27.0,
        weather="Cloudy",
        realfeel_f=89.6,
        humidity=84,
        validation_status="PASSED",
    )
    day_base = WeatherRecord(
        date="Friday, May 15",
        period="Day",
        temperature_f=98.6,
        temperature_c_calculated=37.0,
        temperature_c_displayed=37.0,
        weather="Hot",
        realfeel_f=114.8,
        humidity=70,
        validation_status="PASSED",
    )
    existing_records = [
        WeatherRecord(
            date="Friday, May 15",
            period="Evening",
            temperature_f=80.6,
            temperature_c_calculated=27.0,
            temperature_c_displayed=27.0,
            weather="Cloudy",
            realfeel_f=89.6,
            humidity=84,
            validation_status="PASSED",
        ),
        WeatherRecord(
            date="Friday, May 15",
            period="Overnight",
            temperature_f=80.6,
            temperature_c_calculated=27.0,
            temperature_c_displayed=27.0,
            weather="Cloudy",
            realfeel_f=89.6,
            humidity=91,
            validation_status="PASSED",
        ),
    ]

    def click_time_of_day_section(label, labels):
        clicked.append(label)
        return {
            "Morning": "Humidity 70%",
            "Afternoon": "Humidity 75%",
        }.get(label, "")

    page._click_time_of_day_section = click_time_of_day_section
    page._extract_day_and_night_base_records = lambda: [day_base, night_base]

    records = page._backfill_missing_time_of_day_records(existing_records, [night_base])

    assert [record.period for record in records] == ["Morning", "Afternoon", "Evening", "Overnight"]
    assert [record.humidity for record in records] == [70, 75, 84, 91]
    assert records[0].temperature_f == 98.6
    assert records[1].temperature_f == 98.6
    assert clicked == ["Morning", "Afternoon"]


def test_expanded_ten_day_card_text_extracts_visible_detail_fields():
    page = DailyForecastPage.__new__(DailyForecastPage)
    text = (
        "FRI 5/15 37° /27° 55% "
        "Hot with some sun, then turning cloudy; an afternoon thunderstorm in spots; "
        "caution advised if outside for extended periods of time "
        "RealFeel® 45° RealFeel Shade™ 41° Max UV Index 11.0 (Extreme) "
        "Wind SW 11 km/h Hours of Precipitation 1.5 Hours of Rain 1.5"
    )

    record = page._record_from_expanded_daily_text(text)

    assert record.date == "FRI 5/15"
    assert record.period == "Day"
    assert record.temperature_f == 98.6
    assert record.temperature_c_displayed == 37
    assert record.temperature_c_calculated == 37.0
    assert record.validation_status == "PASSED"
    assert record.weather == (
        "Hot with some sun, then turning cloudy; an afternoon thunderstorm in spots; "
        "caution advised if outside for extended periods of time"
    )
    assert record.realfeel_f == 113.0
    assert record.realfeel_shade_f == 105.8
    assert record.precipitation_probability == 55
    assert record.low_temperature_c_displayed == 27
    assert record.low_temperature_f == 80.6
    assert record.max_uv_index == "11.0 (Extreme)"
    assert record.wind == "SW 11 km/h"
    assert record.hours_of_precipitation == 1.5
    assert record.hours_of_rain == 1.5
    assert record.humidity == 55
    assert record.error_message is None


def test_compact_ten_day_card_text_extracts_summary_fields():
    page = DailyForecastPage.__new__(DailyForecastPage)
    text = (
        "SAT 5/16 35° /27° 40% "
        "Mostly cloudy and very warm; a thunderstorm in spots in the afternoon"
    )

    record = page._record_from_compact_ten_day_text(text)

    assert record.date == "SAT 5/16"
    assert record.period == "Day"
    assert record.temperature_f == 95.0
    assert record.temperature_c_displayed == 35
    assert record.low_temperature_c_displayed == 27
    assert record.low_temperature_f == 80.6
    assert record.weather == "Mostly cloudy and very warm; a thunderstorm in spots in the afternoon"
    assert record.precipitation_probability == 40
    assert record.humidity is None
    assert record.validation_status == "PASSED"
    assert record.error_message is None


def test_compact_ten_day_card_does_not_use_precipitation_as_weather_or_humidity():
    page = DailyForecastPage.__new__(DailyForecastPage)
    text = "TUE 5/19 33Â° /27Â° 100%"

    record = page._record_from_compact_ten_day_text(text)

    assert record.weather is None
    assert record.humidity is None
    assert record.precipitation_probability == 100
    assert record.validation_status == "PASSED"
    assert record.error_message == "Missing fields: weather"


def test_ten_day_url_is_created_from_location_or_daily_forecast_url():
    page = DailyForecastPage.__new__(DailyForecastPage)

    class FakePage:
        url = "https://www.accuweather.com/en/vn/city/1/weather-forecast/1"

    page.page = FakePage()
    assert page._ten_day_url_from_current_url().endswith("/10-day-weather-forecast/1")

    page.page.url = "https://www.accuweather.com/en/vn/city/1/daily-weather-forecast/1"
    assert page._ten_day_url_from_current_url().endswith("/10-day-weather-forecast/1")

    page.page.url = "https://www.accuweather.com/en/vn/city/1/10-day-weather-forecast/1"
    assert page._ten_day_url_from_current_url().endswith("/10-day-weather-forecast/1")


def test_forecast_range_accepts_uppercase_months():
    assert DailyForecastPage._is_forecast_range_text("MAY 15 - MAY 29")
    assert DailyForecastPage._normalize_forecast_range_text("MAY 15 - MAY 29") == "May 15 - May 29"


def test_search_results_page_clicks_first_location_option():
    page = DailyForecastPage.__new__(DailyForecastPage)
    clicked = []

    class FakeLocator:
        first = None

        def __init__(self, selector):
            self.selector = selector
            self.first = self

        def wait_for(self, state, timeout):
            if self.selector != ".locations-list a[href]":
                raise RuntimeError("not found")

        def click(self):
            clicked.append(self.selector)

    class FakePage:
        url = "https://www.accuweather.com/en/search-locations?query=Ho+Chi+Minh+City"

        def locator(self, selector):
            return FakeLocator(selector)

    class FakeLogger:
        def info(self, *args):
            return None

    page.page = FakePage()
    page.logger = FakeLogger()

    page._select_matching_location("Ho Chi Minh City", "Vietnam")

    assert clicked == [".locations-list a[href]"]


def test_visible_search_result_list_wins_before_generic_city_link():
    page = DailyForecastPage.__new__(DailyForecastPage)
    clicked = []

    class FakeLocator:
        first = None

        def __init__(self, selector):
            self.selector = selector
            self.first = self

        def wait_for(self, state, timeout):
            if self.selector != ".locations-list a[href]":
                raise RuntimeError("not found")

        def click(self):
            clicked.append(self.selector)

    class FakePage:
        url = "https://www.accuweather.com/"

        def locator(self, selector):
            return FakeLocator(selector)

        def get_by_role(self, role, name):
            raise AssertionError("generic role lookup should not run when result list is visible")

    class FakeLogger:
        def info(self, *args):
            return None

    page.page = FakePage()
    page.logger = FakeLogger()

    page._select_matching_location("Ho Chi Minh City", "Vietnam")

    assert clicked == [".locations-list a[href]"]


def test_best_location_fallback_keeps_first_city_match():
    page = DailyForecastPage.__new__(DailyForecastPage)
    clicked = []

    class FakeSuggestion:
        def __init__(self, text):
            self.text = text

        def inner_text(self, timeout):
            return self.text

        def click(self):
            clicked.append(self.text)

    class FakeLocator:
        def __init__(self):
            self.items = [
                FakeSuggestion("Ho Chi Minh City"),
                FakeSuggestion("Ho Chi Minh City University of Sports"),
                FakeSuggestion("Ho Chi Minh City University of Technology"),
            ]
            self.first = self.items[0]

        def count(self):
            return len(self.items)

        def nth(self, index):
            return self.items[index]

    page._click_best_location_match(
        FakeLocator(),
        city="Ho Chi Minh City",
        country="Vietnam",
        expected="ho chi minh city vietnam",
    )

    assert clicked == ["Ho Chi Minh City"]


def test_open_ten_day_uses_direct_url_before_menu_click():
    page = DailyForecastPage.__new__(DailyForecastPage)

    class FakeLocator:
        def __init__(self):
            self.first = self
            self.clicked = False

        def wait_for(self, state, timeout):
            return None

        def click(self):
            self.clicked = True

    class FakePage:
        url = "https://www.accuweather.com/en/vn/city/1/weather-forecast/1"

        def __init__(self):
            self.locators = []
            self.goto_calls = []
            self.ten_day_locator = FakeLocator()

        def locator(self, selector):
            self.locators.append(selector)
            return self.ten_day_locator

    fake_page = FakePage()
    page.page = fake_page
    page.current_url = fake_page.url
    page.logger = type("Logger", (), {"info": lambda self, *args, **kwargs: None})()
    page.goto = lambda url, action_name: fake_page.goto_calls.append((url, action_name))

    page._open_ten_day_link_or_url()

    assert fake_page.ten_day_locator.clicked is False
    assert fake_page.goto_calls == [
        (
            "https://www.accuweather.com/en/vn/city/1/10-day-weather-forecast/1",
            "open 10-day forecast URL",
        )
    ]
    assert fake_page.locators == []


def test_open_ten_day_does_not_reopen_current_ten_day_url():
    page = DailyForecastPage.__new__(DailyForecastPage)

    class FakePage:
        url = "about:blank"

        def __init__(self):
            self.locators = []
            self.goto_calls = []

        def locator(self, selector):
            self.locators.append(selector)
            raise AssertionError("locator lookup should not be needed")

    fake_page = FakePage()
    page.page = fake_page
    page.current_url = "https://www.accuweather.com/en/vn/city/1/10-day-weather-forecast/1"
    page.logger = type("Logger", (), {"info": lambda self, *args, **kwargs: None})()
    page.goto = lambda url, action_name: fake_page.goto_calls.append((url, action_name))

    page._open_ten_day_link_or_url()

    assert fake_page.goto_calls == []
    assert fake_page.locators == []


def test_ten_day_detail_extraction_uses_card_record_when_detail_page_is_empty():
    page = DailyForecastPage.__new__(DailyForecastPage)
    fallback_record = WeatherRecord(
        date="5/19",
        period="Day",
        temperature_f=95.0,
        temperature_c_calculated=35.0,
        temperature_c_displayed=35.0,
        weather="Cloudy",
        realfeel_f=None,
        humidity=None,
        validation_status="PASSED",
    )
    opened_urls = []

    page.collect_ten_day_detail_urls = lambda max_days: ["https://example.com/day/1"]
    page._ten_day_card_records_by_detail_url = lambda max_days: {
        "https://example.com/day/1": [fallback_record]
    }
    page.goto = lambda url, action_name: opened_urls.append((url, action_name))
    page.extract_detail_weather_records_with_retry = lambda: []
    page.logger = type("Logger", (), {"info": lambda self, *args, **kwargs: None})()

    records = page.extract_weather_records_from_ten_day_details(1)

    assert records == [fallback_record]
    assert opened_urls == [("https://example.com/day/1", "open 10-day detail card 1")]


def test_ten_day_http_fallback_uses_card_records_without_opening_detail_pages():
    page = DailyForecastPage.__new__(DailyForecastPage)
    first_record = WeatherRecord(
        date="5/19",
        period="Day",
        temperature_f=95.0,
        temperature_c_calculated=35.0,
        temperature_c_displayed=35.0,
        weather="Cloudy",
        realfeel_f=None,
        humidity=None,
        validation_status="PASSED",
    )
    second_record = WeatherRecord(
        date="5/20",
        period="Day",
        temperature_f=96.8,
        temperature_c_calculated=36.0,
        temperature_c_displayed=36.0,
        weather="Sunny",
        realfeel_f=None,
        humidity=None,
        validation_status="PASSED",
    )
    page.loaded_via_http_fallback = True
    page._ten_day_card_records_by_detail_url = lambda max_days: {
        "https://example.com/day/1": [first_record],
        "https://example.com/day/2": [second_record],
    }
    page.collect_ten_day_detail_urls = lambda max_days: pytest.fail("detail URLs should not be opened")
    page.goto = lambda url, action_name: pytest.fail("detail pages should not be opened")
    page.logger = type("Logger", (), {"info": lambda self, *args, **kwargs: None})()

    records = page.extract_weather_records_from_ten_day_details(2)

    assert records == [first_record, second_record]


def test_records_are_limited_by_unique_10_day_dates():
    records = []
    for day_number in range(1, 13):
        records.append(type("Record", (), {"date": f"5/{day_number}", "period": "Day"})())

    limited = DailyForecastPage._limit_records_by_unique_dates(records, 10)

    assert len(limited) == 10
    assert limited[-1].date == "5/10"


def test_daily_url_day_parameter_is_added_or_replaced():
    original = "https://www.accuweather.com/en/vn/city/1/daily-weather-forecast/1?day=3"
    updated = DailyForecastPage._url_with_day(original, 12)

    assert updated.endswith("?day=12")

    without_query = "https://www.accuweather.com/en/vn/city/1/daily-weather-forecast/1"
    assert DailyForecastPage._url_with_day(without_query, 4).endswith("?day=4")


def test_daily_url_day_parameter_preserves_existing_query_params():
    original = (
        "https://www.accuweather.com/en/vn/city/1/daily-weather-forecast/1"
        "?unit=c&lang=en&day=3"
    )

    updated = DailyForecastPage._url_with_day(original, 12)

    assert updated.endswith("?unit=c&lang=en&day=12")


def test_extract_weather_records_with_retry_retries_transient_failure(monkeypatch):
    monkeypatch.setattr("config.settings.RETRY_ATTEMPTS", 3)

    class FakePage:
        def set_default_timeout(self, timeout):
            pass

        def wait_for_timeout(self, timeout):
            return None

    page = DailyForecastPage(FakePage())
    attempt = {"count": 0}

    def failing_extract():
        attempt["count"] += 1
        if attempt["count"] < 2:
            raise RuntimeError("transient failure")
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

    page.extract_weather_records = failing_extract

    records = page.extract_weather_records_with_retry()

    assert attempt["count"] == 2
    assert len(records) == 1
    assert records[0].date == "5/15"


def test_extract_weather_records_with_retry_raises_after_max_attempts():
    class FakePage:
        def set_default_timeout(self, timeout):
            pass

        def wait_for_timeout(self, timeout):
            return None

    page = DailyForecastPage(FakePage())

    def always_fail():
        raise RuntimeError("persistent failure")

    page.extract_weather_records = always_fail

    with pytest.raises(RuntimeError, match="Extract weather records failed after"):
        page.extract_weather_records_with_retry()
