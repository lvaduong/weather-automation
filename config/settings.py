from __future__ import annotations

import os
from pathlib import Path

from models.city_target import CityTarget


ROOT_DIR = Path(__file__).resolve().parents[1]

BASE_URL = os.getenv("BASE_URL", "https://www.accuweather.com")
LOCATION_URL = os.getenv("LOCATION_URL", "")
CITY = os.getenv("CITY", "Ho Chi Minh City")
COUNTRY = os.getenv("COUNTRY", "Vietnam")
TEMPERATURE_TOLERANCE = float(os.getenv("TEMPERATURE_TOLERANCE", "1.0"))
MAX_FORECAST_DAYS = 10


def parse_bool(raw_value: str | None, default: bool = False) -> bool:
    if raw_value is None or not raw_value.strip():
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {raw_value!r}")


def parse_positive_int(raw_value: str | None, default: int, name: str) -> int:
    if raw_value is None or not raw_value.strip():
        return default
    value = int(raw_value)
    if value < 0:
        raise ValueError(f"{name} must be zero or a positive integer")
    return value


def parse_forecast_days(raw_value: str | None) -> int:
    if not raw_value or not raw_value.strip():
        return MAX_FORECAST_DAYS

    forecast_days = int(raw_value)
    if forecast_days <= 0:
        raise ValueError("FORECAST_DAYS must be a positive integer")
    if forecast_days > MAX_FORECAST_DAYS:
        raise ValueError(
            f"FORECAST_DAYS={forecast_days} exceeds the supported 10-day forecast limit"
        )
    return forecast_days


HEADLESS = parse_bool(os.getenv("HEADLESS"), default=True)
FORECAST_DAYS = parse_forecast_days(os.getenv("FORECAST_DAYS", str(MAX_FORECAST_DAYS)))
PARALLEL_DAY_WORKERS = parse_positive_int(os.getenv("PARALLEL_DAY_WORKERS"), 3, "PARALLEL_DAY_WORKERS")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT_DIR / "data"))
REPORT_DIR = Path(os.getenv("REPORT_DIR", ROOT_DIR / "reports"))
SCREENSHOT_DIR = REPORT_DIR / "screenshots"
TRACE_DIR = REPORT_DIR / "traces"
DEFAULT_TIMEOUT_MS = int(os.getenv("DEFAULT_TIMEOUT_MS", "30000"))
PAGE_LOAD_TIMEOUT_MS = int(os.getenv("PAGE_LOAD_TIMEOUT_MS", "10000"))
SCREENSHOT_TIMEOUT_MS = int(os.getenv("SCREENSHOT_TIMEOUT_MS", "5000"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_DELAY_MS = int(os.getenv("RETRY_DELAY_MS", "2000"))
RANDOM_CITY_COUNT = parse_positive_int(os.getenv("RANDOM_CITY_COUNT"), 0, "RANDOM_CITY_COUNT")
RANDOM_SEED = os.getenv("RANDOM_SEED", "")


DEFAULT_CITY_TARGETS = [
    CityTarget(
        "Ho Chi Minh City",
        "Vietnam",
        "https://www.accuweather.com/en/vn/ho-chi-minh-city/353981/weather-forecast/353981",
    ),
    CityTarget(
        "New York",
        "United States",
        "https://www.accuweather.com/en/us/new-york/10007/weather-forecast/349727",
    ),
    CityTarget(
        "London",
        "United Kingdom",
        "https://www.accuweather.com/en/gb/london/ec4a-2/weather-forecast/328328",
    ),
    CityTarget(
        "Tokyo",
        "Japan",
        "https://www.accuweather.com/en/jp/tokyo/226396/weather-forecast/226396",
    ),
    CityTarget(
        "Singapore",
        "Singapore",
        "https://www.accuweather.com/en/sg/singapore/300597/weather-forecast/300597",
    ),
    CityTarget(
        "Sydney",
        "Australia",
        "https://www.accuweather.com/en/au/sydney/22889/weather-forecast/22889",
    ),
    CityTarget(
        "Paris",
        "France",
        "https://www.accuweather.com/en/fr/paris/623/weather-forecast/623",
    ),
]


def parse_city_targets(raw_value: str) -> list[CityTarget]:
    if not raw_value.strip():
        return DEFAULT_CITY_TARGETS

    targets = []
    for item in raw_value.split(";"):
        parts = [part.strip() for part in item.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                "CITY_TARGETS entries must use 'City|Country|AccuWeather URL' separated by semicolons"
            )
        targets.append(CityTarget(parts[0], parts[1], parts[2]))
    return targets


CITY_TARGETS = parse_city_targets(os.getenv("CITY_TARGETS", ""))
