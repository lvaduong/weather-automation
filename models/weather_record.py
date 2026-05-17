from dataclasses import asdict, dataclass
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
    city: Optional[str] = None
    extracted_at: Optional[str] = None
    precipitation_probability: Optional[int] = None
    low_temperature_c_displayed: Optional[float] = None
    low_temperature_f: Optional[float] = None
    realfeel_shade_f: Optional[float] = None
    wind: Optional[str] = None
    max_uv_index: Optional[str] = None
    hours_of_precipitation: Optional[float] = None
    hours_of_rain: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
