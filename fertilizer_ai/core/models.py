from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class SoilSample:
    plot_name: str
    crop: str
    area_mu: float
    ph: float
    organic_matter: float
    nitrogen: float
    phosphorus: float
    potassium: float
    moisture: float
    sampling_date: date


@dataclass(slots=True)
class WeatherProfile:
    rainfall_7d: float
    temperature_avg: float
    evapotranspiration: float
    irrigation_available: bool


@dataclass(slots=True)
class FertilizerPlan:
    nitrogen_kg: float
    phosphorus_kg: float
    potassium_kg: float
    organic_kg: float
    risk_level: str
    confidence: float
    notes: list[str]
