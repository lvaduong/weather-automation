# Weather Automation

Python Playwright and Pytest framework for extracting AccuWeather 10-day forecast data, validating Fahrenheit-to-Celsius conversion, and generating CSV, JSON, and HTML reports.

## What This Project Demonstrates

- Playwright browser automation using a page object model.
- Deterministic unit tests separated from opt-in live browser tests.
- Environment-driven configuration with validation for common flags.
- Retry handling for flaky navigation and extraction steps.
- Weather data validation, structured file output, and HTML reporting.
- Scheduled CI execution through GitHub Actions.

## Project Structure

```text
config/                 Runtime settings from environment variables
models/                 Weather and city dataclasses
pages/                  Playwright page objects
services/               Scraper, validation, and report services
utils/                  File output, logging, and conversion helpers
tests/                  Unit and live browser tests
data/                   Generated CSV and JSON files, ignored by git
reports/                Generated reports, logs, screenshots, and traces, ignored by git
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Copy `.env.example` if you want local overrides, or set environment variables directly:

```bash
set CITY=Ho Chi Minh City
set COUNTRY=Vietnam
set HEADLESS=true
```

## Run Deterministic Tests

These tests validate conversion, file output, report generation, configuration parsing, city selection, and parser logic without opening AccuWeather:

```bash
pytest
```

Expected baseline:

```text
60+ passed, live tests skipped unless explicitly enabled
```

## Run Live AccuWeather Extraction

Live scraping is opt-in because AccuWeather layout, rate limits, and anti-bot behavior can change:

```bash
set RUN_LIVE_WEATHER_TESTS=true
python run_tests.py
```

For interview review, provide only the city and country. The CLI requests the full supported 10-day range by default, and built-in city targets use their configured AccuWeather 10-day URL directly:

```bash
python -m weather run --city "Ho Chi Minh City" --country Vietnam
```

The command writes the extracted records to `data/weather_data.csv`, `data/weather_data.json`, and a timestamped HTML summary report under `reports/`.

To make the 10-day behavior explicit while debugging, you can pass the same defaults yourself:

```bash
python -m weather run --city "Ho Chi Minh City" --country Vietnam --forecast-days 10 --parallel-day-workers 1 --headless true
```

Useful CLI options:

```bash
python -m weather run --city Tokyo --country Japan --forecast-days 3 --headless true
python -m weather run --location-url "https://www.accuweather.com/en/vn/ho-chi-minh-city/353981/weather-forecast/353981"
python -m weather run --local-city
```

Generated outputs:

- `data/weather_data.csv`
- `data/weather_data.json`
- `reports/summary_report_<city>_<timestamp>.html`
- `reports/report.html`
- `reports/weather_automation.log`
- `reports/screenshots/failure_<city>_<timestamp>.png` on scraper failure
- `reports/traces/` when live tests run through `run_tests.py`

The summary report includes a data-completeness section that lists missing forecast dates or missing time-of-day sections when extraction is partial.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `BASE_URL` | `https://www.accuweather.com` | AccuWeather base URL |
| `LOCATION_URL` | blank | Optional city forecast URL to bypass homepage search |
| `CITY` | `Ho Chi Minh City` | Default city |
| `COUNTRY` | `Vietnam` | Default country |
| `HEADLESS` | `true` | Accepts `true`, `false`, `1`, `0`, `yes`, `no`, `on`, `off` |
| `TEMPERATURE_TOLERANCE` | `1.0` | Celsius validation tolerance |
| `FORECAST_DAYS` | `10` | Maximum supported value is `10` |
| `PARALLEL_DAY_WORKERS` | `3` | Set to `1` for sequential click-through debugging |
| `RANDOM_CITY_COUNT` | `0` | Set to a positive number to enable random-city live tests |
| `RANDOM_SEED` | blank | Optional repeatable random selection seed |
| `CITY_TARGETS` | built-in city pool | Optional `City\|Country\|URL;City\|Country\|URL` list |
| `OUTPUT_DIR` | `data` | Generated CSV/JSON directory |
| `REPORT_DIR` | `reports` | Generated report/log directory |
| `RETRY_ATTEMPTS` | `3` | Navigation and extraction retry attempts |
| `RETRY_DELAY_MS` | `2000` | Delay between retries |

## Random City Live Runs

The random-city live test samples cities from the configured city pool, opens AccuWeather, searches by city name, and writes each city to its own output folder. It is disabled by default.

```bash
set RUN_LIVE_WEATHER_TESTS=true
set RANDOM_CITY_COUNT=3
set FORECAST_DAYS=10
pytest tests/test_weather_forecast_live.py --browser-channel=chrome --headed -s
```

Set `RANDOM_SEED` to repeat the same random city selection while debugging.

## Local City Detection

`WeatherScraper.find_and_search_local_city()` can detect an approximate city and country using the free `ipapi.co` geolocation API, then scrape weather for that location:

```python
from services.weather_scraper import WeatherScraper

scraper = WeatherScraper(page)
result = scraper.find_and_search_local_city()
```

## CI And Scheduling

GitHub Actions is included at `.github/workflows/weather-automation.yml` and runs hourly plus on manual dispatch.

Linux cron example:

```bash
0 * * * * cd /path/to/weather-automation && RUN_LIVE_WEATHER_TESTS=true python run_tests.py
```

## Notes For Reviewers

The deterministic suite is the stable interview baseline. Live tests prove the browser workflow, but they depend on AccuWeather availability and page structure, so they are intentionally gated by environment variables.
