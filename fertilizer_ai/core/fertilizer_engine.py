from __future__ import annotations

from fertilizer_ai.core.models import FertilizerPlan, SoilSample, WeatherProfile


class PrecisionFertilizerEngine:
    CROP_TARGETS = {
        "水稻": {"n": 19.0, "p": 8.2, "k": 13.5, "ph_min": 5.8, "ph_max": 7.2},
        "玉米": {"n": 22.0, "p": 7.6, "k": 14.0, "ph_min": 6.0, "ph_max": 7.5},
        "小麦": {"n": 18.0, "p": 7.2, "k": 11.0, "ph_min": 6.2, "ph_max": 7.6},
        "番茄": {"n": 16.0, "p": 9.4, "k": 21.0, "ph_min": 6.0, "ph_max": 7.0},
        "苹果": {"n": 14.0, "p": 6.0, "k": 18.0, "ph_min": 6.0, "ph_max": 7.4},
    }
    DEFAULT_TARGET = {"n": 17.0, "p": 7.0, "k": 13.0, "ph_min": 6.0, "ph_max": 7.4}

    def build_plan(self, sample: SoilSample, weather: WeatherProfile) -> FertilizerPlan:
        target = self.CROP_TARGETS.get(sample.crop, self.DEFAULT_TARGET)
        soil_factor = self._soil_buffer_factor(sample)
        water_factor = self._water_adjustment(weather, sample.moisture)
        risk_score = self._risk_score(sample, weather)

        n_gap = self._nutrient_gap(target["n"], sample.nitrogen, 0.62)
        p_gap = self._nutrient_gap(target["p"], sample.phosphorus, 0.34)
        k_gap = self._nutrient_gap(target["k"], sample.potassium, 0.47)

        nitrogen = n_gap * sample.area_mu * soil_factor * water_factor
        phosphorus = p_gap * sample.area_mu * soil_factor
        potassium = k_gap * sample.area_mu * (0.9 + sample.moisture / 200)
        organic = self._organic_need(sample.organic_matter, sample.area_mu)

        notes = self._explain(sample, weather, target, risk_score)
        confidence = max(0.52, min(0.94, 0.88 - risk_score * 0.09 + sample.area_mu / 800))

        return FertilizerPlan(
            nitrogen_kg=round(nitrogen, 2),
            phosphorus_kg=round(phosphorus, 2),
            potassium_kg=round(potassium, 2),
            organic_kg=round(organic, 2),
            risk_level=self._risk_label(risk_score),
            confidence=round(confidence, 2),
            notes=notes,
        )

    def _nutrient_gap(self, target: float, measured: float, absorption: float) -> float:
        gap = max(0.0, target - measured)
        return gap / max(absorption, 0.1)

    def _soil_buffer_factor(self, sample: SoilSample) -> float:
        if sample.organic_matter >= 32:
            return 0.88
        if sample.organic_matter >= 22:
            return 1.0
        return 1.15

    def _water_adjustment(self, weather: WeatherProfile, moisture: float) -> float:
        if weather.rainfall_7d > 60:
            return 0.82
        if moisture < 38 and not weather.irrigation_available:
            return 0.72
        if weather.evapotranspiration > 5.5:
            return 1.08
        return 1.0

    def _organic_need(self, organic_matter: float, area_mu: float) -> float:
        if organic_matter >= 30:
            return area_mu * 30
        if organic_matter >= 20:
            return area_mu * 55
        return area_mu * 85

    def _risk_score(self, sample: SoilSample, weather: WeatherProfile) -> int:
        score = 0
        if sample.ph < 5.5 or sample.ph > 8.2:
            score += 2
        if sample.moisture < 35 or sample.moisture > 78:
            score += 1
        if weather.rainfall_7d > 75:
            score += 2
        if weather.temperature_avg > 34 or weather.temperature_avg < 8:
            score += 1
        if sample.organic_matter < 16:
            score += 1
        return min(score, 5)

    def _risk_label(self, score: int) -> str:
        if score >= 4:
            return "高"
        if score >= 2:
            return "中"
        return "低"

    def _explain(
        self,
        sample: SoilSample,
        weather: WeatherProfile,
        target: dict[str, float],
        risk_score: int,
    ) -> list[str]:
        notes = []
        if sample.ph < target["ph_min"]:
            notes.append("土壤偏酸，建议把氮肥拆分到追肥阶段，降低一次性投入。")
        elif sample.ph > target["ph_max"]:
            notes.append("土壤偏碱，磷肥有效性偏弱，建议配合有机肥改善根际环境。")
        if weather.rainfall_7d > 60:
            notes.append("近期降雨偏多，氮肥建议避开强降雨窗口。")
        if sample.organic_matter < 20:
            notes.append("有机质不足，本方案提高了有机肥基施权重。")
        if risk_score == 0:
            notes.append("土壤与天气指标稳定，可按常规基肥加追肥节奏执行。")
        return notes
