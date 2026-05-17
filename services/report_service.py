from __future__ import annotations

from collections import Counter
from html import escape
from pathlib import Path
from statistics import mean
from typing import Iterable

from config import settings
from models.weather_record import WeatherRecord
from utils.file_writer import ensure_directory


class ReportService:
    def generate_summary(
        self,
        records: Iterable[WeatherRecord],
        city: str,
        forecast_range: str,
        missing_dates: list[str] | None = None,
        missing_sections: list[str] | None = None,
        output_path: Path | None = None,
    ) -> Path:
        records = list(records)
        missing_dates = missing_dates or []
        missing_sections = missing_sections or []
        output_path = output_path or settings.REPORT_DIR / "summary_report.html"
        ensure_directory(output_path.parent)

        daily_rows = self._daily_summary_rows(records)
        html = self._render_html(city, forecast_range, daily_rows, missing_dates, missing_sections)
        output_path.write_text(html, encoding="utf-8")
        return output_path

    @staticmethod
    def _format_percent(value: float | None) -> str:
        return "Unavailable" if value is None else f"{value:.1f}%"

    @classmethod
    def _daily_summary_rows(cls, records: list[WeatherRecord]) -> list[dict[str, str]]:
        rows = []
        ordered_dates = list(dict.fromkeys(record.date for record in records if record.date))

        for forecast_date in ordered_dates:
            day_records = [record for record in records if record.date == forecast_date]
            humidities = [record.humidity for record in day_records if record.humidity is not None]
            realfeel_values = [record.realfeel_f for record in day_records if record.realfeel_f is not None]

            rows.append(
                {
                    "date": forecast_date,
                    "temperature": cls._format_temperature_sections(day_records),
                    "main_weather": cls._most_common_text(record.weather for record in day_records),
                    "realfeel": cls._format_realfeel(max(realfeel_values) if realfeel_values else None),
                    "humidity": cls._format_percent(mean(humidities) if humidities else None),
                }
            )

        return rows

    @classmethod
    def _format_temperature_sections(cls, records: list[WeatherRecord]) -> str:
        sections = []
        for period in ["Morning", "Afternoon", "Evening", "Overnight"]:
            matching_record = next((record for record in records if record.period == period), None)
            temperature = cls._temperature_c(matching_record) if matching_record else None
            sections.append(f"{period}: {cls._format_celsius(temperature)}")
        return " | ".join(sections)

    @staticmethod
    def _temperature_c(record: WeatherRecord | None) -> float | None:
        if record is None:
            return None
        if record.temperature_c_displayed is not None:
            return record.temperature_c_displayed
        return record.temperature_c_calculated

    @staticmethod
    def _format_celsius(value: float | None) -> str:
        return "Unavailable" if value is None else f"{value:g}C"

    @classmethod
    def _format_realfeel(cls, value_f: float | None) -> str:
        if value_f is None:
            return "Unavailable"
        return f"{((value_f - 32) * 5 / 9):.1f}C"

    @staticmethod
    def _most_common_text(values: Iterable[str | None]) -> str:
        text_values = [value for value in values if value]
        return Counter(text_values).most_common(1)[0][0] if text_values else "Unavailable"

    @staticmethod
    def _render_html(
        city: str,
        forecast_range: str,
        daily_rows: list[dict[str, str]],
        missing_dates: list[str],
        missing_sections: list[str],
    ) -> str:
        forecast_rows = "\n".join(
            "<tr>"
            f"<td>{escape(row['date'])}</td>"
            f"<td>{escape(row['temperature'])}</td>"
            f"<td>{escape(row['main_weather'])}</td>"
            f"<td>{escape(row['realfeel'])}</td>"
            f"<td>{escape(row['humidity'])}</td>"
            "</tr>"
            for row in daily_rows
        )
        if not forecast_rows:
            forecast_rows = '<tr><td colspan="5">No forecast records available.</td></tr>'

        quality_summary = ReportService._render_quality_summary(missing_dates, missing_sections)

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Daily Forecast Summary Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #172026; }}
    h1 {{ font-size: 28px; margin-bottom: 8px; }}
    .meta {{ color: #5c6873; margin-bottom: 24px; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 960px; margin-bottom: 32px; }}
    th, td {{ border: 1px solid #d7dde2; padding: 10px 12px; text-align: left; }}
    th {{ background: #eef3f7; }}
    caption {{ text-align: left; font-weight: 700; margin-bottom: 8px; }}
    .quality {{ max-width: 960px; margin-bottom: 24px; padding: 12px 16px; border: 1px solid #d7dde2; }}
    .quality h2 {{ font-size: 18px; margin: 0 0 8px; }}
    .quality p {{ margin: 4px 0; }}
  </style>
</head>
<body>
  <h1>Daily Forecast Summary Report</h1>
  <div class="meta">{escape(city)} | {escape(forecast_range)}</div>
  {quality_summary}
  <table>
    <caption>Daily Forecast Summary</caption>
    <thead>
      <tr>
        <th>Date</th>
        <th>Temperature</th>
        <th>Main Weather Of The Day</th>
        <th>Day's RealFeel</th>
        <th>Humidity</th>
      </tr>
    </thead>
    <tbody>{forecast_rows}</tbody>
  </table>
</body>
</html>
"""

    @staticmethod
    def _render_quality_summary(missing_dates: list[str], missing_sections: list[str]) -> str:
        if not missing_dates and not missing_sections:
            return (
                '<section class="quality">'
                "<h2>Data Completeness</h2>"
                "<p>All expected forecast dates and day sections were captured.</p>"
                "</section>"
            )

        missing_dates_text = ", ".join(escape(item) for item in missing_dates) or "None"
        missing_sections_text = ", ".join(escape(item) for item in missing_sections) or "None"
        return (
            '<section class="quality">'
            "<h2>Data Completeness</h2>"
            f"<p><strong>Missing Dates:</strong> {missing_dates_text}</p>"
            f"<p><strong>Missing Sections:</strong> {missing_sections_text}</p>"
            "</section>"
        )
