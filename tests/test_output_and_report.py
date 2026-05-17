import json
import csv

from models.weather_record import WeatherRecord
from services.report_service import ReportService
from utils.file_writer import write_csv, write_json


def sample_records():
    return [
        WeatherRecord(
            date="Thursday, November 8",
            period="Morning",
            temperature_f=88,
            temperature_c_calculated=31.1,
            temperature_c_displayed=31,
            weather="Cloudy",
            realfeel_f=101,
            humidity=70,
            validation_status="PASSED",
            precipitation_probability=60,
            wind="SE 12 km/h",
            max_uv_index="6.0 (High)",
        ),
        WeatherRecord(
            date="Thursday, November 8",
            period="Afternoon",
            temperature_f=90,
            temperature_c_calculated=32.2,
            temperature_c_displayed=32,
            weather="Cloudy",
            realfeel_f=104,
            humidity=74,
            validation_status="PASSED",
        ),
        WeatherRecord(
            date="Thursday, November 8",
            period="Evening",
            temperature_f=72,
            temperature_c_calculated=22.2,
            temperature_c_displayed=None,
            weather="Clear",
            realfeel_f=75,
            humidity=80,
            validation_status="CALCULATED_ONLY",
            precipitation_probability=85,
            low_temperature_c_displayed=22,
            wind="SE 12 km/h",
        ),
        WeatherRecord(
            date="Thursday, November 8",
            period="Overnight",
            temperature_f=70,
            temperature_c_calculated=21.1,
            temperature_c_displayed=21,
            weather="Clear",
            realfeel_f=72,
            humidity=86,
            validation_status="PASSED",
        ),
    ]


def test_csv_and_json_outputs_are_generated(tmp_path):
    records = sample_records()
    records[0].city = "Ho Chi Minh City, Vietnam"
    records[0].extracted_at = "2026-05-15T21:45:39"
    csv_path = write_csv(records, tmp_path / "weather_data.csv")
    json_path = write_json(records, tmp_path / "weather_data.json")

    assert csv_path.exists()
    assert csv_path.stat().st_size > 0
    csv_rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    assert csv_rows[0]["city"] == "Ho Chi Minh City, Vietnam"
    assert csv_rows[0]["extracted_at"] == "2026-05-15T21:45:39"
    assert json_path.exists()
    json_rows = json.loads(json_path.read_text(encoding="utf-8"))
    assert json_rows[0]["weather"] == "Cloudy"
    assert json_rows[0]["city"] == "Ho Chi Minh City, Vietnam"
    assert json_rows[0]["extracted_at"] == "2026-05-15T21:45:39"


def test_summary_report_contains_daily_weather_fields(tmp_path):
    report_path = ReportService().generate_summary(
        sample_records(),
        city="Ho Chi Minh City, Vietnam",
        forecast_range="November 8 - December 22",
        missing_dates=["11/10"],
        missing_sections=["11/11 Morning", "11/11 Afternoon"],
        output_path=tmp_path / "summary_report.html",
    )

    content = report_path.read_text(encoding="utf-8")
    assert "Daily Forecast Summary Report" in content
    assert "Daily Forecast Summary" in content
    assert "Data Completeness" in content
    assert "Missing Dates:" in content
    assert "11/10" in content
    assert "Missing Sections:" in content
    assert "11/11 Morning, 11/11 Afternoon" in content
    assert "Temperature" in content
    assert "Morning: 31C | Afternoon: 32C | Evening: 22.2C | Overnight: 21C" in content
    assert "Main Weather Of The Day" in content
    assert "Cloudy" in content
    assert "Day's RealFeel" in content
    assert "40.0C" in content
    assert "Humidity" in content
    assert "77.5%" in content
    assert "Rain Chance" not in content
    assert "Wind" not in content
    assert "UV Index" not in content
    assert "Total Records" not in content
    assert "Error Details" not in content
