from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from config import settings
from models.weather_record import WeatherRecord
from pages.base_page import BasePage
from services.temperature_validator import build_temperature_validation
from utils.converter import celsius_to_fahrenheit


class DailyForecastPage(BasePage):
    SEARCH_INPUTS = [
        'input[name="query"]',
        'input[placeholder*="Search"]',
        'input[aria-label*="Search"]',
        'input[type="search"]',
    ]
    LOCATION_SUGGESTIONS = [
        '[data-qa="searchBar-results"] a',
        '[class*="locations"] a',
        '[class*="search"] a',
        ".results-container a",
        ".search-results a",
        'a[href*="/weather-forecast/"]',
        'a[href*="/en/"]',
    ]
    SEARCH_RESULT_LINKS = [
        ".locations-list a[href]",
        'a[href*="/web-api/three-day-redirect"]',
        'a[href*="type=locality"]',
    ]
    TEN_DAY_LINKS = [
        'a[href*="/10-day-weather-forecast/"]',
        'a:has-text("10-Day")',
        '[data-qa="daily"]',
        '[data-gaid="daily"]',
    ]
    DAILY_LINKS = [
        'a[href*="/daily-weather-forecast/"]',
        'a:has-text("Daily")',
        '[data-qa*="daily"]',
    ]
    FORECAST_RANGE_SELECTORS = [
        ".module-title",
    ]
    CARD_SELECTORS = [
        "a.daily-forecast-card[href]",
        ".daily-wrapper",
        ".half-day-card",
        ".daily-list-item",
        '[data-qa*="dailyCard"]',
        'a[href*="/daily-weather-forecast/"][class*="daily"]',
        ".forecast-list-card",
    ]
    TEN_DAY_CARD_LINKS = [
        'a.daily-forecast-card[href]',
        'a[href*="/weather-tomorrow/"]',
        'a[href*="/daily-weather-forecast/"]',
    ]
    DETAIL_CARD_SELECTORS = [
        ".half-day-card",
        ".half-day-card-content",
    ]

    def open_homepage(self) -> None:
        self.logger.info("Opening AccuWeather: %s", settings.BASE_URL)
        self.goto(settings.BASE_URL, "open AccuWeather homepage")
        self._accept_cookie_banner()

    def open_location_url(self, location_url: str) -> None:
        self.logger.info("Opening configured AccuWeather location URL: %s", location_url)
        self.goto(location_url, "open configured AccuWeather location URL")
        self._accept_cookie_banner()

    def search_location(self, city: str, country: str = "") -> None:
        def action() -> None:
            search_input = self._first_visible_locator(self.SEARCH_INPUTS)
            search_input.click()
            search_input.fill(city)
            self.page.keyboard.press("Enter")
            self.page.wait_for_load_state("domcontentloaded")
            self._select_matching_location(city, country)
            self.wait_for_page_loaded()
            self.current_url = self._current_url()
            self.logger.info("Selected location URL: %s", self.current_url)

        self.logger.info("Searching location: %s %s", city, country)
        self.retry(action, "search location")

    def open_daily_forecast(self) -> None:
        def action() -> None:
            self._open_ten_day_link_or_url()
            self.wait_for_page_loaded()

        self.logger.info("Opening 10-Day Forecast page")
        self.retry(action, "open 10-day forecast")

    def ensure_ten_day_forecast_range(self) -> str:
        forecast_range = self.get_forecast_range()
        if forecast_range != "Unavailable":
            return forecast_range

        ten_day_url = self._ten_day_url_from_current_url()
        if ten_day_url:
            self.goto(ten_day_url, "open 10-day forecast URL for date range")
            return self.get_forecast_range()
        return forecast_range

    def get_forecast_range(self) -> str:
        for selector in self.FORECAST_RANGE_SELECTORS:
            locator = self.page.locator(selector)
            if locator.count() == 0:
                continue
            for index in range(locator.count()):
                text = self._clean_text(locator.nth(index).inner_text(timeout=3000))
                if self._is_forecast_range_text(text):
                    return self._normalize_forecast_range_text(text)

        body_text = self._clean_text(self.page.locator("body").inner_text(timeout=3000))
        match = re.search(
            r"\b([A-Z][a-z]+|[A-Z]{3,9})\s+\d{1,2}\s*-\s*([A-Z][a-z]+|[A-Z]{3,9})\s+\d{1,2}\b",
            body_text,
            re.I,
        )
        if match:
            return self._normalize_forecast_range_text(match.group(0))
        return "Unavailable"

    def get_forecast_cards(self):
        self._scroll_to_load_forecasts()
        for selector in self.CARD_SELECTORS:
            cards = self.page.locator(selector)
            if cards.count() > 0:
                self.logger.info("Total forecast cards found: %s", cards.count())
                return cards
        raise RuntimeError("No daily forecast cards found")

    def extract_weather_records(self) -> list[WeatherRecord]:
        cards = self.get_forecast_cards()
        records: list[WeatherRecord] = []

        for index in range(cards.count()):
            card = cards.nth(index)
            try:
                text = self._clean_text(card.inner_text(timeout=5000))
                if self._is_half_day_card_text(text):
                    records.append(self._record_from_half_day_text(text))
                elif self._is_expanded_daily_card_text(text):
                    records.append(self._record_from_expanded_daily_text(text))
                elif self._is_compact_ten_day_card_text(text):
                    records.append(self._record_from_compact_ten_day_text(text))
                else:
                    records.extend(self._records_from_card_text(text))
            except Exception as error:
                self.logger.warning("Forecast card %s extraction failed: %s", index, error)
                if settings.STRICT_AUTOMATION_FAILURES:
                    raise
                records.append(
                    WeatherRecord(
                        date=f"Card {index + 1}",
                        period="Unknown",
                        temperature_f=None,
                        temperature_c_calculated=None,
                        temperature_c_displayed=None,
                        weather=None,
                        realfeel_f=None,
                        humidity=None,
                        validation_status="EXTRACTION_ERROR",
                        precipitation_probability=None,
                        error_message=str(error),
                    )
                )

        return records

    def extract_weather_records_with_retry(self) -> list[WeatherRecord]:
        last_error: Exception | None = None
        for attempt in range(1, settings.RETRY_ATTEMPTS + 1):
            try:
                return self.extract_weather_records()
            except Exception as error:
                last_error = error
                self.logger.warning(
                    "Extract weather records failed on attempt %s: %s",
                    attempt,
                    error,
                )
                if attempt < settings.RETRY_ATTEMPTS:
                    self.page.wait_for_timeout(settings.RETRY_DELAY_MS)
        raise RuntimeError(
            f"Extract weather records failed after {settings.RETRY_ATTEMPTS} attempts"
        ) from last_error

    def extract_all_available_weather_records(self, max_days: int) -> list[WeatherRecord]:
        if self._is_ten_day_url(self._current_url()):
            records = self.extract_weather_records_from_ten_day_details(max_days)
            self.logger.info("Total unique weather records collected: %s", len(records))
            return records

        daily_url = self._daily_url_from_current_url()
        if not daily_url:
            return self._limit_records_by_unique_dates(self.extract_weather_records(), max_days)

        records: list[WeatherRecord] = []
        seen_keys: set[tuple[str, str]] = set()
        consecutive_empty_pages = 0

        for day_number in range(1, max_days + 1):
            page_url = self._url_with_day(daily_url, day_number)
            self.logger.info("Extracting daily forecast page %s: %s", day_number, page_url)
            self.goto(page_url, f"open daily forecast page {day_number}")

            try:
                page_records = self.extract_weather_records_with_retry()
            except Exception as error:
                self.logger.warning("Daily forecast day=%s extraction failed: %s", day_number, error)
                if settings.STRICT_AUTOMATION_FAILURES:
                    raise
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= 3:
                    break
                continue

            new_records = []
            for record in page_records:
                key = (record.date, record.period)
                if key not in seen_keys:
                    seen_keys.add(key)
                    new_records.append(record)

            if not new_records:
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= 3:
                    break
                continue

            consecutive_empty_pages = 0
            records.extend(new_records)

        records = self._limit_records_by_unique_dates(records, max_days)
        self.logger.info("Total unique weather records collected: %s", len(records))
        return records

    def extract_detail_weather_records_with_retry(self) -> list[WeatherRecord]:
        last_error: Exception | None = None
        for attempt in range(1, settings.RETRY_ATTEMPTS + 1):
            try:
                return self.extract_detail_weather_records()
            except Exception as error:
                last_error = error
                self.logger.warning(
                    "Extract detail weather records failed on attempt %s: %s",
                    attempt,
                    error,
                )
                if attempt < settings.RETRY_ATTEMPTS:
                    self.page.wait_for_timeout(settings.RETRY_DELAY_MS)
        raise RuntimeError(
            f"Extract detail weather records failed after {settings.RETRY_ATTEMPTS} attempts"
        ) from last_error

    def extract_weather_records_from_ten_day_details(self, max_days: int) -> list[WeatherRecord]:
        fallback_records_by_url = self._ten_day_card_records_by_detail_url(max_days)
        if getattr(self, "loaded_via_http_fallback", False) and fallback_records_by_url:
            self.logger.info("Using 10-day card records from HTTP fallback page")
            records = [
                record
                for url_records in fallback_records_by_url.values()
                for record in url_records
            ]
            return self._limit_records_by_unique_dates(records, max_days)

        detail_urls = self.collect_ten_day_detail_urls(max_days)
        records: list[WeatherRecord] = []

        for index, detail_url in enumerate(detail_urls):
            self.goto(detail_url, f"open 10-day detail card {index + 1}")
            detail_records = self.extract_detail_weather_records_with_retry()
            self.logger.info(
                "Collected %s detail records from 10-day card %s",
                len(detail_records),
                index + 1,
            )
            if not detail_records:
                detail_records = fallback_records_by_url.get(detail_url, [])
                if detail_records:
                    self.logger.info(
                        "Using 10-day card fallback record for card %s",
                        index + 1,
                    )
            records.extend(detail_records)

        return records

    def _ten_day_card_records_by_detail_url(self, max_days: int) -> dict[str, list[WeatherRecord]]:
        records_by_url: dict[str, list[WeatherRecord]] = {}
        target_count = min(max_days, self._ten_day_detail_link_count())
        for selector in self.TEN_DAY_CARD_LINKS:
            links = self.page.locator(selector)
            for index in range(links.count()):
                if len(records_by_url) >= target_count:
                    return records_by_url
                href = links.nth(index).get_attribute("href")
                if not href:
                    continue
                url = urljoin(self._current_url(), href)
                text = self._clean_text(links.nth(index).inner_text(timeout=5000))
                records = self._records_from_ten_day_card_text(text)
                if records:
                    records_by_url[url] = records
            if records_by_url:
                break
        return records_by_url

    def _records_from_ten_day_card_text(self, text: str) -> list[WeatherRecord]:
        if self._is_half_day_card_text(text):
            return [self._record_from_half_day_text(text)]
        if self._is_expanded_daily_card_text(text):
            return [self._record_from_expanded_daily_text(text)]
        if self._is_compact_ten_day_card_text(text):
            return [self._record_from_compact_ten_day_text(text)]
        return self._records_from_card_text(text)

    def collect_ten_day_detail_urls(self, max_days: int) -> list[str]:
        urls: list[str] = []
        target_count = min(max_days, self._ten_day_detail_link_count())
        for selector in self.TEN_DAY_CARD_LINKS:
            links = self.page.locator(selector)
            for index in range(links.count()):
                if len(urls) >= target_count:
                    return urls
                href = links.nth(index).get_attribute("href")
                if not href:
                    continue
                url = urljoin(self._current_url(), href)
                if url not in urls:
                    urls.append(url)
            if urls:
                break
        return urls

    def extract_detail_weather_records(self) -> list[WeatherRecord]:
        base_records = self._extract_day_and_night_base_records()
        records: list[WeatherRecord] = []
        for base_record in base_records:
            records.extend(self._click_and_extract_time_of_day_records(base_record))
        return self._backfill_missing_time_of_day_records(records, base_records)

    def _extract_day_and_night_base_records(self) -> list[WeatherRecord]:
        cards = self._detail_cards()
        records = []
        for index in range(cards.count()):
            text = self._clean_text(cards.nth(index).inner_text(timeout=5000))
            if self._is_half_day_card_text(text):
                record = self._record_from_half_day_text(text)
                record.date = self._full_date_from_numeric_date(record.date)
                records.append(record)
        return records

    def _accept_cookie_banner(self) -> None:
        for label in ["Accept", "I Accept", "Agree", "Continue"]:
            button = self.page.get_by_role("button", name=re.compile(label, re.I))
            try:
                if button.count() > 0 and button.first.is_visible(timeout=1000):
                    button.first.click()
                    return
            except Exception:
                continue

    def _select_matching_location(self, city: str, country: str) -> None:
        if "/search-locations" in self._current_url():
            self._click_first_search_result(city, timeout_ms=10000, raise_if_missing=True)
            return
        if self._click_first_search_result(city, timeout_ms=1000, raise_if_missing=False):
            return

        expected = " ".join(part for part in [city, country] if part).lower()
        role_link = self.page.get_by_role("link", name=re.compile(re.escape(city), re.I))
        try:
            role_link.first.wait_for(state="visible", timeout=10000)
            self._click_best_location_match(role_link, city, country, expected)
            return
        except Exception:
            pass

        for selector in self.LOCATION_SUGGESTIONS:
            suggestions = self.page.locator(selector)
            try:
                suggestions.first.wait_for(state="visible", timeout=10000)
            except Exception:
                continue
            self._click_best_location_match(suggestions, city, country, expected)
            return

        text_match = self.page.get_by_text(re.compile(re.escape(city), re.I)).first
        try:
            text_match.wait_for(state="visible", timeout=5000)
            text_match.click()
            return
        except Exception as error:
            raise RuntimeError(f"No location search result matched {city}") from error

    def _click_first_search_result(
        self,
        city: str,
        timeout_ms: int,
        raise_if_missing: bool,
    ) -> bool:
        for selector in self.SEARCH_RESULT_LINKS:
            results = self.page.locator(selector)
            try:
                results.first.wait_for(state="visible", timeout=timeout_ms)
            except Exception:
                continue
            self.logger.info("Selecting first search result for %s", city)
            results.first.click()
            return True
        if raise_if_missing:
            raise RuntimeError(f"No search result option found for {city}")
        return False

    def _click_best_location_match(self, locator, city: str, country: str, expected: str) -> None:
        fallback = locator.first
        fallback_found = False
        city_lower = city.lower()
        country_lower = country.lower()
        for index in range(locator.count()):
            suggestion = locator.nth(index)
            text = self._clean_text(suggestion.inner_text(timeout=3000)).lower()
            if city_lower in text and (not country_lower or country_lower in text or expected in text):
                suggestion.click()
                return
            if city_lower in text and not fallback_found:
                fallback = suggestion
                fallback_found = True
        fallback.click()

    def _open_ten_day_link_or_url(self) -> None:
        current_url = self._current_url()
        if self._is_ten_day_url(current_url):
            self.logger.info("Already on 10-Day forecast URL: %s", current_url)
            return

        ten_day_url = self._ten_day_url_from_current_url()
        if ten_day_url:
            self.logger.info("Navigating directly to 10-Day forecast URL: %s", ten_day_url)
            self.goto(ten_day_url, "open 10-day forecast URL")
            return
        try:
            ten_day_link = self._first_visible_locator(self.TEN_DAY_LINKS, timeout_ms=3000)
            ten_day_link.click()
            return
        except Exception:
            self._open_daily_link_or_url()

    def _open_daily_link_or_url(self) -> None:
        daily_url = self._daily_url_from_current_url()
        if daily_url:
            self.logger.info("Navigating directly to Daily forecast URL: %s", daily_url)
            self.goto(daily_url, "open daily forecast URL")
            return
        try:
            daily_link = self._first_visible_locator(self.DAILY_LINKS, timeout_ms=3000)
            daily_link.click()
            return
        except Exception:
            raise

    def _ten_day_detail_link_count(self) -> int:
        for selector in self.TEN_DAY_CARD_LINKS:
            links = self.page.locator(selector)
            count = links.count()
            if count > 0:
                return count
        raise RuntimeError("No 10-day forecast detail links found")

    def _click_ten_day_detail_link(self, index: int) -> None:
        last_error: Exception | None = None
        for selector in self.TEN_DAY_CARD_LINKS:
            links = self.page.locator(selector)
            if links.count() <= index:
                continue
            try:
                link = links.nth(index)
                href = link.get_attribute("href")
                absolute_href = urljoin(self._current_url(), href or "")
                self.logger.info("Opening 10-day detail card %s: %s", index + 1, href)
                link.click()
                self.wait_for_page_loaded()
                self.current_url = self._current_url()
                if "accuweather.com" not in self.current_url:
                    self.logger.warning(
                        "Click was redirected away from AccuWeather (%s); opening intended detail URL",
                        self.current_url,
                    )
                    self.goto(absolute_href, f"open intended 10-day detail card {index + 1}")
                return
            except Exception as error:
                last_error = error
        raise RuntimeError(f"Could not click 10-day detail card {index + 1}") from last_error

    def _return_to_ten_day_page(self, ten_day_url: str) -> None:
        try:
            self.page.go_back(wait_until="domcontentloaded")
            self.wait_for_page_loaded()
            self.current_url = self._current_url()
            if self._is_ten_day_url(self.current_url):
                return
        except Exception:
            self.logger.info("Browser back did not return to 10-day page; using URL fallback")
        self.goto(ten_day_url, "return to 10-day forecast")

    def _detail_cards(self):
        for selector in self.DETAIL_CARD_SELECTORS:
            cards = self.page.locator(selector)
            if cards.count() > 0:
                return cards
        raise RuntimeError("No Day/Night detail cards found")

    def _click_and_extract_time_of_day_records(self, base_record: WeatherRecord) -> list[WeatherRecord]:
        labels = ["Morning", "Afternoon"] if base_record.period == "Day" else ["Evening", "Overnight"]
        records = []
        for label in labels:
            section_text = self._click_time_of_day_section(label, labels)
            if not section_text:
                continue
            record = self._record_from_time_of_day_section(base_record, label, section_text)
            if record:
                records.append(record)
        return records or [base_record]

    def _backfill_missing_time_of_day_records(
        self,
        records: list[WeatherRecord],
        base_records: list[WeatherRecord],
    ) -> list[WeatherRecord]:
        labels = ["Morning", "Afternoon", "Evening", "Overnight"]
        records_by_period = {record.period: record for record in records}
        base_by_period = {record.period: record for record in base_records}

        for label in labels:
            if label in records_by_period:
                continue

            section_text = self._click_time_of_day_section(label, labels)
            if not section_text:
                continue

            refreshed_base_by_period = {
                record.period: record
                for record in self._extract_day_and_night_base_records()
            }
            base_by_period.update(refreshed_base_by_period)
            base_record = self._base_record_for_time_of_day(label, base_by_period)
            if not base_record:
                continue

            record = self._record_from_time_of_day_section(base_record, label, section_text)
            if record:
                records_by_period[label] = record

        return [
            records_by_period[label]
            for label in labels
            if label in records_by_period
        ]

    @staticmethod
    def _base_record_for_time_of_day(
        label: str,
        base_by_period: dict[str, WeatherRecord],
    ) -> Optional[WeatherRecord]:
        primary_period = "Day" if label in ["Morning", "Afternoon"] else "Night"
        fallback_period = "Night" if primary_period == "Day" else "Day"
        return base_by_period.get(primary_period) or base_by_period.get(fallback_period)

    def _click_time_of_day_section(self, label: str, labels: list[str]) -> str:
        row = self._time_of_day_locator(label)
        try:
            row.first.wait_for(state="visible", timeout=5000)
            row.first.click()
            self._close_interstitial_ad()
            self.page.wait_for_timeout(500)
            page_text = self._clean_text(self.page.locator("body").inner_text(timeout=5000))
            return self._extract_time_of_day_section(page_text, label, labels)
        except Exception as error:
            self.logger.warning("Could not click %s section: %s", label, error)
            if settings.STRICT_AUTOMATION_FAILURES:
                raise
            return ""

    def _time_of_day_locator(self, label: str):
        link = self.page.get_by_role("link", name=re.compile(rf"^{re.escape(label)}$", re.I))
        heading = self.page.get_by_role("heading", name=re.compile(rf"^{re.escape(label)}$", re.I))
        try:
            if heading.count() > 0 and heading.first.is_visible(timeout=500):
                return heading
        except Exception:
            pass
        return link

    def _close_interstitial_ad(self) -> None:
        try:
            close_button = self.page.get_by_label(re.compile("Close ad", re.I))
            if close_button.count() > 0 and close_button.first.is_visible(timeout=1000):
                close_button.first.click()
                return
        except Exception:
            pass

        for frame in self.page.frames:
            try:
                close_button = frame.get_by_label(re.compile("Close ad", re.I))
                if close_button.count() > 0 and close_button.first.is_visible(timeout=1000):
                    close_button.first.click()
                    return
            except Exception:
                continue

    def _daily_url_from_current_url(self) -> Optional[str]:
        current_url = self._current_url()
        if "/daily-weather-forecast/" in current_url:
            return current_url
        if "/10-day-weather-forecast/" in current_url:
            return current_url.replace("/10-day-weather-forecast/", "/daily-weather-forecast/")
        if "/weather-forecast/" in current_url:
            return current_url.replace("/weather-forecast/", "/daily-weather-forecast/")
        return None

    def _ten_day_url_from_current_url(self) -> Optional[str]:
        current_url = self._current_url()
        if "/10-day-weather-forecast/" in current_url:
            return current_url
        if "/daily-weather-forecast/" in current_url:
            return current_url.replace("/daily-weather-forecast/", "/10-day-weather-forecast/")
        if "/weather-forecast/" in current_url:
            return current_url.replace("/weather-forecast/", "/10-day-weather-forecast/")
        return None

    @staticmethod
    def _is_ten_day_url(url: str) -> bool:
        return "/10-day-weather-forecast/" in url

    @staticmethod
    def _url_with_day(url: str, day_number: int) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["day"] = str(day_number)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    def _first_visible_locator(self, selectors: list[str], timeout_ms: int = 5000):
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                locator.wait_for(state="visible", timeout=timeout_ms)
                return locator
            except Exception:
                continue
        raise RuntimeError(f"No visible locator matched: {selectors}")

    def _current_url(self) -> str:
        page_url = getattr(self.page, "url", "")
        if page_url and page_url != "about:blank" and not page_url.startswith("data:"):
            self.current_url = page_url
        return self.current_url

    def _scroll_to_load_forecasts(self) -> None:
        previous_height = 0
        stable_rounds = 0
        while stable_rounds < 2:
            height = self.page.evaluate("document.body.scrollHeight")
            if height == previous_height:
                stable_rounds += 1
            else:
                stable_rounds = 0
            previous_height = height
            self.page.mouse.wheel(0, 1800)
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(500)

    def _records_from_card_text(self, text: str) -> list[WeatherRecord]:
        text = self._normalize_weather_text(text)
        date = self._extract_date(text)
        day_text = self._extract_period_text(text, "Day", "Night")
        night_text = self._extract_period_text(text, "Night", None)
        temperature_text = self._strip_secondary_temperature_fields(text)
        fallback_fahrenheit_values = self._extract_fahrenheit_values(temperature_text)
        fallback_celsius_values = self._extract_celsius_values(temperature_text)
        day_temperature_text = self._strip_secondary_temperature_fields(day_text)
        night_temperature_text = self._strip_secondary_temperature_fields(night_text)
        day_fahrenheit_values = self._extract_fahrenheit_values(day_temperature_text)
        night_fahrenheit_values = self._extract_fahrenheit_values(night_temperature_text)
        day_celsius_values = self._extract_celsius_values(day_temperature_text)
        night_celsius_values = self._extract_celsius_values(night_temperature_text)

        day_f = day_fahrenheit_values[0] if day_fahrenheit_values else (
            fallback_fahrenheit_values[0] if fallback_fahrenheit_values else None
        )
        night_f = night_fahrenheit_values[0] if night_fahrenheit_values else (
            fallback_fahrenheit_values[1] if len(fallback_fahrenheit_values) > 1 else None
        )
        day_c_displayed = day_celsius_values[0] if day_celsius_values else (
            fallback_celsius_values[0] if fallback_celsius_values else None
        )
        night_c_displayed = night_celsius_values[0] if night_celsius_values else (
            fallback_celsius_values[1] if len(fallback_celsius_values) > 1 else None
        )

        return [
            self._build_record(
                date,
                "Day",
                day_f,
                day_c_displayed,
                self._extract_weather(day_text) or self._extract_weather(text),
                self._extract_realfeel(day_text),
                self._extract_humidity(day_text),
            ),
            self._build_record(
                date,
                "Night",
                night_f,
                night_c_displayed,
                self._extract_weather(night_text) or self._extract_weather(text),
                self._extract_realfeel(night_text),
                self._extract_humidity(night_text),
            ),
        ]

    def _record_from_half_day_text(self, text: str) -> WeatherRecord:
        text = self._normalize_weather_text(text)
        period = "Night" if text.lower().startswith("night") else "Day"
        date = self._extract_date(text)
        displayed_celsius = self._extract_daily_high_celsius(text)
        fahrenheit_values = self._extract_fahrenheit_values(text)
        temperature_f = fahrenheit_values[0] if fahrenheit_values else celsius_to_fahrenheit(displayed_celsius)
        realfeel_f = self._extract_realfeel(text)
        if realfeel_f is None:
            realfeel_f = celsius_to_fahrenheit(self._extract_realfeel_celsius(text))
        weather = self._extract_weather_phrase_from_half_day(text) or self._extract_weather(text)
        humidity = self._extract_humidity(text)
        record = self._build_record(
            date,
            period,
            temperature_f,
            displayed_celsius,
            weather,
            realfeel_f,
            humidity,
        )
        self._populate_half_day_detail_fields(record, text)
        return record

    def _populate_half_day_detail_fields(self, record: WeatherRecord, text: str) -> None:
        record.realfeel_shade_f = celsius_to_fahrenheit(self._extract_realfeel_shade_celsius(text))
        record.wind = self._extract_labeled_value(text, "Wind")
        record.max_uv_index = self._extract_labeled_value(text, "Max UV Index")
        record.hours_of_precipitation = self._extract_labeled_float(text, "Hours of Precipitation")
        record.hours_of_rain = self._extract_labeled_float(text, "Hours of Rain")
        record.precipitation_probability = self._extract_labeled_percentage(
            text,
            ["Precipitation", "Rain", "Thunderstorms"],
        )
        if record.period == "Night":
            record.low_temperature_c_displayed = record.temperature_c_displayed
            record.low_temperature_f = record.temperature_f

    @staticmethod
    def _is_expanded_daily_card_text(text: str) -> bool:
        return "RealFeel" in text and bool(re.search(r"\b(?:MON|TUE|WED|THU|FRI|SAT|SUN)\b", text))

    def _record_from_expanded_daily_text(self, text: str) -> WeatherRecord:
        text = self._normalize_weather_text(text)
        date = self._extract_compact_daily_date(text)
        displayed_celsius = self._extract_primary_displayed_celsius(text)
        low_celsius = self._extract_low_displayed_celsius(text)
        fahrenheit_values = self._extract_fahrenheit_values(text)
        temperature_f = fahrenheit_values[0] if fahrenheit_values else celsius_to_fahrenheit(displayed_celsius)
        low_temperature_f = celsius_to_fahrenheit(low_celsius)
        realfeel_f = self._extract_realfeel(text)
        if realfeel_f is None:
            realfeel_f = celsius_to_fahrenheit(self._extract_realfeel_celsius(text))
        record = self._build_record(
            date,
            "Day",
            temperature_f,
            displayed_celsius,
            self._extract_expanded_daily_weather(text),
            realfeel_f,
            self._extract_ten_day_percentage(text),
            self._extract_precipitation_probability(text),
        )
        record.low_temperature_c_displayed = low_celsius
        record.low_temperature_f = low_temperature_f
        record.realfeel_shade_f = celsius_to_fahrenheit(self._extract_realfeel_shade_celsius(text))
        record.wind = self._extract_labeled_value(text, "Wind")
        record.max_uv_index = self._extract_labeled_value(text, "Max UV Index")
        record.hours_of_precipitation = self._extract_labeled_float(text, "Hours of Precipitation")
        record.hours_of_rain = self._extract_labeled_float(text, "Hours of Rain")
        return record

    @staticmethod
    def _is_compact_ten_day_card_text(text: str) -> bool:
        return bool(
            re.search(r"\b(?:MON|TUE|WED|THU|FRI|SAT|SUN)\s+\d{1,2}/\d{1,2}\b", text, re.I)
            and re.search(r"-?\d+(?:\.\d+)?\s*°\s*/\s*-?\d+(?:\.\d+)?\s*°", text)
        )

    def _record_from_compact_ten_day_text(self, text: str) -> WeatherRecord:
        text = self._normalize_weather_text(text)
        displayed_celsius = self._extract_primary_displayed_celsius(text)
        low_celsius = self._extract_low_displayed_celsius(text)
        record = self._build_record(
            self._extract_compact_daily_date(text),
            "Day",
            celsius_to_fahrenheit(displayed_celsius),
            displayed_celsius,
            self._extract_compact_daily_weather(text),
            None,
            None,
            self._extract_precipitation_probability(text),
            require_realfeel=False,
            require_humidity=False,
        )
        record.low_temperature_c_displayed = low_celsius
        record.low_temperature_f = celsius_to_fahrenheit(low_celsius)
        return record

    @staticmethod
    def _is_half_day_card_text(text: str) -> bool:
        return bool(re.match(r"^(Day|Night)\b", text, re.I)) and "RealFeel" in text

    def _build_record(
        self,
        date: str,
        period: str,
        temperature_f: Optional[float],
        displayed_celsius: Optional[float],
        weather: Optional[str],
        realfeel_f: Optional[float],
        humidity: Optional[int],
        precipitation_probability: Optional[int] = None,
        require_realfeel: bool = True,
        require_humidity: bool = True,
    ) -> WeatherRecord:
        calculated_celsius, validation_status = build_temperature_validation(
            temperature_f, displayed_celsius
        )
        required_fields = {
            "date": date,
            "temperature_f": temperature_f,
            "weather": weather,
        }
        if require_realfeel:
            required_fields["realfeel_f"] = realfeel_f
        if require_humidity:
            required_fields["humidity"] = humidity
        missing = [field for field, value in required_fields.items() if value in [None, ""]]
        error_message = f"Missing fields: {', '.join(missing)}" if missing else None
        return WeatherRecord(
            date=date,
            period=period,
            temperature_f=temperature_f,
            temperature_c_calculated=calculated_celsius,
            temperature_c_displayed=displayed_celsius,
            weather=weather,
            realfeel_f=realfeel_f,
            humidity=humidity,
            validation_status=validation_status,
            precipitation_probability=precipitation_probability,
            error_message=error_message,
        )

    def _records_from_time_of_day_sections(
        self,
        base_record: WeatherRecord,
        text: str,
    ) -> list[WeatherRecord]:
        labels = ["Morning", "Afternoon"] if base_record.period == "Day" else ["Evening", "Overnight"]
        section_records = []

        for label in labels:
            section_text = self._extract_time_of_day_section(text, label, labels)
            if not section_text:
                continue
            record = self._record_from_time_of_day_section(base_record, label, section_text)
            if record:
                section_records.append(record)

        return section_records or [base_record]

    def _record_from_time_of_day_section(
        self,
        base_record: WeatherRecord,
        label: str,
        section_text: str,
    ) -> Optional[WeatherRecord]:
        humidity = self._extract_humidity(section_text)
        if humidity is None:
            return None
        return replace(
            base_record,
            period=label,
            humidity=humidity,
            error_message=None,
        )

    @staticmethod
    def _extract_time_of_day_section(text: str, label: str, labels: list[str]) -> str:
        next_labels = [item for item in labels if item.lower() != label.lower()]
        next_label_pattern = "|".join(re.escape(item) for item in next_labels)
        if next_label_pattern:
            pattern = rf"\b{re.escape(label)}\b(.+?)(?=\b(?:{next_label_pattern})\b|$)"
        else:
            pattern = rf"\b{re.escape(label)}\b(.+)$"
        match = re.search(pattern, text, re.I)
        return DailyForecastPage._clean_text(match.group(1)) if match else ""

    @staticmethod
    def _limit_records_by_unique_dates(records: list[WeatherRecord], max_days: int) -> list[WeatherRecord]:
        if max_days <= 0:
            return []

        limited_records: list[WeatherRecord] = []
        seen_dates: set[str] = set()
        for record in records:
            if record.date not in seen_dates and len(seen_dates) >= max_days:
                break
            seen_dates.add(record.date)
            limited_records.append(record)
        return limited_records

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _is_forecast_range_text(text: str) -> bool:
        return bool(
            re.search(
                r"\b([A-Z][a-z]+|[A-Z]{3,9})\s+\d{1,2}\s*-\s*([A-Z][a-z]+|[A-Z]{3,9})\s+\d{1,2}\b",
                text,
                re.I,
            )
        )

    @staticmethod
    def _normalize_forecast_range_text(text: str) -> str:
        def title_month(match):
            return f"{match.group(1).title()} {match.group(2)}"

        text = re.sub(r"\b([A-Z]{3,9})\s+(\d{1,2})\b", title_month, text)
        return DailyForecastPage._clean_text(text)

    @staticmethod
    def _normalize_weather_text(text: str) -> str:
        return text.replace("Â°", "°").replace("Â®", "®").replace("â„¢", "™")

    @staticmethod
    def _extract_compact_daily_date(text: str) -> str:
        match = re.search(
            r"\b((?:MON|TUE|WED|THU|FRI|SAT|SUN|TONIGHT)\s+\d{1,2}/\d{1,2})\b",
            text,
            re.I,
        )
        return match.group(1).upper() if match else DailyForecastPage._extract_date(text)

    @staticmethod
    def _extract_daily_high_celsius(text: str) -> Optional[float]:
        match = re.search(r"\b(-?\d+(?:\.\d+)?)\s*(?:Â°|°)", text)
        return float(match.group(1)) if match else None

    @staticmethod
    def _extract_expanded_daily_weather(text: str) -> Optional[str]:
        match = re.search(r"\d{1,3}\s*%\s+(.+?)\s+RealFeel", text, re.I)
        if match:
            return DailyForecastPage._clean_text(match.group(1))
        match = re.search(
            r"(?:Â°|°)\s*(?:/\s*-?\d+(?:\.\d+)?\s*(?:Â°|°)?)?\s+(.+?)\s+RealFeel",
            text,
            re.I,
        )
        return DailyForecastPage._clean_text(match.group(1)) if match else None

    @staticmethod
    def _extract_compact_daily_weather(text: str) -> Optional[str]:
        match = re.search(
            r"\b(?:MON|TUE|WED|THU|FRI|SAT|SUN)\s+\d{1,2}/\d{1,2}\s+"
            r"-?\d+(?:\.\d+)?\s*°\s*/\s*-?\d+(?:\.\d+)?\s*°\s+"
            r"(?:\d{1,3}\s*%\s+)?(.+?)(?:\s+\d{1,3}\s*%|$)",
            text,
            re.I,
        )
        if not match:
            return DailyForecastPage._extract_weather(text)
        weather = DailyForecastPage._clean_text(match.group(1))
        if re.fullmatch(r"\d{1,3}\s*%", weather):
            return DailyForecastPage._extract_weather(text)
        return weather

    @staticmethod
    def _extract_precipitation_probability(text: str) -> Optional[int]:
        match = re.search(r"\b(\d{1,3})\s*%", text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_ten_day_percentage(text: str) -> Optional[int]:
        return DailyForecastPage._extract_precipitation_probability(text)

    @staticmethod
    def _extract_period_text(text: str, start_period: str, end_period: Optional[str]) -> str:
        start_match = re.search(rf"\b{re.escape(start_period)}\b", text, re.I)
        if not start_match:
            return text if start_period == "Day" else ""

        start_index = start_match.start()
        if not end_period:
            return text[start_index:]

        remaining_text = text[start_match.end():]
        end_match = re.search(rf"\b{re.escape(end_period)}\b", remaining_text, re.I)
        if not end_match:
            return text[start_index:]
        return text[start_index : start_match.end() + end_match.start()]

    @staticmethod
    def _extract_date(text: str) -> str:
        numeric_match = re.search(r"\b\d{1,2}/\d{1,2}\b", text)
        if numeric_match:
            return numeric_match.group(0)
        match = re.search(
            r"([A-Z][a-z]+,\s+[A-Z][a-z]+\s+\d{1,2}|[A-Z][a-z]+\s+\d{1,2})",
            text,
        )
        return match.group(1) if match else "Unavailable"

    @staticmethod
    def _full_date_from_numeric_date(value: str) -> str:
        match = re.search(r"\b(\d{1,2})/(\d{1,2})\b", value or "")
        if not match:
            return value

        month, day = int(match.group(1)), int(match.group(2))
        try:
            parsed = datetime(datetime.now().year, month, day)
        except ValueError:
            return value
        return f"{parsed.strftime('%A')}, {parsed.strftime('%B')} {parsed.day}"

    @staticmethod
    def _extract_fahrenheit_values(text: str) -> list[float]:
        return [float(value) for value in re.findall(r"(-?\d+(?:\.\d+)?)\s*°?\s*F\b", text)]

    @staticmethod
    def _extract_celsius_values(text: str) -> list[float]:
        return [float(value) for value in re.findall(r"(-?\d+(?:\.\d+)?)\s*°?\s*C\b", text)]

    @staticmethod
    def _extract_primary_displayed_celsius(text: str) -> Optional[float]:
        match = re.search(r"\b(-?\d+(?:\.\d+)?)\s*°\s*(?:Hi|Lo)?", text)
        return float(match.group(1)) if match else None

    @staticmethod
    def _extract_low_displayed_celsius(text: str) -> Optional[float]:
        match = re.search(r"/\s*(-?\d+(?:\.\d+)?)\s*°", text)
        return float(match.group(1)) if match else None

    @staticmethod
    def _strip_secondary_temperature_fields(text: str) -> str:
        return re.sub(
            r"RealFeel(?:®|[A-Za-z\s]*)?\s*-?\d+(?:\.\d+)?\s*°?\s*[FC]\b",
            "",
            text,
            flags=re.I,
        )

    @staticmethod
    def _extract_realfeel(text: str) -> Optional[float]:
        match = re.search(r"RealFeel(?:®|[A-Za-z\s]*)?\s*(-?\d+(?:\.\d+)?)\s*°?\s*F", text, re.I)
        return float(match.group(1)) if match else None

    @staticmethod
    def _extract_realfeel_celsius(text: str) -> Optional[float]:
        match = re.search(r"RealFeel(?:®|[A-Za-z\s]*)?\s*(-?\d+(?:\.\d+)?)\s*°", text, re.I)
        return float(match.group(1)) if match else None

    @staticmethod
    def _extract_realfeel_shade_celsius(text: str) -> Optional[float]:
        match = re.search(r"RealFeel Shade(?:™|[A-Za-z\s]*)?\s*(-?\d+(?:\.\d+)?)\s*°", text, re.I)
        return float(match.group(1)) if match else None

    @staticmethod
    def _extract_labeled_value(text: str, label: str) -> Optional[str]:
        label_pattern = re.escape(label)
        next_labels = (
            "RealFeel Shade|Max UV Index|AccuLumen Brightness Index|Wind Gusts|Wind|"
            "Hours of Precipitation|Hours of Rain|Cloud Cover|Rain|Precipitation|Thunderstorms"
        )
        match = re.search(rf"{label_pattern}\s+(.+?)(?=\s+(?:{next_labels})\b|$)", text, re.I)
        return DailyForecastPage._clean_text(match.group(1)) if match else None

    @staticmethod
    def _extract_labeled_float(text: str, label: str) -> Optional[float]:
        value = DailyForecastPage._extract_labeled_value(text, label)
        if value is None:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        return float(match.group(0)) if match else None

    @staticmethod
    def _extract_labeled_percentage(text: str, labels: list[str]) -> Optional[int]:
        for label in labels:
            value = DailyForecastPage._extract_labeled_value(text, label)
            if value is None:
                continue
            match = re.search(r"\b(\d{1,3})\s*%", value)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _extract_humidity(text: str) -> Optional[int]:
        match = re.search(r"Humidity\s*(\d{1,3})\s*%", text, re.I)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_weather(text: str) -> Optional[str]:
        known_conditions = [
            "Cloudy",
            "Mostly cloudy",
            "Partly cloudy",
            "Sunny",
            "Mostly sunny",
            "Rain",
            "Showers",
            "Thunderstorms",
            "Humid",
            "Clear",
            "Overcast",
            "Windy",
        ]
        lowered = text.lower()
        for condition in known_conditions:
            if condition.lower() in lowered:
                return condition
        return None

    @staticmethod
    def _extract_weather_phrase_from_half_day(text: str) -> Optional[str]:
        match = re.search(
            r"RealFeel(?:®|[A-Za-z\s]*)?\s*-?\d+(?:\.\d+)?\s*°\s*"
            r"(?:RealFeel Shade[™A-Za-z\s]*\s*-?\d+(?:\.\d+)?\s*°\s*)?"
            r"(.+?)\s+(?:Max UV Index|Wind|Precipitation|Rain|Cloud Cover)\b",
            text,
            re.I,
        )
        return DailyForecastPage._clean_text(match.group(1)) if match else None
