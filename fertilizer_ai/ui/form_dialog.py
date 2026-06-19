from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)


class RecordDialog(QDialog):
    def __init__(
        self,
        title: str,
        fields: list[dict[str, Any]],
        values: dict[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.fields = fields
        self.widgets: dict[str, Any] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(form)

        values = values or {}
        for field in fields:
            widget = self._build_widget(field, values.get(field["name"], field.get("default")))
            self.widgets[field["name"]] = widget
            form.addRow(field["label"], widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def payload(self) -> dict[str, Any]:
        result = {}
        for field in self.fields:
            name = field["name"]
            widget = self.widgets[name]
            kind = field.get("type", "text")
            if kind == "float":
                result[name] = float(widget.value())
            elif kind == "int":
                result[name] = int(widget.value())
            elif kind == "choice":
                result[name] = widget.currentText()
            elif kind == "date":
                result[name] = widget.date().toString("yyyy-MM-dd")
            else:
                result[name] = widget.text().strip()
        return result

    def _build_widget(self, field: dict[str, Any], value: Any):
        kind = field.get("type", "text")
        if kind == "float":
            widget = QDoubleSpinBox()
            widget.setRange(field.get("min", 0.0), field.get("max", 999999.0))
            widget.setDecimals(field.get("decimals", 2))
            widget.setValue(float(value or 0))
            return widget
        if kind == "int":
            widget = QSpinBox()
            widget.setRange(field.get("min", 0), field.get("max", 100))
            widget.setValue(int(value or 0))
            return widget
        if kind == "choice":
            widget = QComboBox()
            widget.addItems(field.get("choices", []))
            if value:
                index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)
            return widget
        if kind == "date":
            widget = QDateEdit()
            widget.setCalendarPopup(True)
            date_value = QDate.fromString(str(value), "yyyy-MM-dd") if value else QDate.currentDate()
            widget.setDate(date_value if date_value.isValid() else QDate.currentDate())
            return widget

        widget = QLineEdit()
        widget.setText("" if value is None else str(value))
        return widget
