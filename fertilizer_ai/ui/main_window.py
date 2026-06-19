from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from fertilizer_ai import APP_NAME
from fertilizer_ai.core.hot_reload import HotReloadWatcher
from fertilizer_ai.data.repository import AppRepository
from fertilizer_ai.modules.alert_center import AlertCenterPage
from fertilizer_ai.modules.dashboard import DashboardPage
from fertilizer_ai.modules.fertilizer_decision import FertilizerDecisionPage
from fertilizer_ai.modules.inventory_management import InventoryManagementPage
from fertilizer_ai.modules.plot_management import PlotManagementPage
from fertilizer_ai.modules.reports_center import ReportsCenterPage
from fertilizer_ai.modules.soil_sampling import SoilSamplingPage
from fertilizer_ai.modules.task_center import TaskCenterPage
from fertilizer_ai.modules.user_center import UserCenterPage
from fertilizer_ai.modules.weather_center import WeatherCenterPage


class MainWindow(QMainWindow):
    def __init__(self, repository: AppRepository, current_user: dict) -> None:
        super().__init__()
        self.repository = repository
        self.current_user = current_user
        self.setWindowTitle(f"{APP_NAME} - {current_user['username']}")
        self.resize(1240, 780)
        self.pages = []
        self._build_ui()
        self._start_hot_reload()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.menu = QListWidget()
        self.menu.setFixedWidth(190)
        self.stack = QStackedWidget()
        layout.addWidget(self.menu)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        page_specs = [
            ("决策驾驶舱", DashboardPage(self.repository)),
            ("用户与权限", UserCenterPage(self.repository, self.current_user)),
            ("地块档案", PlotManagementPage(self.repository)),
            ("土壤检测", SoilSamplingPage(self.repository)),
            ("气象水分", WeatherCenterPage(self.repository)),
            ("施肥决策", FertilizerDecisionPage(self.repository)),
            ("肥料库存", InventoryManagementPage(self.repository)),
            ("作业任务", TaskCenterPage(self.repository)),
            ("风险预警", AlertCenterPage(self.repository)),
            ("报表分析", ReportsCenterPage(self.repository)),
        ]
        for name, page in page_specs:
            item = QListWidgetItem(name)
            self.menu.addItem(item)
            self.stack.addWidget(page)
            self.pages.append(page)

        self.menu.currentRowChanged.connect(self._page_changed)
        self.menu.setCurrentRow(0)
        self.statusBar().showMessage("系统已启动，热更新监听中。")

    def _page_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _start_hot_reload(self) -> None:
        project_dir = Path(__file__).resolve().parents[1]
        self.hot_reload = HotReloadWatcher(project_dir, self)
        self.hot_reload.changed.connect(self._on_source_changed)
        self.hot_reload.start()

    def _on_source_changed(self, path: str) -> None:
        self.statusBar().showMessage(f"检测到代码变化：{Path(path).name}，切换页面可刷新业务数据。", 6000)
