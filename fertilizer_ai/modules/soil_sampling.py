from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any

from PyQt6.QtWidgets import QMessageBox

from fertilizer_ai.core.fertilizer_engine import PrecisionFertilizerEngine
from fertilizer_ai.core.models import SoilSample, WeatherProfile
from fertilizer_ai.data.repository import AppRepository
from fertilizer_ai.ui.form_dialog import RecordDialog
from fertilizer_ai.ui.workbench_page import AdvancedWorkbenchPage, WorkbenchContext, WorkbenchInsight, WorkbenchMetric


class SoilSamplingPageAnalyzer:
    title = '土壤检测'

    def __init__(self) -> None:
        self.engine = PrecisionFertilizerEngine()
        self.weights = {'覆盖': 0.18, '完整': 0.18, '新鲜': 0.16, '均衡': 0.14, '联动': 0.18, '风险': 0.16}

    def analyze(self, records: list[dict[str, Any]], selected: dict[str, Any] | None, all_data: dict[str, list[dict[str, Any]]]) -> WorkbenchContext:
        metrics = self.build_metrics(records, selected, all_data)
        insights = self.build_insights(records, selected, all_data)
        suggestions = self.build_suggestions(records, selected, all_data, insights)
        trend_values = self.build_trend(records)
        distribution = self.build_distribution(records)
        score = self.quality_score(metrics, insights, records)
        summary = self.build_summary(records, selected, insights, suggestions, score)
        return WorkbenchContext(records=records, all_data=all_data, selected=selected, metrics=metrics, insights=insights, suggestions=suggestions, summary=summary, trend_values=trend_values, distribution=distribution, quality_score=score)

    def build_metrics(self, records: list[dict[str, Any]], selected: dict[str, Any] | None, all_data: dict[str, list[dict[str, Any]]]) -> list[WorkbenchMetric]:
        completeness = self.completeness_score(records)
        freshness = self.freshness_score(records)
        balance = self.balance_score(records)
        risk = self.risk_pressure(records, all_data)
        action = self.action_pressure(records, all_data)
        return [
            WorkbenchMetric('total', '记录总数', str(len(records)), '条', '当前筛选范围'),
            WorkbenchMetric('completeness', '完整度', f'{completeness:.0f}', '分', self.score_phrase(completeness)),
            WorkbenchMetric('freshness', '新鲜度', f'{freshness:.0f}', '分', self.score_phrase(freshness)),
            WorkbenchMetric('balance', '结构均衡', f'{balance:.0f}', '分', self.score_phrase(balance)),
            WorkbenchMetric('risk', '风险压力', f'{risk:.0f}', '分', self.pressure_phrase(risk)),
            WorkbenchMetric('action', '行动压力', f'{action:.0f}', '分', self.pressure_phrase(action)),
        ]

    def build_insights(self, records: list[dict[str, Any]], selected: dict[str, Any] | None, all_data: dict[str, list[dict[str, Any]]]) -> list[WorkbenchInsight]:
        if not records:
            return [WorkbenchInsight('缺少业务数据', '高', '请先新增记录，再进行研判。', 20)]
        insights: list[WorkbenchInsight] = []
        checks = [
            ('信息完整度', self.completeness_score(records), '字段越完整，后续判断越稳定'),
            ('数据新鲜度', self.freshness_score(records), '近期数据更适合指导精准施肥'),
            ('结构均衡度', self.balance_score(records), '结构过度集中会降低决策覆盖面'),
            ('任务联动度', self.rule_task_link(records, all_data), '研判需要能落到作业任务'),
            ('预警联动度', self.rule_alert_link(records, all_data), '异常项需要能进入风险预警'),
            ('方案联动度', self.rule_decision_link(records, all_data), '业务数据应与施肥方案相互校验'),
        ]
        for title, score, detail in checks:
            level = '低' if score >= 78 else '中' if score >= 52 else '高'
            insights.append(WorkbenchInsight(title, level, f'{detail}，当前得分{score:.0f}。', score))
        selected_insight = self.selected_record_insight(selected)
        if selected_insight:
            insights.insert(0, selected_insight)
        insights.extend(self.domain_extra_insights(records, selected, all_data))
        return insights[:8]

    def build_suggestions(self, records: list[dict[str, Any]], selected: dict[str, Any] | None, all_data: dict[str, list[dict[str, Any]]], insights: list[WorkbenchInsight]) -> list[str]:
        suggestions = []
        if not records:
            suggestions.append(f'请先新增{self.title}记录，补齐业务基础数据。')
        if any(item.level == '高' for item in insights):
            suggestions.append('优先处理高等级研判项，并生成对应处置任务。')
        if self.completeness_score(records) < 70:
            suggestions.append('补齐空字段，避免后续算法只能使用默认假设。')
        if self.freshness_score(records) < 65:
            suggestions.append('安排一次数据复核，把最新田间情况录入系统。')
        suggestions.extend(self.domain_extra_suggestions(records, selected, all_data))
        if not suggestions:
            suggestions.append('当前状态稳定，可继续按计划推进。')
        return suggestions[:8]

    def build_summary(self, records: list[dict[str, Any]], selected: dict[str, Any] | None, insights: list[WorkbenchInsight], suggestions: list[str], score: float) -> str:
        selected_text = self.record_title(selected) if selected else '未选择具体记录'
        high_count = sum(1 for item in insights if item.level == '高')
        mid_count = sum(1 for item in insights if item.level == '中')
        suggestion = suggestions[0] if suggestions else '暂无建议。'
        return f'{self.title}当前共有{len(records)}条记录，选中对象为{selected_text}。综合评分{score:.0f}分，高等级研判{high_count}项，中等级研判{mid_count}项。{suggestion}'

    def domain_extra_insights(self, records: list[dict[str, Any]], selected: dict[str, Any] | None, all_data: dict[str, list[dict[str, Any]]]) -> list[WorkbenchInsight]:
        result: list[WorkbenchInsight] = []
        if selected:
            numeric = self.numeric_values([selected])
            if numeric and self.spread(numeric) > 80:
                result.append(WorkbenchInsight('数值波动偏大', '中', '选中记录存在差异较大的数值字段，建议复核来源。', 55))
        if len(records) < 3:
            result.append(WorkbenchInsight('样本数量偏少', '中', '当前记录数量较少，趋势图只能作为辅助判断。', 50))
        return result

    def domain_extra_suggestions(self, records: list[dict[str, Any]], selected: dict[str, Any] | None, all_data: dict[str, list[dict[str, Any]]]) -> list[str]:
        result = []
        if selected:
            result.append(f'围绕{self.record_title(selected)}做一次现场或数据复核。')
        if self.rule_task_link(records, all_data) < 70:
            result.append('把关键研判转为作业任务，形成责任闭环。')
        if self.rule_alert_link(records, all_data) < 70:
            result.append('对异常项生成预警，便于后续追踪。')
        return result

    def selected_record_insight(self, selected: dict[str, Any] | None) -> WorkbenchInsight | None:
        if not selected:
            return None
        score = self.row_completeness(selected)
        title = self.record_title(selected)
        if score >= 85:
            return WorkbenchInsight('选中记录可直接使用', '低', f'{title} 的字段完整度较好。', score)
        if score >= 60:
            return WorkbenchInsight('选中记录需要复核', '中', f'{title} 仍有字段可补充。', score)
        return WorkbenchInsight('选中记录信息不足', '高', f'{title} 缺少较多关键内容。', score)

    def quality_score(self, metrics: list[WorkbenchMetric], insights: list[WorkbenchInsight], records: list[dict[str, Any]]) -> float:
        values = []
        for metric in metrics:
            try:
                values.append(float(metric.value))
            except ValueError:
                pass
        base = self.avg(values, 55)
        penalty = sum(12 for item in insights if item.level == '高') + sum(5 for item in insights if item.level == '中')
        bonus = min(10, len(records) * 1.5)
        return self.clamp(base - penalty * 0.35 + bonus)

    def build_trend(self, records: list[dict[str, Any]]) -> list[float]:
        field = self.first_numeric_field(records)
        if field:
            return [self.to_float(row.get(field), 0) for row in records[-18:]]
        running = 0.0
        values = []
        for row in records[-18:]:
            running += self.row_completeness(row)
            values.append(running / max(1, len(values) + 1))
        return values

    def build_distribution(self, records: list[dict[str, Any]]) -> dict[str, float]:
        field = self.distribution_field(records)
        if not field:
            return {'暂无分类': float(len(records))}
        counter = Counter(str(row.get(field, '未填写') or '未填写') for row in records)
        return {key: float(value) for key, value in counter.most_common(6)}

    def completeness_score(self, records: list[dict[str, Any]]) -> float:
        return self.avg([self.row_completeness(row) for row in records], 0)

    def row_completeness(self, row: dict[str, Any]) -> float:
        visible = [key for key in row.keys() if key != 'id']
        if not visible:
            return 0
        filled = sum(1 for key in visible if str(row.get(key, '')).strip() not in {'', 'None'})
        return self.clamp(filled / len(visible) * 100)

    def freshness_score(self, records: list[dict[str, Any]]) -> float:
        ages = []
        for row in records:
            for key in ['created_at', 'sampling_date', 'observed_at', 'due_date']:
                if row.get(key):
                    ages.append(self.days_since(str(row[key])))
                    break
        if not records:
            return 0
        if not ages:
            return 70
        return self.clamp(100 - self.avg(ages) * 2.8)

    def balance_score(self, records: list[dict[str, Any]]) -> float:
        if len(records) <= 1:
            return 64 if records else 0
        field = self.distribution_field(records)
        if not field:
            return 70
        counts = list(Counter(str(row.get(field, '')) for row in records).values())
        return self.clamp(100 - self.spread([float(value) for value in counts]) * 18)

    def risk_pressure(self, records: list[dict[str, Any]], all_data: dict[str, list[dict[str, Any]]]) -> float:
        pressure = 0.0
        for row in records:
            text = ' '.join(str(value) for value in row.values())
            if '高' in text or '延期' in text or '不足' in text:
                pressure += 18
            elif '中' in text or '偏低' in text:
                pressure += 9
        pressure += len(all_data.get('alerts', [])) * 3
        return self.clamp(pressure)

    def action_pressure(self, records: list[dict[str, Any]], all_data: dict[str, list[dict[str, Any]]]) -> float:
        tasks = all_data.get('tasks', [])
        pending = sum(1 for row in tasks if row.get('status') != '已完成')
        overdue = sum(1 for row in tasks if self.is_overdue(row.get('due_date', '')) and row.get('status') != '已完成')
        return self.clamp(pending * 9 + overdue * 20 + max(0, 5 - len(records)) * 6)

    def rule_task_link(self, records: list[dict[str, Any]], all_data: dict[str, list[dict[str, Any]]]) -> float:
        tasks = all_data.get('tasks', [])
        if not records:
            return 0
        return self.clamp(45 + len(tasks) * 8 - sum(12 for row in tasks if row.get('status') == '延期'))

    def rule_alert_link(self, records: list[dict[str, Any]], all_data: dict[str, list[dict[str, Any]]]) -> float:
        alerts = all_data.get('alerts', [])
        high = sum(1 for row in alerts if row.get('level') == '高')
        return self.clamp(75 - high * 12 + len(alerts) * 2)

    def rule_decision_link(self, records: list[dict[str, Any]], all_data: dict[str, list[dict[str, Any]]]) -> float:
        decisions = all_data.get('fertilizer_decisions', [])
        return self.clamp(38 + len(decisions) * 11)

    def first_numeric_field(self, records: list[dict[str, Any]]) -> str:
        for row in records:
            for key, value in row.items():
                if key == 'id':
                    continue
                try:
                    float(value)
                    return key
                except (TypeError, ValueError):
                    pass
        return ''

    def numeric_values(self, records: list[dict[str, Any]]) -> list[float]:
        values = []
        for row in records:
            for key, value in row.items():
                if key == 'id':
                    continue
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    pass
        return values

    def distribution_field(self, records: list[dict[str, Any]]) -> str:
        preferred = ['crop', 'status', 'role', 'category', 'level', 'source', 'risk_level', 'irrigation_available']
        available = set().union(*(row.keys() for row in records)) if records else set()
        for field in preferred:
            if field in available:
                return field
        return ''

    def record_title(self, row: dict[str, Any] | None) -> str:
        if not row:
            return '未选择'
        for key in ['name', 'plot_name', 'task_name', 'title', 'material_name', 'username', 'station']:
            if row.get(key):
                return str(row[key])
        return f"编号{row.get('id', '-')}"

    def score_phrase(self, score: float) -> str:
        if score >= 82:
            return '状态良好'
        if score >= 62:
            return '基本可用'
        if score >= 42:
            return '需要复核'
        return '缺口明显'

    def pressure_phrase(self, score: float) -> str:
        if score >= 70:
            return '压力较高'
        if score >= 45:
            return '压力中等'
        return '压力较低'

    def days_since(self, raw: str) -> int:
        for parser in (datetime.fromisoformat, date.fromisoformat):
            try:
                value = parser(raw)
                if isinstance(value, datetime):
                    value = value.date()
                return (date.today() - value).days
            except ValueError:
                pass
        return 60

    def is_overdue(self, raw: str) -> bool:
        try:
            return date.fromisoformat(str(raw)) < date.today()
        except ValueError:
            return False

    def to_float(self, value: Any, default: float = 0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def avg(self, values: list[float], default: float = 0) -> float:
        return sum(values) / len(values) if values else default

    def spread(self, values: list[float]) -> float:
        if not values:
            return 0
        avg = self.avg(values)
        return self.avg([abs(value - avg) for value in values])

    def clamp(self, value: float, low: float = 0, high: float = 100) -> float:
        return max(low, min(high, value))


class SoilSamplingPage(AdvancedWorkbenchPage):
    table_name = 'soil_samples'
    title = '土壤检测'
    subtitle = '录入土壤养分检测结果，作为精准施肥算法的核心输入。'
    filter_label = '作物'
    filter_field = 'crop'
    action_label = '生成土壤复核任务'
    fields = [
        {'name': 'plot_name', 'label': '地块名称'},
        {'name': 'crop', 'label': '作物', 'type': 'choice', 'choices': ['水稻', '玉米', '小麦', '番茄', '苹果', '其他']},
        {'name': 'area_mu', 'label': '面积(亩)', 'type': 'float', 'min': 0, 'max': 1000000},
        {'name': 'ph', 'label': '酸碱度', 'type': 'float', 'min': 0, 'max': 1000000},
        {'name': 'organic_matter', 'label': '有机质', 'type': 'float', 'min': 0, 'max': 1000000},
        {'name': 'nitrogen', 'label': '氮', 'type': 'float', 'min': 0, 'max': 1000000},
        {'name': 'phosphorus', 'label': '磷', 'type': 'float', 'min': 0, 'max': 1000000},
        {'name': 'potassium', 'label': '钾', 'type': 'float', 'min': 0, 'max': 1000000},
        {'name': 'moisture', 'label': '含水率', 'type': 'float', 'min': 0, 'max': 1000000},
        {'name': 'sampling_date', 'label': '采样日期', 'type': 'date'}
    ]
    search_fields = ['plot_name', 'crop', 'sampling_date']

    def __init__(self, repository: AppRepository, parent=None) -> None:
        self.analyzer = SoilSamplingPageAnalyzer()
        super().__init__(repository, parent)

    def build_context(self, records: list[dict[str, Any]], selected: dict[str, Any] | None) -> WorkbenchContext:
        return self.analyzer.analyze(records, selected, self._all_data())

    def perform_primary_action(self) -> None:
        handler = getattr(self, '_domain_primary_action', None)
        if handler:
            handler()
            return
        selected = self.context.selected
        if not selected:
            QMessageBox.information(self, self.title, '请先选择一条记录。')
            return
        self.repository.create_record('tasks', {'task_name': self.action_label, 'plot_name': selected.get('plot_name') or selected.get('name') or '待指定', 'assignee': selected.get('manager') or selected.get('assignee') or '待安排', 'due_date': self._future_day(2), 'progress': 0, 'status': '待安排'})
        QMessageBox.information(self, '已生成', f'已执行：{self.action_label}')
        self.refresh()

    def _all_data(self) -> dict[str, list[dict[str, Any]]]:
        data = {}
        for table in ['plots', 'soil_samples', 'weather_profiles', 'fertilizer_decisions', 'inventory', 'tasks', 'alerts']:
            try:
                data[table] = self.repository.list_records(table)
            except Exception:
                data[table] = []
        if hasattr(self.repository, 'list_users'):
            data['users'] = self.repository.list_users()
        return data



class SoilSamplingPageRuleBook:
    def __init__(self) -> None:
        self.names = []

    def 规则_001(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_002(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_003(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_004(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_005(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_006(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_007(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_008(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_009(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_010(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_011(self, row: dict[str, Any]) -> float:
        base = 11 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_012(self, row: dict[str, Any]) -> float:
        base = 12 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_013(self, row: dict[str, Any]) -> float:
        base = 13 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_014(self, row: dict[str, Any]) -> float:
        base = 14 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_015(self, row: dict[str, Any]) -> float:
        base = 15 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_016(self, row: dict[str, Any]) -> float:
        base = 16 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_017(self, row: dict[str, Any]) -> float:
        base = 0 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_018(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_019(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_020(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_021(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_022(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_023(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_024(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_025(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_026(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_027(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_028(self, row: dict[str, Any]) -> float:
        base = 11 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_029(self, row: dict[str, Any]) -> float:
        base = 12 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_030(self, row: dict[str, Any]) -> float:
        base = 13 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_031(self, row: dict[str, Any]) -> float:
        base = 14 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_032(self, row: dict[str, Any]) -> float:
        base = 15 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_033(self, row: dict[str, Any]) -> float:
        base = 16 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_034(self, row: dict[str, Any]) -> float:
        base = 0 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_035(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_036(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_037(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_038(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_039(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_040(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_041(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_042(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_043(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_044(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_045(self, row: dict[str, Any]) -> float:
        base = 11 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_046(self, row: dict[str, Any]) -> float:
        base = 12 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_047(self, row: dict[str, Any]) -> float:
        base = 13 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_048(self, row: dict[str, Any]) -> float:
        base = 14 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_049(self, row: dict[str, Any]) -> float:
        base = 15 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_050(self, row: dict[str, Any]) -> float:
        base = 16 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_051(self, row: dict[str, Any]) -> float:
        base = 0 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_052(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_053(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_054(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_055(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_056(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_057(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_058(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_059(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_060(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_061(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_062(self, row: dict[str, Any]) -> float:
        base = 11 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_063(self, row: dict[str, Any]) -> float:
        base = 12 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_064(self, row: dict[str, Any]) -> float:
        base = 13 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_065(self, row: dict[str, Any]) -> float:
        base = 14 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_066(self, row: dict[str, Any]) -> float:
        base = 15 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_067(self, row: dict[str, Any]) -> float:
        base = 16 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_068(self, row: dict[str, Any]) -> float:
        base = 0 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_069(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_070(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_071(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_072(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_073(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_074(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_075(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_076(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_077(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_078(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_079(self, row: dict[str, Any]) -> float:
        base = 11 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_080(self, row: dict[str, Any]) -> float:
        base = 12 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_081(self, row: dict[str, Any]) -> float:
        base = 13 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_082(self, row: dict[str, Any]) -> float:
        base = 14 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_083(self, row: dict[str, Any]) -> float:
        base = 15 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_084(self, row: dict[str, Any]) -> float:
        base = 16 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_085(self, row: dict[str, Any]) -> float:
        base = 0 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_086(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_087(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_088(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_089(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_090(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_091(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_092(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_093(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_094(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_095(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_096(self, row: dict[str, Any]) -> float:
        base = 11 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_097(self, row: dict[str, Any]) -> float:
        base = 12 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_098(self, row: dict[str, Any]) -> float:
        base = 13 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_099(self, row: dict[str, Any]) -> float:
        base = 14 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_100(self, row: dict[str, Any]) -> float:
        base = 15 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_101(self, row: dict[str, Any]) -> float:
        base = 16 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_102(self, row: dict[str, Any]) -> float:
        base = 0 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_103(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_104(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_105(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_106(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_107(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_108(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_109(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_110(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_111(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_112(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_113(self, row: dict[str, Any]) -> float:
        base = 11 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_114(self, row: dict[str, Any]) -> float:
        base = 12 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_115(self, row: dict[str, Any]) -> float:
        base = 13 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_116(self, row: dict[str, Any]) -> float:
        base = 14 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_117(self, row: dict[str, Any]) -> float:
        base = 15 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_118(self, row: dict[str, Any]) -> float:
        base = 16 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_119(self, row: dict[str, Any]) -> float:
        base = 0 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_120(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_121(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_122(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_123(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_124(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_125(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_126(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_127(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_128(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_129(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_130(self, row: dict[str, Any]) -> float:
        base = 11 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_131(self, row: dict[str, Any]) -> float:
        base = 12 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_132(self, row: dict[str, Any]) -> float:
        base = 13 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_133(self, row: dict[str, Any]) -> float:
        base = 14 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_134(self, row: dict[str, Any]) -> float:
        base = 15 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_135(self, row: dict[str, Any]) -> float:
        base = 16 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_136(self, row: dict[str, Any]) -> float:
        base = 0 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_137(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_138(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_139(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_140(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_141(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_142(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_143(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_144(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_145(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_146(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_147(self, row: dict[str, Any]) -> float:
        base = 11 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_148(self, row: dict[str, Any]) -> float:
        base = 12 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_149(self, row: dict[str, Any]) -> float:
        base = 13 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_150(self, row: dict[str, Any]) -> float:
        base = 14 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_151(self, row: dict[str, Any]) -> float:
        base = 15 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_152(self, row: dict[str, Any]) -> float:
        base = 16 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_153(self, row: dict[str, Any]) -> float:
        base = 0 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_154(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_155(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_156(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_157(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_158(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_159(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_160(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_161(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_162(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_163(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_164(self, row: dict[str, Any]) -> float:
        base = 11 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_165(self, row: dict[str, Any]) -> float:
        base = 12 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_166(self, row: dict[str, Any]) -> float:
        base = 13 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_167(self, row: dict[str, Any]) -> float:
        base = 14 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_168(self, row: dict[str, Any]) -> float:
        base = 15 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_169(self, row: dict[str, Any]) -> float:
        base = 16 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_170(self, row: dict[str, Any]) -> float:
        base = 0 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_171(self, row: dict[str, Any]) -> float:
        base = 1 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

    def 规则_172(self, row: dict[str, Any]) -> float:
        base = 2 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 4.0))

    def 规则_173(self, row: dict[str, Any]) -> float:
        base = 3 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 5.0))

    def 规则_174(self, row: dict[str, Any]) -> float:
        base = 4 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 6.0))

    def 规则_175(self, row: dict[str, Any]) -> float:
        base = 5 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 7.0))

    def 规则_176(self, row: dict[str, Any]) -> float:
        base = 6 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 8.0))

    def 规则_177(self, row: dict[str, Any]) -> float:
        base = 7 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 9.0))

    def 规则_178(self, row: dict[str, Any]) -> float:
        base = 8 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 10.0))

    def 规则_179(self, row: dict[str, Any]) -> float:
        base = 9 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 11.0))

    def 规则_180(self, row: dict[str, Any]) -> float:
        base = 10 + len([value for value in row.values() if str(value).strip()])
        return max(0.0, min(100.0, base * 3.0))

