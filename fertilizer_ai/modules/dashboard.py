from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fertilizer_ai.core.fertilizer_engine import PrecisionFertilizerEngine
from fertilizer_ai.core.models import SoilSample, WeatherProfile
from fertilizer_ai.data.repository import AppRepository


@dataclass(slots=True)
class FieldScore:
    name: str
    value: float
    level: str
    reason: str


@dataclass(slots=True)
class DashboardState:
    plot: dict[str, Any] | None = None
    sample: dict[str, Any] | None = None
    weather: dict[str, Any] | None = None
    latest_decision: dict[str, Any] | None = None
    inventory: list[dict[str, Any]] = field(default_factory=list)
    tasks: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    scores: list[FieldScore] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    task_pressure: float = 0.0
    inventory_pressure: float = 0.0
    decision_score: float = 0.0
    readiness_score: float = 0.0
    risk_level: str = "低"
    summary: str = ""


class DashboardAnalyzer:
    def __init__(self) -> None:
        self.engine = PrecisionFertilizerEngine()

    def build(
        self,
        plot: dict[str, Any] | None,
        samples: list[dict[str, Any]],
        weathers: list[dict[str, Any]],
        inventory: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        alerts: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
    ) -> DashboardState:
        selected_name = plot["name"] if plot else ""
        sample = self._latest_for_plot(samples, selected_name, "sampling_date")
        weather = self._latest_weather(weathers)
        latest_decision = self._latest_for_plot(decisions, selected_name, "created_at")
        plot_tasks = [row for row in tasks if not selected_name or row.get("plot_name") == selected_name]
        plot_alerts = [row for row in alerts if not selected_name or row.get("source") in {"土壤", "气象", "库存", "任务", "算法"}]
        plot_decisions = [row for row in decisions if not selected_name or row.get("plot_name") == selected_name]

        scores = self._build_scores(plot, sample, weather, inventory, plot_tasks, plot_alerts, plot_decisions)
        readiness = self._weighted_readiness(scores)
        task_pressure = self._task_pressure(plot_tasks)
        inventory_pressure = self._inventory_pressure(inventory)
        decision_score = self._decision_score(sample, weather, latest_decision)
        risk_level = self._risk_level(readiness, task_pressure, inventory_pressure, plot_alerts)
        suggestions = self._suggestions(plot, sample, weather, inventory, plot_tasks, plot_alerts, latest_decision)
        summary = self._summary(plot, sample, weather, readiness, risk_level, suggestions)

        return DashboardState(
            plot=plot,
            sample=sample,
            weather=weather,
            latest_decision=latest_decision,
            inventory=inventory,
            tasks=plot_tasks,
            alerts=plot_alerts,
            decisions=plot_decisions,
            scores=scores,
            suggestions=suggestions,
            task_pressure=task_pressure,
            inventory_pressure=inventory_pressure,
            decision_score=decision_score,
            readiness_score=readiness,
            risk_level=risk_level,
            summary=summary,
        )

    def preview_plan(self, state: DashboardState):
        if not state.sample or not state.weather:
            return None
        sample = self._sample_model(state.sample)
        weather = self._weather_model(state.weather)
        return self.engine.build_plan(sample, weather)

    def _build_scores(
        self,
        plot: dict[str, Any] | None,
        sample: dict[str, Any] | None,
        weather: dict[str, Any] | None,
        inventory: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        alerts: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
    ) -> list[FieldScore]:
        return [
            self._soil_score(sample),
            self._weather_score(weather),
            self._inventory_score(inventory),
            self._task_score(tasks),
            self._decision_memory_score(plot, decisions),
            self._alert_score(alerts),
        ]

    def _soil_score(self, sample: dict[str, Any] | None) -> FieldScore:
        if not sample:
            return FieldScore("土壤完整度", 18, "缺失", "当前地块没有土壤检测记录")
        ph = float(sample.get("ph", 0))
        organic = float(sample.get("organic_matter", 0))
        nitrogen = float(sample.get("nitrogen", 0))
        phosphorus = float(sample.get("phosphorus", 0))
        potassium = float(sample.get("potassium", 0))
        moisture = float(sample.get("moisture", 0))
        ph_score = 100 - min(70, abs(ph - 6.6) * 23)
        organic_score = min(100, organic * 3.2)
        nutrient_balance = 100 - min(80, self._spread([nitrogen, phosphorus * 2.1, potassium * 1.25]) * 3.4)
        moisture_score = 100 - min(85, abs(moisture - 58) * 2.1)
        value = self._clamp(mean([ph_score, organic_score, nutrient_balance, moisture_score]), 0, 100)
        return FieldScore("土壤适配", value, self._level(value), self._soil_reason(ph, organic, moisture))

    def _weather_score(self, weather: dict[str, Any] | None) -> FieldScore:
        if not weather:
            return FieldScore("气象窗口", 20, "缺失", "没有气象水分记录")
        rainfall = float(weather.get("rainfall_7d", 0))
        temperature = float(weather.get("temperature_avg", 0))
        evaporation = float(weather.get("evapotranspiration", 0))
        rain_score = 100 - min(90, max(0, rainfall - 35) * 1.8 + max(0, 12 - rainfall) * 1.0)
        temp_score = 100 - min(90, abs(temperature - 24) * 3.0)
        evaporation_score = 100 - min(80, abs(evaporation - 4.0) * 13)
        irrigation_bonus = 8 if weather.get("irrigation_available") == "是" else -8
        value = self._clamp(mean([rain_score, temp_score, evaporation_score]) + irrigation_bonus, 0, 100)
        return FieldScore("施肥天气", value, self._level(value), self._weather_reason(rainfall, temperature, evaporation))

    def _inventory_score(self, inventory: list[dict[str, Any]]) -> FieldScore:
        if not inventory:
            return FieldScore("库存支撑", 16, "缺失", "肥料库存没有可用记录")
        categories = {row.get("category") for row in inventory}
        stock = sum(float(row.get("stock_kg", 0)) for row in inventory)
        price_values = [float(row.get("unit_price", 0)) for row in inventory if float(row.get("unit_price", 0)) > 0]
        diversity = min(42, len(categories) * 8)
        stock_score = min(42, stock / 90)
        price_score = 16 if price_values and mean(price_values) <= 5 else 9
        value = self._clamp(diversity + stock_score + price_score, 0, 100)
        reason = f"库存覆盖 {len(categories)} 类肥料，总量 {stock:.0f} 公斤"
        return FieldScore("库存保障", value, self._level(value), reason)

    def _task_score(self, tasks: list[dict[str, Any]]) -> FieldScore:
        if not tasks:
            return FieldScore("作业执行", 68, "正常", "当前地块没有未完成作业压力")
        progress_values = [int(row.get("progress", 0)) for row in tasks]
        overdue = sum(1 for row in tasks if self._is_overdue(row.get("due_date", "")) and row.get("status") != "已完成")
        done = sum(1 for row in tasks if row.get("status") == "已完成")
        progress = mean(progress_values) if progress_values else 0
        value = progress * 0.62 + done * 8 - overdue * 18 + 35
        value = self._clamp(value, 0, 100)
        reason = f"平均进度 {progress:.0f}%，延期 {overdue} 项"
        return FieldScore("执行节奏", value, self._level(value), reason)

    def _decision_memory_score(self, plot: dict[str, Any] | None, decisions: list[dict[str, Any]]) -> FieldScore:
        if not plot:
            return FieldScore("方案记忆", 30, "缺失", "尚未选择地块")
        if not decisions:
            return FieldScore("方案记忆", 36, "偏低", "当前地块没有历史施肥方案")
        confidence_values = [float(row.get("confidence", 0)) * 100 for row in decisions]
        risk_penalty = sum(14 for row in decisions if row.get("risk_level") == "高")
        recency_bonus = 12 if self._days_since(decisions[0].get("created_at", "")) <= 10 else 4
        value = self._clamp(mean(confidence_values) + recency_bonus - risk_penalty, 0, 100)
        reason = f"历史方案 {len(decisions)} 条，平均可信度 {mean(confidence_values):.0f}%"
        return FieldScore("方案沉淀", value, self._level(value), reason)

    def _alert_score(self, alerts: list[dict[str, Any]]) -> FieldScore:
        if not alerts:
            return FieldScore("风险静默", 86, "良好", "暂无风险预警记录")
        penalty = 0
        for row in alerts:
            if row.get("level") == "高":
                penalty += 18
            elif row.get("level") == "中":
                penalty += 10
            else:
                penalty += 4
        value = self._clamp(100 - penalty, 0, 100)
        reason = f"关联预警 {len(alerts)} 条，高等级 {sum(1 for row in alerts if row.get('level') == '高')} 条"
        return FieldScore("风险控制", value, self._level(value), reason)

    def _suggestions(
        self,
        plot: dict[str, Any] | None,
        sample: dict[str, Any] | None,
        weather: dict[str, Any] | None,
        inventory: list[dict[str, Any]],
        tasks: list[dict[str, Any]],
        alerts: list[dict[str, Any]],
        latest_decision: dict[str, Any] | None,
    ) -> list[str]:
        suggestions: list[str] = []
        if not plot:
            return ["请先在地块档案中建立地块，再进入驾驶舱做闭环判断。"]
        if not sample:
            suggestions.append("当前地块缺少土壤检测，建议先补录氮、磷、钾、有机质和含水率。")
        else:
            ph = float(sample.get("ph", 0))
            organic = float(sample.get("organic_matter", 0))
            moisture = float(sample.get("moisture", 0))
            if ph < 5.8:
                suggestions.append("土壤偏酸，基肥阶段减少一次性氮肥，配合调理剂改善根际环境。")
            if ph > 7.6:
                suggestions.append("土壤偏碱，磷肥有效性可能下降，建议提高有机肥和水分协同。")
            if organic < 20:
                suggestions.append("有机质偏低，建议把有机肥作为本轮方案的稳定项。")
            if moisture < 38:
                suggestions.append("含水率偏低，施肥前应确认灌溉条件，避免肥效释放不足。")
        if weather:
            rainfall = float(weather.get("rainfall_7d", 0))
            temperature = float(weather.get("temperature_avg", 0))
            if rainfall > 60:
                suggestions.append("近期降雨偏多，氮肥追施应避开强降雨窗口。")
            if temperature > 34:
                suggestions.append("气温偏高，建议选择清晨或傍晚作业，降低挥发损失。")
        else:
            suggestions.append("缺少气象水分信息，建议更新监测点数据后再生成方案。")
        if not inventory:
            suggestions.append("库存为空，施肥方案生成后无法估算物料保障。")
        elif self._inventory_pressure(inventory) > 65:
            suggestions.append("库存结构偏紧，建议优先补齐氮肥、钾肥和有机肥。")
        if any(self._is_overdue(row.get("due_date", "")) for row in tasks if row.get("status") != "已完成"):
            suggestions.append("存在延期作业，请先处理执行堵点，再安排新的施肥任务。")
        if any(row.get("level") == "高" for row in alerts):
            suggestions.append("已有高等级预警，建议先复核风险来源，再保存新的施肥方案。")
        if not latest_decision:
            suggestions.append("当前地块还没有历史方案，可在驾驶舱生成一次施肥快照作为基线。")
        if not suggestions:
            suggestions.append("当前状态稳定，可以按常规基肥加追肥节奏推进。")
        return suggestions[:7]

    def _summary(
        self,
        plot: dict[str, Any] | None,
        sample: dict[str, Any] | None,
        weather: dict[str, Any] | None,
        readiness: float,
        risk_level: str,
        suggestions: list[str],
    ) -> str:
        name = plot.get("name", "未选择地块") if plot else "未选择地块"
        crop = plot.get("crop", "未知作物") if plot else "未知作物"
        sample_text = "已有土壤检测" if sample else "缺少土壤检测"
        weather_text = "已有气象水分" if weather else "缺少气象水分"
        main = suggestions[0] if suggestions else "暂无建议。"
        return (
            f"{name}，作物为{crop}。当前{sample_text}，{weather_text}。"
            f"综合准备度 {readiness:.0f} 分，风险等级为{risk_level}。{main}"
        )

    def _weighted_readiness(self, scores: list[FieldScore]) -> float:
        weights = {
            "土壤适配": 0.24,
            "施肥天气": 0.18,
            "库存保障": 0.16,
            "执行节奏": 0.15,
            "方案沉淀": 0.15,
            "风险控制": 0.12,
        }
        if not scores:
            return 0
        value = sum(score.value * weights.get(score.name, 0.1) for score in scores)
        return self._clamp(value, 0, 100)

    def _task_pressure(self, tasks: list[dict[str, Any]]) -> float:
        if not tasks:
            return 20
        pending = sum(1 for row in tasks if row.get("status") != "已完成")
        overdue = sum(1 for row in tasks if self._is_overdue(row.get("due_date", "")) and row.get("status") != "已完成")
        avg_progress = mean([int(row.get("progress", 0)) for row in tasks]) if tasks else 0
        return self._clamp(pending * 12 + overdue * 22 + (100 - avg_progress) * 0.22, 0, 100)

    def _inventory_pressure(self, inventory: list[dict[str, Any]]) -> float:
        if not inventory:
            return 100
        stock = sum(float(row.get("stock_kg", 0)) for row in inventory)
        categories = len({row.get("category") for row in inventory})
        pressure = 100 - min(70, stock / 80) - min(25, categories * 4)
        return self._clamp(pressure, 0, 100)

    def _decision_score(
        self,
        sample: dict[str, Any] | None,
        weather: dict[str, Any] | None,
        latest_decision: dict[str, Any] | None,
    ) -> float:
        base = 30
        if sample:
            base += 25
        if weather:
            base += 20
        if latest_decision:
            base += float(latest_decision.get("confidence", 0)) * 25
            if latest_decision.get("risk_level") == "高":
                base -= 18
            elif latest_decision.get("risk_level") == "中":
                base -= 8
        return self._clamp(base, 0, 100)

    def _risk_level(
        self,
        readiness: float,
        task_pressure: float,
        inventory_pressure: float,
        alerts: list[dict[str, Any]],
    ) -> str:
        high_alerts = sum(1 for row in alerts if row.get("level") == "高")
        score = 100 - readiness + task_pressure * 0.25 + inventory_pressure * 0.2 + high_alerts * 18
        if score >= 62:
            return "高"
        if score >= 36:
            return "中"
        return "低"

    def _sample_model(self, row: dict[str, Any]) -> SoilSample:
        return SoilSample(
            plot_name=row["plot_name"],
            crop=row["crop"],
            area_mu=float(row["area_mu"]),
            ph=float(row["ph"]),
            organic_matter=float(row["organic_matter"]),
            nitrogen=float(row["nitrogen"]),
            phosphorus=float(row["phosphorus"]),
            potassium=float(row["potassium"]),
            moisture=float(row["moisture"]),
            sampling_date=date.fromisoformat(row["sampling_date"]),
        )

    def _weather_model(self, row: dict[str, Any]) -> WeatherProfile:
        return WeatherProfile(
            rainfall_7d=float(row["rainfall_7d"]),
            temperature_avg=float(row["temperature_avg"]),
            evapotranspiration=float(row["evapotranspiration"]),
            irrigation_available=row["irrigation_available"] == "是",
        )

    def _latest_for_plot(self, rows: list[dict[str, Any]], plot_name: str, date_key: str) -> dict[str, Any] | None:
        matched = [row for row in rows if not plot_name or row.get("plot_name") == plot_name]
        if not matched:
            return None
        return sorted(matched, key=lambda row: row.get(date_key, ""), reverse=True)[0]

    def _latest_weather(self, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not rows:
            return None
        return sorted(rows, key=lambda row: row.get("observed_at", ""), reverse=True)[0]

    def _soil_reason(self, ph: float, organic: float, moisture: float) -> str:
        parts = [f"酸碱度 {ph:.1f}", f"有机质 {organic:.1f}", f"含水率 {moisture:.0f}%"]
        if ph < 5.8:
            parts.append("偏酸")
        elif ph > 7.6:
            parts.append("偏碱")
        if organic < 20:
            parts.append("有机质不足")
        return "，".join(parts)

    def _weather_reason(self, rainfall: float, temperature: float, evaporation: float) -> str:
        parts = [f"七日降雨 {rainfall:.0f} 毫米", f"均温 {temperature:.1f}℃", f"蒸散 {evaporation:.1f}"]
        if rainfall > 60:
            parts.append("降雨偏多")
        if temperature > 34:
            parts.append("高温风险")
        return "，".join(parts)

    def _level(self, value: float) -> str:
        if value >= 82:
            return "良好"
        if value >= 62:
            return "正常"
        if value >= 42:
            return "偏低"
        return "缺口"

    def _spread(self, values: list[float]) -> float:
        if not values:
            return 0
        avg = mean(values)
        return mean([abs(value - avg) for value in values])

    def _days_since(self, raw: str) -> int:
        try:
            day = datetime.fromisoformat(raw).date()
        except ValueError:
            try:
                day = date.fromisoformat(raw)
            except ValueError:
                return 999
        return (date.today() - day).days

    def _is_overdue(self, raw: str) -> bool:
        try:
            return date.fromisoformat(raw) < date.today()
        except ValueError:
            return False

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))


class MetricCard(QFrame):
    def __init__(self, title: str, unit: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Surface")
        self.value = QLabel("0")
        self.value.setObjectName("Title")
        self.title = QLabel(title)
        self.title.setObjectName("Muted")
        self.unit = QLabel(unit)
        self.unit.setObjectName("Muted")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.addWidget(self.title)
        row = QHBoxLayout()
        row.addWidget(self.value)
        row.addWidget(self.unit)
        row.addStretch(1)
        layout.addLayout(row)

    def set_value(self, value: str) -> None:
        self.value.setText(value)


class HealthGauge(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.score = 0.0
        self.level = "低"
        self.setMinimumHeight(210)

    def set_state(self, score: float, level: str) -> None:
        self.score = score
        self.level = level
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(14, 14, -14, -14)
        size = min(rect.width(), rect.height() * 1.9)
        arc_rect = QRectF(rect.center().x() - size / 2, rect.bottom() - size / 2, size, size)
        base_pen = QPen(QColor("#d9e5d7"), 18, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(base_pen)
        painter.drawArc(arc_rect, 0, 180 * 16)
        color = self._score_color(self.score)
        painter.setPen(QPen(color, 18, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(arc_rect, 180 * 16, int(-180 * 16 * self.score / 100))
        painter.setPen(QColor("#203a2c"))
        painter.setFont(QFont("", 30, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self.score:.0f}")
        painter.setFont(QFont("", 12))
        painter.setPen(QColor("#60766b"))
        painter.drawText(rect.adjusted(0, 84, 0, 0), Qt.AlignmentFlag.AlignCenter, f"准备度  风险{self.level}")

    def _score_color(self, score: float) -> QColor:
        if score >= 80:
            return QColor("#2f8a5b")
        if score >= 60:
            return QColor("#74a342")
        if score >= 40:
            return QColor("#c7922b")
        return QColor("#b84c4c")


class RadarChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scores: list[FieldScore] = []
        self.setMinimumHeight(260)

    def set_scores(self, scores: list[FieldScore]) -> None:
        self.scores = scores
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(18, 18, -18, -18)
        center = QPointF(rect.center())
        radius = min(rect.width(), rect.height()) * 0.34
        labels = [score.name for score in self.scores]
        values = [score.value for score in self.scores]
        count = max(1, len(values))

        painter.setPen(QPen(QColor("#d6e4d5"), 1))
        for step in range(1, 5):
            path = QPainterPath()
            for index in range(count):
                point = self._point(center, radius * step / 4, index, count)
                if index == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            path.closeSubpath()
            painter.drawPath(path)

        painter.setPen(QPen(QColor("#b8cbbb"), 1))
        for index in range(count):
            painter.drawLine(center, self._point(center, radius, index, count))
            label_point = self._point(center, radius + 28, index, count)
            text = labels[index] if index < len(labels) else ""
            painter.drawText(QRectF(label_point.x() - 44, label_point.y() - 12, 88, 24), Qt.AlignmentFlag.AlignCenter, text)

        path = QPainterPath()
        for index, value in enumerate(values):
            point = self._point(center, radius * value / 100, index, count)
            if index == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        path.closeSubpath()
        painter.setBrush(QColor(47, 125, 79, 72))
        painter.setPen(QPen(QColor("#2f7d4f"), 2))
        painter.drawPath(path)

    def _point(self, center: QPointF, radius: float, index: int, count: int) -> QPointF:
        angle = -math.pi / 2 + index * math.tau / count
        return QPointF(center.x() + math.cos(angle) * radius, center.y() + math.sin(angle) * radius)


class TrendChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.values: list[float] = []
        self.setMinimumHeight(190)

    def set_values(self, values: list[float]) -> None:
        self.values = values[-12:]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(24, 24, -24, -32)
        painter.setPen(QPen(QColor("#d8e5d7"), 1))
        for step in range(5):
            y = rect.top() + rect.height() * step / 4
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))
        if not self.values:
            painter.setPen(QColor("#809188"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "暂无历史方案")
            return
        max_value = max(max(self.values), 1)
        points = []
        for index, value in enumerate(self.values):
            x = rect.left() + rect.width() * index / max(1, len(self.values) - 1)
            y = rect.bottom() - rect.height() * value / max_value
            points.append(QPointF(x, y))
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        fill = QPainterPath(path)
        fill.lineTo(points[-1].x(), rect.bottom())
        fill.lineTo(points[0].x(), rect.bottom())
        fill.closeSubpath()
        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        gradient.setColorAt(0, QColor(47, 125, 79, 90))
        gradient.setColorAt(1, QColor(47, 125, 79, 8))
        painter.fillPath(fill, gradient)
        painter.setPen(QPen(QColor("#2f7d4f"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#2f7d4f"), 2))
        for point in points:
            painter.drawEllipse(point, 4, 4)


class PlotSketch(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.state: DashboardState | None = None
        self.setMinimumHeight(230)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_state(self, state: DashboardState) -> None:
        self.state = state
        self.update()

    def mousePressEvent(self, event) -> None:
        if self.state and self.state.plot:
            self.clicked.emit(self.state.plot.get("name", ""))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(18, 18, -18, -18)
        painter.setPen(QPen(QColor("#cddccc"), 1))
        painter.setBrush(QColor("#f8fbf5"))
        painter.drawRoundedRect(rect, 14, 14)

        name = self.state.plot.get("name", "未选择地块") if self.state and self.state.plot else "未选择地块"
        crop = self.state.plot.get("crop", "未知作物") if self.state and self.state.plot else "未知作物"
        painter.setPen(QColor("#203a2c"))
        painter.setFont(QFont("", 15, QFont.Weight.Bold))
        painter.drawText(rect.adjusted(18, 14, -18, -160), Qt.AlignmentFlag.AlignLeft, name)
        painter.setFont(QFont("", 10))
        painter.setPen(QColor("#64756c"))
        painter.drawText(rect.adjusted(18, 42, -18, -130), Qt.AlignmentFlag.AlignLeft, f"当前作物：{crop}")

        field_rect = rect.adjusted(24, 82, -24, -24)
        bands = 7
        for index in range(bands):
            top = field_rect.top() + index * field_rect.height() / bands
            band = QRectF(
                field_rect.left() + index * 8,
                top,
                field_rect.width() - index * 16,
                field_rect.height() / bands - 5,
            )
            hue = 92 + index * 5
            painter.setBrush(QColor.fromHsv(hue, 110, 205))
            painter.setPen(QPen(QColor("#dce8d7"), 1))
            painter.drawRoundedRect(band, 12, 12)
        painter.setPen(QPen(QColor("#6aa77f"), 2, Qt.PenStyle.DashLine))
        painter.drawLine(field_rect.left() + 16, field_rect.center().y(), field_rect.right() - 16, field_rect.center().y())
        painter.setBrush(QColor("#2f7d4f"))
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(5):
            x = field_rect.left() + 38 + index * field_rect.width() / 5
            y = field_rect.top() + 18 + (index % 2) * 42
            painter.drawEllipse(QPointF(x, y), 5, 5)


class ScoreTable(QTableWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(0, 4, parent)
        self.setHorizontalHeaderLabels(["指标", "分值", "状态", "判断"])
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setMinimumHeight(220)
        self.horizontalHeader().setStretchLastSection(True)

    def set_scores(self, scores: list[FieldScore]) -> None:
        self.setRowCount(len(scores))
        for row_index, score in enumerate(scores):
            values = [score.name, f"{score.value:.0f}", score.level, score.reason]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if column_index < 3 else Qt.AlignmentFlag.AlignLeft)
                self.setItem(row_index, column_index, item)
        self.resizeColumnsToContents()


class DashboardPage(QWidget):
    title = "决策驾驶舱"

    def __init__(self, repository: AppRepository, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.analyzer = DashboardAnalyzer()
        self.state = DashboardState()
        self.cards: dict[str, MetricCard] = {}
        self._plots: list[dict[str, Any]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.layout = QVBoxLayout(content)
        self.layout.setContentsMargins(18, 18, 18, 18)
        self.layout.setSpacing(14)
        scroll.setWidget(content)
        root.addWidget(scroll)

        self._build_header()
        self._build_metric_cards()
        self._build_control_bar()
        self._build_main_panels()
        self._build_bottom_panels()

    def _build_header(self) -> None:
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("AI精准施肥决策系统")
        title.setObjectName("Title")
        subtitle = QLabel("围绕地块、土壤、天气、库存、任务和预警形成闭环决策。")
        subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        self.plot_box = QComboBox()
        self.plot_box.setMinimumWidth(220)
        self.plot_box.currentIndexChanged.connect(self._plot_changed)
        header.addWidget(QLabel("当前地块"))
        header.addWidget(self.plot_box)
        self.layout.addLayout(header)

    def _build_metric_cards(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(12)
        specs = [
            ("readiness", "综合准备度", "分"),
            ("risk", "风险等级", ""),
            ("soil", "土壤适配", "分"),
            ("weather", "天气窗口", "分"),
            ("inventory", "库存压力", "分"),
            ("tasks", "任务压力", "分"),
        ]
        for index, (key, name, unit) in enumerate(specs):
            card = MetricCard(name, unit)
            self.cards[key] = card
            grid.addWidget(card, index // 3, index % 3)
        self.layout.addLayout(grid)

    def _build_control_bar(self) -> None:
        frame = QFrame()
        frame.setObjectName("Surface")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        self.sensitivity = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity.setRange(0, 100)
        self.sensitivity.setValue(55)
        self.sensitivity.valueChanged.connect(self._update_sensitivity_hint)
        self.sensitivity_label = QLabel("预警灵敏度：55")
        self.sensitivity_label.setObjectName("Muted")
        layout.addWidget(self.sensitivity_label)
        layout.addWidget(self.sensitivity, 1)

        buttons = [
            ("刷新驾驶舱", self.refresh),
            ("生成施肥快照", self.create_decision_snapshot),
            ("生成作业任务", self.create_task_from_state),
            ("生成风险预警", self.create_alert_from_state),
            ("复制研判摘要", self.copy_summary),
        ]
        for text, slot in buttons:
            button = QPushButton(text)
            if text == "刷新驾驶舱":
                button.setObjectName("Primary")
            button.clicked.connect(slot)
            layout.addWidget(button)
        self.layout.addWidget(frame)

    def _build_main_panels(self) -> None:
        row = QHBoxLayout()
        left = QFrame()
        left.setObjectName("Surface")
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("地块态势"))
        self.plot_sketch = PlotSketch()
        self.plot_sketch.clicked.connect(self._show_plot_detail)
        left_layout.addWidget(self.plot_sketch)
        self.gauge = HealthGauge()
        left_layout.addWidget(self.gauge)

        middle = QFrame()
        middle.setObjectName("Surface")
        middle_layout = QVBoxLayout(middle)
        middle_layout.addWidget(QLabel("六维评分"))
        self.radar = RadarChart()
        middle_layout.addWidget(self.radar)
        self.score_table = ScoreTable()
        middle_layout.addWidget(self.score_table)

        right = QFrame()
        right.setObjectName("Surface")
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("智能建议"))
        self.suggestion_list = QListWidget()
        self.suggestion_list.itemDoubleClicked.connect(self._suggestion_to_task)
        right_layout.addWidget(self.suggestion_list)
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMinimumHeight(120)
        right_layout.addWidget(QLabel("研判摘要"))
        right_layout.addWidget(self.summary)

        row.addWidget(left, 3)
        row.addWidget(middle, 4)
        row.addWidget(right, 4)
        self.layout.addLayout(row)

    def _build_bottom_panels(self) -> None:
        row = QHBoxLayout()
        decision_frame = QFrame()
        decision_frame.setObjectName("Surface")
        decision_layout = QVBoxLayout(decision_frame)
        decision_layout.addWidget(QLabel("施肥方案走势"))
        self.trend = TrendChart()
        decision_layout.addWidget(self.trend)
        self.plan_preview = QTextEdit()
        self.plan_preview.setReadOnly(True)
        self.plan_preview.setMinimumHeight(145)
        decision_layout.addWidget(QLabel("当前快照预览"))
        decision_layout.addWidget(self.plan_preview)

        event_frame = QFrame()
        event_frame.setObjectName("Surface")
        event_layout = QVBoxLayout(event_frame)
        event_layout.addWidget(QLabel("近期事项"))
        self.event_list = QListWidget()
        event_layout.addWidget(self.event_list)

        row.addWidget(decision_frame, 6)
        row.addWidget(event_frame, 4)
        self.layout.addLayout(row)
        self.layout.addStretch(1)

    def refresh(self) -> None:
        plots = self.repository.list_records("plots")
        samples = self.repository.list_records("soil_samples")
        weathers = self.repository.list_records("weather_profiles")
        inventory = self.repository.list_records("inventory")
        tasks = self.repository.list_records("tasks")
        alerts = self.repository.list_records("alerts")
        decisions = self.repository.list_records("fertilizer_decisions")
        self._reload_plot_box(plots)
        plot = self._current_plot(plots)
        self.state = self.analyzer.build(plot, samples, weathers, inventory, tasks, alerts, decisions)
        self._render_state()

    def create_decision_snapshot(self) -> None:
        plan = self.analyzer.preview_plan(self.state)
        if not plan or not self.state.sample:
            QMessageBox.information(self, "数据不足", "请先补齐土壤检测和气象水分数据。")
            return
        payload = {
            "plot_name": self.state.sample["plot_name"],
            "crop": self.state.sample["crop"],
            "nitrogen_kg": plan.nitrogen_kg,
            "phosphorus_kg": plan.phosphorus_kg,
            "potassium_kg": plan.potassium_kg,
            "organic_kg": plan.organic_kg,
            "risk_level": plan.risk_level,
            "confidence": plan.confidence,
            "notes": "；".join(plan.notes),
        }
        self.repository.save_decision(payload)
        QMessageBox.information(self, "已生成", "施肥快照已经保存到方案历史。")
        self.refresh()

    def create_task_from_state(self) -> None:
        if not self.state.plot:
            QMessageBox.information(self, "缺少地块", "请先选择地块。")
            return
        due = date.today() + timedelta(days=3)
        task_name = self._task_name_from_state()
        self.repository.create_record(
            "tasks",
            {
                "task_name": task_name,
                "plot_name": self.state.plot["name"],
                "assignee": self.state.plot.get("manager", "待安排"),
                "due_date": due.isoformat(),
                "progress": 0,
                "status": "待安排",
            },
        )
        QMessageBox.information(self, "已生成", f"已生成作业任务：{task_name}")
        self.refresh()

    def create_alert_from_state(self) -> None:
        if not self.state.plot:
            QMessageBox.information(self, "缺少地块", "请先选择地块。")
            return
        level = self._alert_level_by_slider()
        content = self.state.suggestions[0] if self.state.suggestions else self.state.summary
        self.repository.create_record(
            "alerts",
            {
                "title": f"{self.state.plot['name']}驾驶舱预警",
                "level": level,
                "source": "算法",
                "content": content,
                "created_at": date.today().isoformat(),
            },
        )
        QMessageBox.information(self, "已生成", f"已生成{level}等级风险预警。")
        self.refresh()

    def copy_summary(self) -> None:
        QApplication.clipboard().setText(self.state.summary)
        QMessageBox.information(self, "已复制", "研判摘要已复制。")

    def _render_state(self) -> None:
        soil_score = self._score_value("土壤适配")
        weather_score = self._score_value("施肥天气")
        self.cards["readiness"].set_value(f"{self.state.readiness_score:.0f}")
        self.cards["risk"].set_value(self.state.risk_level)
        self.cards["soil"].set_value(f"{soil_score:.0f}")
        self.cards["weather"].set_value(f"{weather_score:.0f}")
        self.cards["inventory"].set_value(f"{self.state.inventory_pressure:.0f}")
        self.cards["tasks"].set_value(f"{self.state.task_pressure:.0f}")
        self.gauge.set_state(self.state.readiness_score, self.state.risk_level)
        self.radar.set_scores(self.state.scores)
        self.score_table.set_scores(self.state.scores)
        self.plot_sketch.set_state(self.state)
        self.summary.setPlainText(self.state.summary)
        self._render_suggestions()
        self._render_plan_preview()
        self._render_trend()
        self._render_events()

    def _render_suggestions(self) -> None:
        self.suggestion_list.clear()
        for index, suggestion in enumerate(self.state.suggestions, 1):
            item = QListWidgetItem(f"{index}. {suggestion}")
            self.suggestion_list.addItem(item)

    def _render_plan_preview(self) -> None:
        plan = self.analyzer.preview_plan(self.state)
        if not plan:
            self.plan_preview.setPlainText("缺少土壤检测或气象水分数据，暂不能生成施肥快照。")
            return
        lines = [
            f"氮肥：{plan.nitrogen_kg} 公斤",
            f"磷肥：{plan.phosphorus_kg} 公斤",
            f"钾肥：{plan.potassium_kg} 公斤",
            f"有机肥：{plan.organic_kg} 公斤",
            f"风险等级：{plan.risk_level}",
            f"可信度：{int(plan.confidence * 100)}%",
        ]
        if plan.notes:
            lines.append("说明：" + "；".join(plan.notes))
        self.plan_preview.setPlainText("\n".join(lines))

    def _render_trend(self) -> None:
        values = []
        for row in reversed(self.state.decisions):
            values.append(
                float(row.get("nitrogen_kg", 0))
                + float(row.get("phosphorus_kg", 0))
                + float(row.get("potassium_kg", 0))
            )
        self.trend.set_values(values)

    def _render_events(self) -> None:
        self.event_list.clear()
        items: list[str] = []
        for row in self.state.tasks[:6]:
            items.append(f"任务：{row.get('task_name')}｜{row.get('status')}｜{row.get('due_date')}")
        for row in self.state.alerts[:6]:
            items.append(f"预警：{row.get('title')}｜{row.get('level')}｜{row.get('created_at')}")
        for row in self.state.decisions[:4]:
            items.append(f"方案：{row.get('plot_name')}｜风险{row.get('risk_level')}｜{row.get('created_at')}")
        if not items:
            items.append("暂无近期事项，可先生成施肥快照或作业任务。")
        for text in items[:12]:
            self.event_list.addItem(QListWidgetItem(text))

    def _reload_plot_box(self, plots: list[dict[str, Any]]) -> None:
        current_name = self.plot_box.currentData()
        if self._plots == plots and self.plot_box.count() == len(plots):
            return
        self._plots = plots
        self.plot_box.blockSignals(True)
        self.plot_box.clear()
        for row in plots:
            self.plot_box.addItem(row["name"], row["name"])
        if current_name:
            index = self.plot_box.findData(current_name)
            if index >= 0:
                self.plot_box.setCurrentIndex(index)
        self.plot_box.blockSignals(False)

    def _current_plot(self, plots: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not plots:
            return None
        name = self.plot_box.currentData()
        for row in plots:
            if row["name"] == name:
                return row
        return plots[0]

    def _plot_changed(self) -> None:
        self.refresh()

    def _update_sensitivity_hint(self, value: int) -> None:
        self.sensitivity_label.setText(f"预警灵敏度：{value}")

    def _suggestion_to_task(self, item: QListWidgetItem) -> None:
        if not self.state.plot:
            return
        text = item.text().split(". ", 1)[-1]
        due = date.today() + timedelta(days=2)
        self.repository.create_record(
            "tasks",
            {
                "task_name": text[:24],
                "plot_name": self.state.plot["name"],
                "assignee": self.state.plot.get("manager", "待安排"),
                "due_date": due.isoformat(),
                "progress": 0,
                "status": "待安排",
            },
        )
        QMessageBox.information(self, "已转任务", "已把该建议转为作业任务。")
        self.refresh()

    def _show_plot_detail(self, plot_name: str) -> None:
        if not self.state.plot:
            return
        detail = [
            f"地块：{plot_name}",
            f"作物：{self.state.plot.get('crop')}",
            f"面积：{self.state.plot.get('area_mu')} 亩",
            f"负责人：{self.state.plot.get('manager')}",
            f"状态：{self.state.plot.get('status')}",
            "",
            self.state.summary,
        ]
        QMessageBox.information(self, "地块态势", "\n".join(detail))

    def _task_name_from_state(self) -> str:
        if self.state.risk_level == "高":
            return "复核风险并调整施肥窗口"
        if self.state.inventory_pressure > 65:
            return "核对肥料库存保障"
        if self.state.sample and float(self.state.sample.get("organic_matter", 0)) < 20:
            return "补充有机肥基施安排"
        return "执行精准施肥作业"

    def _alert_level_by_slider(self) -> str:
        sensitivity = self.sensitivity.value()
        score = 100 - self.state.readiness_score + sensitivity * 0.25
        if self.state.risk_level == "高" or score >= 58:
            return "高"
        if self.state.risk_level == "中" or score >= 38:
            return "中"
        return "低"

    def _score_value(self, name: str) -> float:
        for score in self.state.scores:
            if score.name == name:
                return score.value
        return 0
