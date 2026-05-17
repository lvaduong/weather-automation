import csv
import json
from pathlib import Path
from typing import Iterable

from models.weather_record import WeatherRecord


FIELDNAMES = [
    "city",
    "extracted_at",
    "date",
    "period",
    "temperature_f",
    "temperature_c_calculated",
    "temperature_c_displayed",
    "weather",
    "realfeel_f",
    "humidity",
    "precipitation_probability",
    "low_temperature_c_displayed",
    "low_temperature_f",
    "realfeel_shade_f",
    "wind",
    "max_uv_index",
    "hours_of_precipitation",
    "hours_of_rain",
    "validation_status",
    "error_message",
]


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_csv(records: Iterable[WeatherRecord], path: Path) -> Path:
    ensure_directory(path.parent)
    rows = [record.to_dict() for record in records]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_json(records: Iterable[WeatherRecord], path: Path) -> Path:
    ensure_directory(path.parent)
    rows = [record.to_dict() for record in records]
    with path.open("w", encoding="utf-8") as json_file:
        json.dump(rows, json_file, indent=2)
    return path
