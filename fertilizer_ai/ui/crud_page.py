from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fertilizer_ai.data.repository import AppRepository
from fertilizer_ai.ui.form_dialog import RecordDialog


class CrudPage(QWidget):
    table_name = ""
    title = ""
    subtitle = ""
    fields: list[dict[str, Any]] = []

    def __init__(self, repository: AppRepository, parent=None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.records: list[dict[str, Any]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel(self.title)
        title.setObjectName("Title")
        subtitle = QLabel(self.subtitle)
        subtitle.setObjectName("Muted")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        head.addLayout(titles)
        head.addStretch(1)

        add_btn = QPushButton("新增")
        add_btn.setObjectName("Primary")
        edit_btn = QPushButton("编辑")
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("Danger")
        refresh_btn = QPushButton("刷新")
        add_btn.clicked.connect(self.add_record)
        edit_btn.clicked.connect(self.edit_record)
        delete_btn.clicked.connect(self.delete_record)
        refresh_btn.clicked.connect(self.refresh)
        for btn in (add_btn, edit_btn, delete_btn, refresh_btn):
            head.addWidget(btn)

        surface = QFrame()
        surface.setObjectName("Surface")
        surface_layout = QVBoxLayout(surface)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        surface_layout.addWidget(self.table)

        layout.addLayout(head)
        layout.addWidget(surface, 1)

    def refresh(self) -> None:
        self.records = self.repository.list_records(self.table_name)
        labels = ["ID"] + [field["label"] for field in self.fields]
        names = ["id"] + [field["name"] for field in self.fields]
        self.table.setColumnCount(len(labels))
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setRowCount(len(self.records))
        for row_index, record in enumerate(self.records):
            for column_index, name in enumerate(names):
                item = QTableWidgetItem(str(record.get(name, "")))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_index, column_index, item)
        self.table.resizeColumnsToContents()

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
        confirm = QMessageBox.question(self, "确认删除", f"确定删除 ID {record['id']} 这条记录吗？")
        if confirm == QMessageBox.StandardButton.Yes:
            self.repository.delete_record(self.table_name, int(record["id"]))
            self.refresh()

    def _selected_record(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.records):
            QMessageBox.information(self, "请选择记录", "先在表格中选择一条记录。")
            return None
        return self.records[row]
