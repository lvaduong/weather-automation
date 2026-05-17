# Weather Tools Use Case - Implementation Design

## 1. Objective

Build an automated weather data extraction and validation framework for AccuWeather.

The system should:

- Open AccuWeather
- Select a local city
- Navigate to the Daily Forecast page
- Retrieve weather information for all available forecast days
- Extract day and night weather details
- Validate Fahrenheit temperature against Celsius conversion
- Save retrieved data to files
- Generate a summary report
- Support execution at least every 1 hour

---

## 2. Recommended Tech Stack

### Language

Python

### Automation Tool

Playwright Python

### Test Framework

Pytest

### Data Processing

Pandas

### Reporting

- Pytest HTML report
- CSV output
- JSON output
- Custom summary report

### Scheduling

- Cron job for local/Linux execution
- GitHub Actions for CI/CD execution

---

## 3. High-Level Architecture

```text
weather-automation/
│
├── config/
│   └── settings.py
│
├── pages/
│   ├── base_page.py
│   └── daily_forecast_page.py
│
├── models/
│   └── weather_record.py
│
├── services/
│   ├── weather_scraper.py
│   ├── temperature_validator.py
│   └── report_service.py
│
├── utils/
│   ├── logger.py
│   ├── file_writer.py
│   └── converter.py
│
├── tests/
│   └── test_weather_forecast.py
│
├── data/
│   ├── weather_data.csv
│   └── weather_data.json
│
├── reports/
│   └── summary_report.html
│
├── requirements.txt
├── pytest.ini
├── run_tests.py
└── README.md
```

---

## 4. Functional Requirements

### 4.1 Open AccuWeather

The automation should open:

```text
https://www.accuweather.com
```

The browser should wait until the page is fully loaded.

---

### 4.2 Select Location

The system should allow the city to be configurable.

Example:

```env
CITY=Ho Chi Minh City
COUNTRY=Vietnam
```

Implementation approach:

1. Open AccuWeather homepage
2. Find search input
3. Enter city name
4. Select the correct city from search suggestions
5. Wait for location forecast page to load

---

### 4.3 Navigate to Daily Forecast

After selecting the city, navigate to the Daily Forecast tab.

Possible strategies:

- Click the `Daily` menu item
- Or navigate directly to the daily forecast URL if the site provides one

The preferred approach is clicking the visible `Daily` tab to simulate user behavior.

---

### 4.4 Retrieve Forecast Date Range

At the top of the Daily Forecast page, AccuWeather may display a forecast range such as:

```text
November 8 - December 22
```

The automation should extract this value and include it in the report.

---

### 4.5 Retrieve Daily Weather Data

For each forecast day, retrieve:

- Date value
- Day period weather information
- Night period weather information

Each period should include:

- Temperature in Fahrenheit
- Main weather condition
- RealFeel value
- Humidity value

Example record:

```json
{
  "date": "Thursday, November 8",
  "period": "Day",
  "temperature_f": 88,
  "temperature_c_calculated": 31.1,
  "weather": "Cloudy",
  "realfeel_f": 101,
  "humidity": 70,
  "validation_status": "PASSED"
}
```

---

## 5. Temperature Validation

### Formula

```text
C = (F - 32) * 5 / 9
```

### Function

```python
def fahrenheit_to_celsius(fahrenheit: float) -> float:
    return round((fahrenheit - 32) * 5 / 9, 1)
```

### Validation Rule

If the page displays Celsius value, compare it with the calculated Celsius value.

Because websites may round values differently, allow tolerance.

```python
def validate_temperature(fahrenheit: float, displayed_celsius: float, tolerance: float = 1.0) -> bool:
    calculated_celsius = fahrenheit_to_celsius(fahrenheit)
    return abs(calculated_celsius - displayed_celsius) <= tolerance
```

If the website does not display Celsius directly, store only the calculated Celsius value and mark validation as `CALCULATED_ONLY`.

---

## 6. Data Model

Use a dataclass to represent one weather record.

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class WeatherRecord:
    date: str
    period: str
    temperature_f: Optional[float]
    temperature_c_calculated: Optional[float]
    temperature_c_displayed: Optional[float]
    weather: Optional[str]
    realfeel_f: Optional[float]
    humidity: Optional[int]
    validation_status: str
    error_message: Optional[str] = None
```

---

## 7. Page Object Design

### BasePage

Responsibilities:

- Common page actions
- Wait helpers
- Screenshot helper
- Logging wrapper

```python
class BasePage:
    def __init__(self, page):
        self.page = page

    def wait_for_page_loaded(self):
        self.page.wait_for_load_state("networkidle")

    def take_screenshot(self, path: str):
        self.page.screenshot(path=path, full_page=True)
```

---

### DailyForecastPage

Responsibilities:

- Search/select location
- Navigate to Daily Forecast
- Extract forecast range
- Extract daily forecast cards
- Open expanded forecast details if needed

```python
class DailyForecastPage(BasePage):
    def search_location(self, city: str):
        pass

    def open_daily_forecast(self):
        pass

    def get_forecast_range(self) -> str:
        pass

    def get_forecast_cards(self):
        pass

    def extract_weather_records(self):
        pass
```

---

## 8. Scraping Strategy

### Important Notes

AccuWeather pages are dynamic and may use lazy loading.

The scraper should:

- Avoid fixed `sleep()`
- Use explicit waits
- Scroll the page to load hidden forecast cards
- Retry failed card extraction
- Continue execution if one day fails

### Suggested Flow

```text
1. Open homepage
2. Search city
3. Select matching city
4. Navigate to Daily Forecast
5. Wait for forecast cards
6. Scroll until all forecast cards are loaded
7. Loop through each card
8. Extract date, temperature, weather condition
9. Open card detail if humidity or RealFeel is not visible
10. Save each record
11. Validate temperature conversion
12. Export data
13. Generate report
```

---

## 9. Error Handling Strategy

The framework should not fail immediately when one data field is missing.

Instead:

- Capture missing field as `None`
- Add warning in log
- Add error message into the record
- Continue with next forecast day

Example:

```python
try:
    humidity = extract_humidity(card)
except Exception as error:
    humidity = None
    error_message = f"Humidity not found: {error}"
```

At the end, the report should show:

- Total records
- Passed validations
- Failed validations
- Missing fields
- Extraction errors

---

## 10. File Output Design

### CSV Output

Path:

```text
data/weather_data.csv
```

Columns:

```text
date,period,temperature_f,temperature_c_calculated,temperature_c_displayed,weather,realfeel_f,humidity,validation_status,error_message
```

### JSON Output

Path:

```text
data/weather_data.json
```

Example:

```json
[
  {
    "date": "Thursday, November 8",
    "period": "Day",
    "temperature_f": 88,
    "temperature_c_calculated": 31.1,
    "temperature_c_displayed": 31,
    "weather": "Cloudy",
    "realfeel_f": 101,
    "humidity": 70,
    "validation_status": "PASSED",
    "error_message": null
  }
]
```

---

## 11. Summary Report Design

The report should include:

- Execution timestamp
- Selected city
- Forecast date range
- Total forecast days
- Total records collected
- Highest temperature
- Lowest temperature
- Average humidity
- Most common weather condition
- Temperature validation pass count
- Temperature validation fail count
- Missing field count
- Error details

Example:

```text
Weather Automation Summary Report

Execution Time: 2026-05-13 08:00:00
City: Ho Chi Minh City
Forecast Range: November 8 - December 22

Total Days Scraped: 45
Total Records: 90
Highest Temperature: 98F
Lowest Temperature: 72F
Average Humidity: 74%
Most Common Weather: Cloudy

Validation Passed: 88
Validation Failed: 2
Missing Fields: 3
```

---

## 12. Test Case Design

### Test Case 1: Verify Daily Forecast Data Extraction

Steps:

1. Open AccuWeather
2. Search configured city
3. Navigate to Daily Forecast page
4. Extract all available daily forecast records
5. Verify at least one record is retrieved

Expected result:

- Forecast data should be successfully retrieved

---

### Test Case 2: Verify Temperature Conversion

Steps:

1. Retrieve Fahrenheit temperature
2. Convert Fahrenheit to Celsius
3. Compare with displayed Celsius value if available

Expected result:

- Calculated Celsius should match displayed Celsius within tolerance

---

### Test Case 3: Verify Required Fields

Steps:

1. Retrieve all weather records
2. Check required fields:
   - Date
   - Period
   - Temperature
   - Weather condition

Expected result:

- Required fields should not be empty

---

### Test Case 4: Verify Output Files

Steps:

1. Run scraper
2. Save result to CSV
3. Save result to JSON
4. Verify files exist
5. Verify files are not empty

Expected result:

- CSV and JSON files should be generated successfully

---

### Test Case 5: Verify Summary Report

Steps:

1. Run scraper
2. Generate summary report
3. Verify report exists
4. Verify report contains summary metrics

Expected result:

- Summary report should be generated successfully

---

## 13. Pytest Example

```python
def test_weather_forecast_extraction(page):
    forecast_page = DailyForecastPage(page)

    forecast_page.open_homepage()
    forecast_page.search_location("Ho Chi Minh City")
    forecast_page.open_daily_forecast()

    records = forecast_page.extract_weather_records()

    assert len(records) > 0, "No weather records were extracted"

    for record in records:
        assert record.date is not None
        assert record.period in ["Day", "Night"]
        assert record.temperature_f is not None
        assert record.weather is not None
```

---

## 14. Scheduling Design

### Option 1: Cron Job

Run every hour:

```bash
0 * * * * cd /path/to/weather-automation && python run_tests.py
```

---

### Option 2: GitHub Actions

```yaml
name: Weather Automation

on:
  schedule:
    - cron: "0 * * * *"
  workflow_dispatch:

jobs:
  weather-test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install

      - name: Run tests
        run: |
          pytest tests/ --html=reports/report.html --self-contained-html

      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: weather-report
          path: reports/
```

---

## 15. Logging Design

Use structured logging.

Example log entries:

```text
[INFO] Starting weather automation
[INFO] Opening AccuWeather
[INFO] Searching location: Ho Chi Minh City
[INFO] Opening Daily Forecast page
[INFO] Total forecast cards found: 45
[WARN] Humidity missing for Thursday, November 8 - Day
[INFO] CSV file generated: data/weather_data.csv
[INFO] Summary report generated: reports/summary_report.html
```

---

## 16. Retry Strategy

Retry should be used for unstable UI actions.

Examples:

- Search result not appearing
- Forecast cards not loaded
- Detail drawer not opened
- Network timeout

Suggested retry count:

```text
3 attempts
```

Suggested wait between retries:

```text
2 seconds
```

---

## 17. Screenshot and Trace Strategy

On failure, save:

```text
reports/screenshots/
reports/traces/
```

Recommended Playwright debugging features:

```bash
playwright show-trace trace.zip
```

Use screenshots and traces to debug flaky failures.

---

## 18. Configuration Design

Create `config/settings.py`.

```python
import os


BASE_URL = os.getenv("BASE_URL", "https://www.accuweather.com")
CITY = os.getenv("CITY", "Ho Chi Minh City")
COUNTRY = os.getenv("COUNTRY", "Vietnam")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
TEMPERATURE_TOLERANCE = float(os.getenv("TEMPERATURE_TOLERANCE", "1.0"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "data")
REPORT_DIR = os.getenv("REPORT_DIR", "reports")
```

---

## 19. Requirements File

```text
playwright
pytest
pytest-playwright
pytest-html
pandas
python-dotenv
```

Install browsers:

```bash
playwright install
```

---

## 20. Acceptance Criteria

The implementation is considered complete when:

- The automation can open AccuWeather successfully
- A local city can be selected
- Daily Forecast page can be opened
- Weather data is extracted for all available days
- Fahrenheit temperature is converted to Celsius
- Temperature validation is performed
- Data is saved to CSV
- Data is saved to JSON
- Summary report is generated
- Test can be scheduled to run every hour
- Errors are logged clearly
- Screenshots are captured on failure

---

## 21. Risks and Mitigation

### Risk: Website layout changes

Mitigation:

- Use stable selectors
- Avoid hardcoded XPath
- Keep selectors centralized in page objects

### Risk: Dynamic content loads slowly

Mitigation:

- Use Playwright auto-wait
- Use explicit waits
- Use retry logic

### Risk: Anti-bot protection

Mitigation:

- Avoid excessive runs
- Use realistic wait behavior
- Run only at required frequency
- Prefer official API if available

### Risk: Missing data

Mitigation:

- Mark field as `None`
- Continue scraping
- Show missing fields in report

---

## 22. Cursor Implementation Prompt

Use this prompt in Cursor:

```text
Build a Python Playwright Pytest automation framework for AccuWeather daily forecast extraction.

Requirements:
1. Open https://www.accuweather.com
2. Search and select a configurable city from environment variable CITY.
3. Navigate to the Daily Forecast page.
4. Extract all available forecast days.
5. For each day, extract date, period, temperature in Fahrenheit, weather condition, RealFeel, and humidity.
6. Convert Fahrenheit temperature to Celsius using C = (F - 32) * 5 / 9.
7. Validate calculated Celsius against displayed Celsius if available, with 1.0 degree tolerance.
8. Save data to data/weather_data.csv and data/weather_data.json.
9. Generate reports/summary_report.html with total days, highest temperature, lowest temperature, average humidity, most common weather, validation passed count, validation failed count, and missing fields.
10. Use Page Object Model.
11. Add logging, retries, screenshots on failure, and Playwright traces.
12. Add pytest tests for extraction, validation, output files, and summary report.
13. Add requirements.txt, pytest.ini, README.md, and run_tests.py.
14. Add GitHub Actions workflow to run every hour.
15. Keep selectors centralized and avoid hardcoded sleep.
```

---

## 23. Suggested Implementation Order

1. Create project structure
2. Install dependencies
3. Implement config
4. Implement converter utility
5. Implement data model
6. Implement base page
7. Implement daily forecast page
8. Implement scraper service
9. Implement validator service
10. Implement file writer
11. Implement report service
12. Implement pytest test cases
13. Add logging
14. Add screenshots and traces
15. Add hourly scheduler
16. Finalize README
