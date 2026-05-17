from __future__ import annotations

import random
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from config import settings
from models.city_target import CityTarget
from models.weather_record import WeatherRecord
from pages.daily_forecast_page import DailyForecastPage
from services.report_service import ReportService
from utils.file_writer import write_csv, write_json
from utils.logger import get_logger


def _scrape_detail_url_batch(detail_urls: list[str]) -> list[WeatherRecord]:
    from playwright.sync_api import sync_playwright

    logger = get_logger("ParallelDayWorker")
    records: list[WeatherRecord] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=settings.HEADLESS,
            args=[
                "--incognito",
                "--disable-blink-features=AutomationControlled",
                "--disable-http2",
                "--disable-quic",
                "--start-maximized",
            ],
        )
        context = browser.new_context(
            ignore_https_errors=True,
            no_viewport=True,
            locale="en-US",
            timezone_id="Asia/Bangkok",
            extra_http_headers={
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        forecast_page = DailyForecastPage(page)
        for detail_url in detail_urls:
            try:
                forecast_page.goto(detail_url, "open parallel day detail URL")
                day_records = forecast_page.extract_detail_weather_records_with_retry()
                logger.info("Collected %s records from %s", len(day_records), detail_url)
                records.extend(day_records)
            except Exception as error:
                logger.warning("Parallel detail extraction failed for %s: %s", detail_url, error)
                records.append(
                    WeatherRecord(
                        date=detail_url,
                        period="Unknown",
                        temperature_f=None,
                        temperature_c_calculated=None,
                        temperature_c_displayed=None,
                        weather=None,
                        realfeel_f=None,
                        humidity=None,
                        validation_status="EXTRACTION_ERROR",
                        error_message=str(error),
                    )
                )
        context.close()
        browser.close()
    return records


class WeatherScraper:
    def __init__(
        self,
        page,
        city: Optional[str] = None,
        country: Optional[str] = None,
        location_url: Optional[str] = None,
        output_slug: Optional[str] = None,
    ):
        self.page = page
        self.city = city or settings.CITY
        self.country = country or settings.COUNTRY
        self.location_url = location_url if location_url is not None else settings.LOCATION_URL
        self.output_slug = output_slug
        self.logger = get_logger(self.__class__.__name__)

    def find_and_search_local_city(self) -> dict[str, Path | int | str]:
        """Find the local city based on IP geolocation and search for its weather."""
        self._detect_local_city()
        return self.run()

    def _detect_local_city(self):
        """Detect the user's local city and country using IP geolocation."""
        try:
            response = requests.get('http://ipapi.co/json/', timeout=10)
            response.raise_for_status()
            data = response.json()
            detected_city = data.get('city')
            detected_country = data.get('country_name')
            if detected_city and detected_country:
                self.city = detected_city
                self.country = detected_country
                self.logger.info(f"Detected local city: {self.city}, {self.country}")
            else:
                self.logger.warning("Could not detect city or country from IP geolocation, using defaults")
        except Exception as e:
            self.logger.warning(f"Failed to detect local city: {e}, using defaults")

    def run(self) -> dict[str, Path | int | str]:
        page = DailyForecastPage(self.page)
        try:
            if self.location_url:
                page.open_location_url(self.location_url)
            else:
                fallback_url = self._configured_location_url()
                if fallback_url:
                    ten_day_url = self._ten_day_url_from_location_url(fallback_url)
                    self.logger.info(
                        "Using configured 10-day city URL for %s, %s: %s",
                        self.city,
                        self.country,
                        ten_day_url,
                    )
                    page.open_location_url(ten_day_url)
                else:
                    self._open_location_from_homepage_search(page)
            try:
                page.open_daily_forecast()
            except Exception as error:
                self.logger.warning(
                    "Failed to open 10-day forecast after retries: %s. Continuing with available page content.",
                    error,
                )
            forecast_range = page.ensure_ten_day_forecast_range()
            if settings.PARALLEL_DAY_WORKERS > 1 and page._is_ten_day_url(self._page_url(page)):
                detail_urls = page.collect_ten_day_detail_urls(settings.FORECAST_DAYS)
                records = self._scrape_detail_urls_parallel(detail_urls)
            else:
                records = page.extract_all_available_weather_records(settings.FORECAST_DAYS)
            extracted_at = datetime.now().isoformat(timespec="seconds")
            self._annotate_records(records, extracted_at)
            expected_dates = self._expected_dates_from_forecast_range(forecast_range, settings.FORECAST_DAYS)
            missing_dates = self._missing_forecast_dates(records, expected_dates)
            missing_sections = self._missing_forecast_sections(records, expected_dates)
            date_range_valid = bool(expected_dates)

            csv_path = write_csv(records, self._output_path("weather_data.csv", settings.OUTPUT_DIR))
            json_path = write_json(records, self._output_path("weather_data.json", settings.OUTPUT_DIR))
            report_path = ReportService().generate_summary(
                records,
                city=f"{self.city}, {self.country}".strip(", "),
                forecast_range=forecast_range,
                missing_dates=missing_dates,
                missing_sections=missing_sections,
                output_path=self._summary_report_path(),
            )

            self.logger.info("CSV file generated: %s", csv_path)
            self.logger.info("JSON file generated: %s", json_path)
            self.logger.info("Summary report generated: %s", report_path)

            return {
                "record_count": len(records),
                "forecast_range": forecast_range,
                "date_range_valid": date_range_valid,
                "expected_dates": expected_dates,
                "missing_dates": missing_dates,
                "missing_sections": missing_sections,
                "csv_path": csv_path,
                "json_path": json_path,
                "report_path": report_path,
            }
        except Exception:
            screenshot_path = self._failure_screenshot_path()
            try:
                page.take_screenshot(screenshot_path)
                self.logger.exception("Weather scraper failed; screenshot saved to %s", screenshot_path)
            except Exception as screenshot_error:
                self.logger.exception(
                    "Weather scraper failed; screenshot capture also failed: %s",
                    screenshot_error,
                )
            raise

    def _open_location_from_homepage_search(self, page: DailyForecastPage) -> None:
        try:
            page.open_homepage()
            page.search_location(self.city, self.country)
            current_url = self._page_url(page)
            if self._is_search_results_url(current_url) or not self._is_weather_page_url(current_url):
                fallback_url = self._configured_location_url()
                if not fallback_url:
                    raise RuntimeError(f"Search did not select a city page: {current_url}")
                ten_day_url = self._ten_day_url_from_location_url(fallback_url)
                self.logger.warning(
                    "Search did not select a forecast page; opening configured 10-day city URL instead: %s",
                    ten_day_url,
                )
                page.open_location_url(ten_day_url)
        except Exception as error:
            fallback_url = self._configured_location_url()
            if not fallback_url:
                raise
            ten_day_url = self._ten_day_url_from_location_url(fallback_url)
            self.logger.warning(
                "Homepage search failed; opening configured 10-day city URL instead: %s. Cause: %s",
                ten_day_url,
                error,
            )
            page.open_location_url(ten_day_url)

    @staticmethod
    def _page_url(page: DailyForecastPage) -> str:
        if hasattr(page, "_current_url"):
            return page._current_url()
        return getattr(page.page, "url", "")

    def _output_path(self, filename: str, directory: Path) -> Path:
        if not self.output_slug:
            return directory / filename
        return directory / self.output_slug / filename

    def _annotate_records(self, records: list[WeatherRecord], extracted_at: str) -> None:
        city = f"{self.city}, {self.country}".strip(", ")
        for record in records:
            record.city = city
            record.extracted_at = extracted_at

    def _failure_screenshot_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        context_slug = self._context_slug()
        filename = f"failure_{context_slug}_{timestamp}.png" if context_slug else f"failure_{timestamp}.png"
        return settings.SCREENSHOT_DIR / filename

    def _summary_report_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        context_slug = self._context_slug()
        filename = (
            f"summary_report_{context_slug}_{timestamp}.html"
            if context_slug
            else f"summary_report_{timestamp}.html"
        )
        return self._output_path(filename, settings.REPORT_DIR)

    def _context_slug(self) -> str:
        return self.output_slug or self._slugify("-".join([self.city, self.country]).strip("-"))

    @staticmethod
    def _slugify(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    def _configured_location_url(self) -> Optional[str]:
        city = self.city.strip().lower()
        country = self.country.strip().lower()
        for target in settings.CITY_TARGETS:
            if target.name.lower() == city and target.country.lower() == country:
                return target.location_url
        return None

    @staticmethod
    def _ten_day_url_from_location_url(location_url: str) -> str:
        if "/10-day-weather-forecast/" in location_url:
            return location_url
        if "/daily-weather-forecast/" in location_url:
            return location_url.replace("/daily-weather-forecast/", "/10-day-weather-forecast/")
        if "/weather-forecast/" in location_url:
            return location_url.replace("/weather-forecast/", "/10-day-weather-forecast/")
        return location_url

    def _scrape_detail_urls_parallel(self, detail_urls: list[str]) -> list[WeatherRecord]:
        if not detail_urls:
            return []

        worker_count = min(settings.PARALLEL_DAY_WORKERS, len(detail_urls))
        batches = self._chunk_urls(detail_urls, worker_count)
        self.logger.info(
            "Scraping %s detail URLs with %s parallel workers",
            len(detail_urls),
            worker_count,
        )

        batch_results: dict[int, list[WeatherRecord]] = {}
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_scrape_detail_url_batch, batch): batch_index
                for batch_index, batch in enumerate(batches)
            }
            for future in as_completed(futures):
                batch_index = futures[future]
                batch_results[batch_index] = future.result()

        records: list[WeatherRecord] = []
        for batch_index in sorted(batch_results):
            records.extend(batch_results[batch_index])
        self.logger.info("Parallel detail scraping collected %s records", len(records))
        return records

    @staticmethod
    def _chunk_urls(urls: list[str], worker_count: int) -> list[list[str]]:
        chunks = [[] for _ in range(worker_count)]
        for index, url in enumerate(urls):
            chunks[index % worker_count].append(url)
        return [chunk for chunk in chunks if chunk]

    @staticmethod
    def _is_search_results_url(url: str) -> bool:
        return "/search-locations" in url

    @staticmethod
    def _is_weather_page_url(url: str) -> bool:
        weather_paths = [
            "/weather-forecast/",
            "/daily-weather-forecast/",
            "/10-day-weather-forecast/",
        ]
        return any(path in url for path in weather_paths)

    @staticmethod
    def _expected_dates_from_forecast_range(forecast_range: str, days: int) -> list[str]:
        if days <= 0:
            return []

        match = re.search(
            r"\b([A-Z][a-z]+)\s+(\d{1,2})\s*-\s*([A-Z][a-z]+)\s+(\d{1,2})\b",
            forecast_range,
        )
        if not match:
            return []

        start_month, start_day, end_month, end_day = match.groups()
        current_year = datetime.now().year
        try:
            start_date = datetime.strptime(f"{start_month} {start_day} {current_year}", "%B %d %Y").date()
            end_date = datetime.strptime(f"{end_month} {end_day} {current_year}", "%B %d %Y").date()
        except ValueError:
            return []

        if end_date < start_date:
            end_date = date(end_date.year + 1, end_date.month, end_date.day)

        available_days = (end_date - start_date).days + 1
        expected_count = min(days, available_days)
        return [
            WeatherScraper._format_month_day(start_date + timedelta(days=offset))
            for offset in range(expected_count)
        ]

    @staticmethod
    def _missing_forecast_dates(records, expected_dates: list[str]) -> list[str]:
        actual_dates = {
            normalized
            for record in records
            for normalized in [WeatherScraper._normalize_record_date(record.date)]
            if normalized
        }
        return [expected_date for expected_date in expected_dates if expected_date not in actual_dates]

    @staticmethod
    def _missing_forecast_sections(records, expected_dates: list[str]) -> list[str]:
        actual = set()
        for record in records:
            normalized_date = WeatherScraper._normalize_record_date(record.date)
            if normalized_date and record.period:
                actual.add((normalized_date, record.period))

        missing = []
        for expected_date in expected_dates:
            for section in WeatherScraper._expected_sections_for_date(expected_date):
                if (expected_date, section) not in actual:
                    missing.append(f"{expected_date} {section}")
        return missing

    @staticmethod
    def _expected_sections_for_date(expected_date: str) -> list[str]:
        return ["Morning", "Afternoon", "Evening", "Overnight"]

    @staticmethod
    def _normalize_record_date(value: str) -> Optional[str]:
        match = re.search(r"\b(\d{1,2})/(\d{1,2})\b", value or "")
        if match:
            return f"{int(match.group(1))}/{int(match.group(2))}"

        match = re.search(r"\b[A-Z][a-z]+,\s+([A-Z][a-z]+)\s+(\d{1,2})\b", value or "")
        if not match:
            return None

        try:
            parsed = datetime.strptime(f"{match.group(1)} {match.group(2)}", "%B %d")
        except ValueError:
            return None
        return f"{parsed.month}/{parsed.day}"

    @staticmethod
    def _format_month_day(value: date) -> str:
        return f"{value.month}/{value.day}"


class RandomCityWeatherScraper:
    def __init__(
        self,
        page,
        city_targets: Optional[list[CityTarget]] = None,
        city_count: Optional[int] = None,
        random_seed: Optional[str] = None,
    ):
        self.page = page
        self.city_targets = city_targets or settings.CITY_TARGETS
        self.city_count = city_count if city_count is not None else settings.RANDOM_CITY_COUNT
        self.random_seed = random_seed if random_seed is not None else settings.RANDOM_SEED
        self.logger = get_logger(self.__class__.__name__)

    def select_cities(self) -> list[CityTarget]:
        if self.city_count > len(self.city_targets):
            raise ValueError(
                f"RANDOM_CITY_COUNT={self.city_count} exceeds configured city pool size "
                f"({len(self.city_targets)})"
            )

        rng = random.Random(self.random_seed or None)
        return rng.sample(self.city_targets, self.city_count)

    def run(self) -> list[dict[str, Path | int | str]]:
        results = []
        for target in self.select_cities():
            self.logger.info("Running weather extraction for random city: %s", target.display_name)
            result = WeatherScraper(
                self.page,
                city=target.name,
                country=target.country,
                location_url="",
                output_slug=target.slug,
            ).run()
            result["city"] = target.display_name
            results.append(result)
        return results
