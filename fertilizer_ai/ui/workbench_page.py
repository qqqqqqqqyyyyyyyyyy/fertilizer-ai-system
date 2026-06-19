from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
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
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fertilizer_ai.data.repository import AppRepository
from fertilizer_ai.ui.form_dialog import RecordDialog


@dataclass(slots=True)
class WorkbenchMetric:
    key: str
    title: str
    value: str
    unit: str = ""
    note: str = ""


@dataclass(slots=True)
class WorkbenchInsight:
    title: str
    level: str
    detail: str
    score: float = 0.0


@dataclass(slots=True)
class WorkbenchContext:
    records: list[dict[str, Any]] = field(default_factory=list)
    all_data: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    selected: dict[str, Any] | None = None
    metrics: list[WorkbenchMetric] = field(default_factory=list)
    insights: list[WorkbenchInsight] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    summary: str = ""
    trend_values: list[float] = field(default_factory=list)
    distribution: dict[str, float] = field(default_factory=dict)
    quality_score: float = 0.0


class MiniMetricCard(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Surface")
        self.title = QLabel("")
        self.title.setObjectName("Muted")
        self.value = QLabel("0")
        self.value.setObjectName("Title")
        self.unit = QLabel("")
        self.unit.setObjectName("Muted")
        self.note = QLabel("")
        self.note.setObjectName("Muted")
        self.note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)
        layout.addWidget(self.title)
        row = QHBoxLayout()
        row.addWidget(self.value)
        row.addWidget(self.unit)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(self.note)

    def set_metric(self, metric: WorkbenchMetric) -> None:
        self.title.setText(metric.title)
        self.value.setText(metric.value)
        self.unit.setText(metric.unit)
        self.note.setText(metric.note)


class DistributionChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.data: dict[str, float] = {}
        self.setMinimumHeight(210)

    def set_data(self, data: dict[str, float]) -> None:
        self.data = data
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(22, 18, -22, -32)
        painter.setPen(QPen(QColor("#d8e5d7"), 1))
        painter.drawRoundedRect(rect, 8, 8)
        if not self.data:
            painter.setPen(QColor("#75877d"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "暂无分布数据")
            return
        total = sum(max(0, value) for value in self.data.values()) or 1
        x = rect.left() + 16
        available = rect.width() - 32
        colors = ["#2f7d4f", "#6aa84f", "#8fae3f", "#c69c38", "#b7654a", "#5f9ea0"]
        for index, (label, value) in enumerate(self.data.items()):
            width = available * max(0, value) / total
            bar = QRectF(x, rect.center().y() - 22, width, 44)
            gradient = QLinearGradient(bar.topLeft(), bar.topRight())
            gradient.setColorAt(0, QColor(colors[index % len(colors)]).lighter(120))
            gradient.setColorAt(1, QColor(colors[index % len(colors)]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(bar, 8, 8)
            painter.setPen(QColor("#203a2c"))
            painter.drawText(QRectF(x, rect.bottom() + 7, max(width, 64), 22), Qt.AlignmentFlag.AlignCenter, label)
            painter.drawText(QRectF(x, rect.center().y() - 11, max(width, 40), 22), Qt.AlignmentFlag.AlignCenter, f"{value:.0f}")
            x += width


class WorkbenchGauge(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.score = 0.0
        self.caption = "综合评分"
        self.setMinimumHeight(190)

    def set_score(self, score: float, caption: str = "综合评分") -> None:
        self.score = max(0, min(100, score))
        self.caption = caption
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(16, 16, -16, -16)
        radius = min(rect.width(), rect.height()) * 0.36
        center = QPointF(rect.center().x(), rect.center().y() + 16)
        painter.setPen(QPen(QColor("#dbe7d9"), 16, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2), 210 * 16, -240 * 16)
        painter.setPen(QPen(self._color(), 16, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(
            QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
            210 * 16,
            int(-240 * 16 * self.score / 100),
        )
        painter.setPen(QColor("#203a2c"))
        painter.setFont(QFont("", 28, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self.score:.0f}")
        painter.setFont(QFont("", 12))
        painter.setPen(QColor("#60766b"))
        painter.drawText(rect.adjusted(0, 92, 0, 0), Qt.AlignmentFlag.AlignCenter, self.caption)

    def _color(self) -> QColor:
        if self.score >= 80:
            return QColor("#2f7d4f")
        if self.score >= 60:
            return QColor("#73a143")
        if self.score >= 40:
            return QColor("#c69232")
        return QColor("#b94f4f")


class SparkLineChart(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.values: list[float] = []
        self.setMinimumHeight(190)

    def set_values(self, values: list[float]) -> None:
        self.values = values[-18:]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(20, 20, -20, -28)
        painter.setPen(QPen(QColor("#d7e4d5"), 1))
        for step in range(4):
            y = rect.top() + rect.height() * step / 3
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))
        if not self.values:
            painter.setPen(QColor("#75877d"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "暂无趋势数据")
            return
        high = max(self.values) or 1
        low = min(self.values)
        span = max(1, high - low)
        points = []
        for index, value in enumerate(self.values):
            x = rect.left() + rect.width() * index / max(1, len(self.values) - 1)
            y = rect.bottom() - rect.height() * (value - low) / span
            points.append(QPointF(x, y))
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        fill = QPainterPath(path)
        fill.lineTo(points[-1].x(), rect.bottom())
        fill.lineTo(points[0].x(), rect.bottom())
        fill.closeSubpath()
        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        gradient.setColorAt(0, QColor(47, 125, 79, 82))
        gradient.setColorAt(1, QColor(47, 125, 79, 8))
        painter.fillPath(fill, gradient)
        painter.setPen(QPen(QColor("#2f7d4f"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#2f7d4f"), 2))
        for point in points:
            painter.drawEllipse(point, 4, 4)


class WorkbenchTable(QTableWidget):
    selectionChangedSignal = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.itemSelectionChanged.connect(self.selectionChangedSignal.emit)

    def set_records(self, fields: list[dict[str, Any]], records: list[dict[str, Any]]) -> None:
        labels = ["编号"] + [field["label"] for field in fields]
        names = ["id"] + [field["name"] for field in fields]
        self.setColumnCount(len(labels))
        self.setHorizontalHeaderLabels(labels)
        self.setRowCount(len(records))
        for row_index, record in enumerate(records):
            for column_index, name in enumerate(names):
                value = record.get(name, "")
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, record.get("id"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if column_index <= 2 else Qt.AlignmentFlag.AlignLeft)
                self.setItem(row_index, column_index, item)
        self.resizeColumnsToContents()


class AdvancedWorkbenchPage(QWidget):
    table_name = ""
    title = ""
    subtitle = ""
    fields: list[dict[str, Any]] = []
    search_fields: list[str] = []
    filter_field = ""
    filter_label = "筛选"
    action_label = "执行业务动作"

    def __init__(self, repository: AppRepository, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.records: list[dict[str, Any]] = []
        self.filtered_records: list[dict[str, Any]] = []
        self.context = WorkbenchContext()
        self.metric_cards: list[MiniMetricCard] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.page_layout = QVBoxLayout(content)
        self.page_layout.setContentsMargins(18, 18, 18, 18)
        self.page_layout.setSpacing(14)
        scroll.setWidget(content)
        root.addWidget(scroll)
        self._build_header()
        self._build_metrics()
        self._build_toolbar()
        self._build_center()
        self._build_bottom()

    def _build_header(self) -> None:
        row = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel(self.title)
        title.setObjectName("Title")
        subtitle = QLabel(self.subtitle)
        subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        row.addLayout(title_box)
        row.addStretch(1)
        self.page_layout.addLayout(row)

    def _build_metrics(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(12)
        for index in range(6):
            card = MiniMetricCard()
            self.metric_cards.append(card)
            grid.addWidget(card, index // 3, index % 3)
        self.page_layout.addLayout(grid)

    def _build_toolbar(self) -> None:
        frame = QFrame()
        frame.setObjectName("Surface")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        self.keyword = QComboBox()
        self.keyword.setEditable(True)
        self.keyword.setMinimumWidth(240)
        self.keyword.lineEdit().setPlaceholderText("输入关键词检索")
        self.keyword.lineEdit().textChanged.connect(self._apply_filters)
        self.filter_box = QComboBox()
        self.filter_box.setMinimumWidth(180)
        self.filter_box.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(QLabel("检索"))
        layout.addWidget(self.keyword)
        layout.addWidget(QLabel(self.filter_label))
        layout.addWidget(self.filter_box)
        layout.addStretch(1)

        buttons: list[tuple[str, Callable[[], None], str]] = [
            ("新增", self.add_record, "Primary"),
            ("编辑", self.edit_record, ""),
            ("删除", self.delete_record, "Danger"),
            ("刷新", self.refresh, ""),
            (self.action_label, self.perform_primary_action, "Primary"),
            ("复制摘要", self.copy_summary, ""),
        ]
        for text, slot, object_name in buttons:
            button = QPushButton(text)
            if object_name:
                button.setObjectName(object_name)
            button.clicked.connect(slot)
            layout.addWidget(button)
        self.page_layout.addWidget(frame)

    def _build_center(self) -> None:
        row = QHBoxLayout()
        table_frame = QFrame()
        table_frame.setObjectName("Surface")
        table_layout = QVBoxLayout(table_frame)
        table_layout.addWidget(QLabel("业务数据"))
        self.table = WorkbenchTable()
        self.table.selectionChangedSignal.connect(self._selection_changed)
        table_layout.addWidget(self.table)

        insight_frame = QFrame()
        insight_frame.setObjectName("Surface")
        insight_layout = QVBoxLayout(insight_frame)
        insight_layout.addWidget(QLabel("智能研判"))
        self.gauge = WorkbenchGauge()
        insight_layout.addWidget(self.gauge)
        self.insight_list = QListWidget()
        self.insight_list.itemDoubleClicked.connect(self._insight_to_alert)
        insight_layout.addWidget(self.insight_list)
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMinimumHeight(115)
        insight_layout.addWidget(QLabel("摘要"))
        insight_layout.addWidget(self.summary)

        row.addWidget(table_frame, 7)
        row.addWidget(insight_frame, 4)
        self.page_layout.addLayout(row)

    def _build_bottom(self) -> None:
        row = QHBoxLayout()
        trend_frame = QFrame()
        trend_frame.setObjectName("Surface")
        trend_layout = QVBoxLayout(trend_frame)
        trend_layout.addWidget(QLabel("趋势"))
        self.trend = SparkLineChart()
        trend_layout.addWidget(self.trend)

        dist_frame = QFrame()
        dist_frame.setObjectName("Surface")
        dist_layout = QVBoxLayout(dist_frame)
        dist_layout.addWidget(QLabel("结构分布"))
        self.distribution = DistributionChart()
        dist_layout.addWidget(self.distribution)

        suggestion_frame = QFrame()
        suggestion_frame.setObjectName("Surface")
        suggestion_layout = QVBoxLayout(suggestion_frame)
        suggestion_layout.addWidget(QLabel("操作建议"))
        self.suggestion_list = QListWidget()
        self.suggestion_list.itemDoubleClicked.connect(self._suggestion_to_task)
        suggestion_layout.addWidget(self.suggestion_list)

        row.addWidget(trend_frame, 3)
        row.addWidget(dist_frame, 3)
        row.addWidget(suggestion_frame, 4)
        self.page_layout.addLayout(row)
        self.page_layout.addStretch(1)

    def refresh(self) -> None:
        self.records = self.repository.list_records(self.table_name)
        self._reload_filters()
        self._apply_filters()

    def build_context(self, records: list[dict[str, Any]], selected: dict[str, Any] | None) -> WorkbenchContext:
        return WorkbenchContext(records=records, selected=selected)

    def perform_primary_action(self) -> None:
        QMessageBox.information(self, self.title, "该菜单的业务动作位置已预留。")

    def add_record(self) -> None:
        dialog = RecordDialog(f"新增 - {self.title}", self.fields, parent=self)
        if dialog.exec():
            self.repository.create_record(self.table_name, dialog.payload())
            self.refresh()

    def edit_record(self) -> None:
        record = self._selected_record()
        if not record:
            return
        dialog = RecordDialog(f"编辑 - {self.title}", self.fields, record, self)
        if dialog.exec():
            self.repository.update_record(self.table_name, int(record["id"]), dialog.payload())
            self.refresh()

    def delete_record(self) -> None:
        record = self._selected_record()
        if not record:
            return
        confirm = QMessageBox.question(self, "确认删除", f"确定删除编号 {record['id']} 这条记录吗？")
        if confirm == QMessageBox.StandardButton.Yes:
            self.repository.delete_record(self.table_name, int(record["id"]))
            self.refresh()

    def copy_summary(self) -> None:
        QApplication.clipboard().setText(self.context.summary)
        QMessageBox.information(self, "已复制", "当前摘要已复制。")

    def _apply_filters(self) -> None:
        keyword = self.keyword.currentText().strip()
        filter_value = self.filter_box.currentData()
        rows = []
        for record in self.records:
            if filter_value not in (None, "") and str(record.get(self.filter_field, "")) != str(filter_value):
                continue
            if keyword and not self._match_keyword(record, keyword):
                continue
            rows.append(record)
        self.filtered_records = rows
        self.table.set_records(self.fields, rows)
        self._render_context()

    def _render_context(self) -> None:
        selected = self._selected_record(silent=True)
        if not selected and self.filtered_records:
            selected = self.filtered_records[0]
        self.context = self.build_context(self.filtered_records, selected)
        self._render_metrics()
        self._render_insights()
        self._render_suggestions()
        self.summary.setPlainText(self.context.summary)
        self.gauge.set_score(self.context.quality_score)
        self.trend.set_values(self.context.trend_values)
        self.distribution.set_data(self.context.distribution)

    def _render_metrics(self) -> None:
        metrics = self.context.metrics[:6]
        while len(metrics) < 6:
            metrics.append(WorkbenchMetric("", "待分析", "0", "", "暂无数据"))
        for card, metric in zip(self.metric_cards, metrics):
            card.set_metric(metric)

    def _render_insights(self) -> None:
        self.insight_list.clear()
        if not self.context.insights:
            self.insight_list.addItem(QListWidgetItem("暂无智能研判"))
            return
        for insight in self.context.insights:
            self.insight_list.addItem(QListWidgetItem(f"{insight.level}｜{insight.title}｜{insight.detail}"))

    def _render_suggestions(self) -> None:
        self.suggestion_list.clear()
        if not self.context.suggestions:
            self.suggestion_list.addItem(QListWidgetItem("暂无操作建议"))
            return
        for index, text in enumerate(self.context.suggestions, 1):
            self.suggestion_list.addItem(QListWidgetItem(f"{index}. {text}"))

    def _selection_changed(self) -> None:
        self._render_context()

    def _reload_filters(self) -> None:
        current = self.filter_box.currentData()
        self.filter_box.blockSignals(True)
        self.filter_box.clear()
        self.filter_box.addItem("全部", None)
        if self.filter_field:
            values = sorted({str(row.get(self.filter_field, "")) for row in self.records if row.get(self.filter_field, "") != ""})
            for value in values:
                self.filter_box.addItem(value, value)
        if current is not None:
            index = self.filter_box.findData(current)
            if index >= 0:
                self.filter_box.setCurrentIndex(index)
        self.filter_box.blockSignals(False)

    def _selected_record(self, silent: bool = False) -> dict[str, Any] | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.filtered_records):
            if not silent:
                QMessageBox.information(self, "请选择记录", "先在表格中选择一条记录。")
            return None
        return self.filtered_records[row]

    def _match_keyword(self, record: dict[str, Any], keyword: str) -> bool:
        if not self.search_fields:
            return keyword in " ".join(str(value) for value in record.values())
        return any(keyword in str(record.get(field, "")) for field in self.search_fields)

    def _insight_to_alert(self, item: QListWidgetItem) -> None:
        record = self.context.selected
        title = item.text().split("｜", 2)[1] if "｜" in item.text() else self.title
        self.repository.create_record(
            "alerts",
            {
                "title": f"{self.title}研判：{title[:18]}",
                "level": self._alert_level_from_text(item.text()),
                "source": "算法",
                "content": item.text(),
                "created_at": self._today(),
            },
        )
        QMessageBox.information(self, "已生成", "已根据该研判生成风险预警。")

    def _suggestion_to_task(self, item: QListWidgetItem) -> None:
        record = self.context.selected or {}
        plot_name = record.get("plot_name") or record.get("name") or "待指定"
        assignee = record.get("manager") or record.get("assignee") or "待安排"
        text = item.text().split(". ", 1)[-1]
        self.repository.create_record(
            "tasks",
            {
                "task_name": text[:24],
                "plot_name": plot_name,
                "assignee": assignee,
                "due_date": self._future_day(2),
                "progress": 0,
                "status": "待安排",
            },
        )
        QMessageBox.information(self, "已转任务", "已把建议转为作业任务。")

    def _alert_level_from_text(self, text: str) -> str:
        if "高" in text or "缺口" in text:
            return "高"
        if "中" in text or "偏低" in text:
            return "中"
        return "低"

    def _today(self) -> str:
        from datetime import date

        return date.today().isoformat()

    def _future_day(self, days: int) -> str:
        from datetime import date, timedelta

        return (date.today() + timedelta(days=days)).isoformat()

    def _score_level(self, score: float) -> str:
        if score >= 82:
            return "良好"
        if score >= 62:
            return "正常"
        if score >= 42:
            return "偏低"
        return "缺口"

    def _clamp(self, value: float, low: float = 0, high: float = 100) -> float:
        return max(low, min(high, value))

    def _avg(self, values: list[float], default: float = 0) -> float:
        return sum(values) / len(values) if values else default

    def _spread(self, values: list[float]) -> float:
        if not values:
            return 0
        avg = self._avg(values)
        return self._avg([abs(value - avg) for value in values])

    def _bucket_count(self, rows: list[dict[str, Any]], field: str) -> dict[str, float]:
        result: dict[str, float] = {}
        for row in rows:
            key = str(row.get(field, "未填写") or "未填写")
            result[key] = result.get(key, 0) + 1
        return result

    def _numeric_values(self, rows: list[dict[str, Any]], field: str) -> list[float]:
        values = []
        for row in rows:
            try:
                values.append(float(row.get(field, 0)))
            except (TypeError, ValueError):
                pass
        return values
