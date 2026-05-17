import argparse
import os

import pytest

from weather import cli
from weather.cli import apply_run_overrides, build_parser, parse_cli_bool


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", " TRUE "])
def test_parse_cli_bool_accepts_true_values(value):
    assert parse_cli_bool(value)


@pytest.mark.parametrize("value", ["false", "0", "no", "off", " FALSE "])
def test_parse_cli_bool_accepts_false_values(value):
    assert not parse_cli_bool(value)


def test_parse_cli_bool_rejects_unknown_value():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_cli_bool("sometimes")


def test_run_parser_accepts_city_country_and_runtime_options():
    args = build_parser().parse_args(
        [
            "run",
            "--city",
            "Ho Chi Minh City",
            "--country",
            "Vietnam",
            "--headless",
            "false",
            "--forecast-days",
            "3",
            "--parallel-day-workers",
            "1",
            "--output-dir",
            "out-data",
            "--report-dir",
            "out-reports",
        ]
    )

    assert args.command == "run"
    assert args.city == "Ho Chi Minh City"
    assert args.country == "Vietnam"
    assert args.headless is False
    assert args.forecast_days == 3
    assert args.parallel_day_workers == 1
    assert str(args.output_dir) == "out-data"
    assert str(args.report_dir) == "out-reports"


def test_apply_run_overrides_sets_only_provided_environment_values(monkeypatch):
    args = build_parser().parse_args(
        [
            "run",
            "--city",
            "Tokyo",
            "--country",
            "Japan",
            "--headless",
            "true",
            "--forecast-days",
            "2",
        ]
    )
    monkeypatch.delenv("LOCATION_URL", raising=False)

    apply_run_overrides(args)

    assert os.environ["CITY"] == "Tokyo"
    assert os.environ["COUNTRY"] == "Japan"
    assert os.environ["HEADLESS"] == "true"
    assert os.environ["FORECAST_DAYS"] == "2"
    assert "LOCATION_URL" not in os.environ


def test_run_weather_returns_one_with_friendly_message_when_extraction_fails(
    monkeypatch,
    capsys,
):
    class FailingPlaywright:
        @property
        def chromium(self):
            raise RuntimeError("No location search result matched Atlantis")

    class FailingPlaywrightContext:
        def __enter__(self):
            return FailingPlaywright()

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    monkeypatch.setattr(cli, "sync_playwright", lambda: FailingPlaywrightContext(), raising=False)

    args = build_parser().parse_args(
        ["run", "--city", "Atlantis", "--country", "Ocean"]
    )

    assert cli.run_weather(args) == 1
    error_output = capsys.readouterr().err
    assert "Weather extraction failed for Atlantis, Ocean" in error_output
    assert "No location search result matched Atlantis" in error_output
    assert "--location-url" in error_output
