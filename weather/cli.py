from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from playwright.sync_api import sync_playwright


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def parse_cli_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise argparse.ArgumentTypeError(
        "Expected one of: true, false, 1, 0, yes, no, on, off"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m weather",
        description="Run AccuWeather extraction and generate CSV, JSON, and HTML outputs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one weather extraction.")
    run_parser.add_argument("--city", help="City name to search.")
    run_parser.add_argument("--country", help="Country name to match.")
    run_parser.add_argument(
        "--location-url",
        help="AccuWeather forecast URL to open directly instead of using search.",
    )
    run_parser.add_argument(
        "--headless",
        type=parse_cli_bool,
        help="Run browser headlessly. Accepts true/false, 1/0, yes/no, on/off.",
    )
    run_parser.add_argument(
        "--forecast-days",
        type=int,
        help="Number of forecast days to extract. Maximum is 10.",
    )
    run_parser.add_argument(
        "--parallel-day-workers",
        type=int,
        help="Number of parallel detail-page workers. Use 1 for sequential debugging.",
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for generated CSV and JSON files.",
    )
    run_parser.add_argument(
        "--report-dir",
        type=Path,
        help="Directory for generated HTML reports and logs.",
    )
    run_parser.add_argument(
        "--local-city",
        action="store_true",
        help="Detect approximate city from IP geolocation before scraping.",
    )
    run_parser.set_defaults(func=run_weather)
    return parser


def apply_run_overrides(args: argparse.Namespace) -> None:
    overrides = {
        "CITY": args.city,
        "COUNTRY": args.country,
        "LOCATION_URL": args.location_url,
        "FORECAST_DAYS": str(args.forecast_days) if args.forecast_days is not None else None,
        "PARALLEL_DAY_WORKERS": (
            str(args.parallel_day_workers) if args.parallel_day_workers is not None else None
        ),
        "OUTPUT_DIR": str(args.output_dir) if args.output_dir is not None else None,
        "REPORT_DIR": str(args.report_dir) if args.report_dir is not None else None,
    }
    if args.headless is not None:
        overrides["HEADLESS"] = "true" if args.headless else "false"

    for name, value in overrides.items():
        if value is not None:
            os.environ[name] = value


def run_weather(args: argparse.Namespace) -> int:
    apply_run_overrides(args)

    from services.weather_scraper import WeatherScraper

    try:
        with sync_playwright() as playwright:
            from config import settings
            from utils.browser_config import (
                apply_stealth_context,
                browser_context_options,
                launch_browser,
            )

            browser = launch_browser(playwright.chromium)
            context = browser.new_context(**browser_context_options())
            apply_stealth_context(context)
            page = context.new_page()
            try:
                scraper = WeatherScraper(page)
                result = (
                    scraper.find_and_search_local_city()
                    if args.local_city
                    else scraper.run()
                )
            finally:
                context.close()
                browser.close()
    except Exception as error:
        location = _requested_location(args)
        print(f"Weather extraction failed for {location}: {error}", file=sys.stderr)
        print(
            "Try a different city/country pair or pass --location-url with a direct AccuWeather forecast page.",
            file=sys.stderr,
        )
        return 1

    print(f"Records: {result['record_count']}")
    print(f"CSV: {result['csv_path']}")
    print(f"JSON: {result['json_path']}")
    print(f"Report: {result['report_path']}")
    if result.get("missing_dates"):
        print(f"Missing dates: {', '.join(result['missing_dates'])}")
    if result.get("missing_sections"):
        print(f"Missing sections: {', '.join(result['missing_sections'])}")
    return 0


def _requested_location(args: argparse.Namespace) -> str:
    if args.local_city:
        return "the detected local city"
    if args.location_url:
        return args.location_url
    city = args.city or os.getenv("CITY") or "configured city"
    country = args.country or os.getenv("COUNTRY") or ""
    return ", ".join(part for part in [city, country] if part)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
