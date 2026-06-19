from PyQt6.QtWidgets import QApplication


def apply_app_style(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QWidget {
            font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue";
            font-size: 14px;
            color: #22312b;
        }
        QMainWindow, QDialog {
            background: #f5f7f2;
        }
        QDialog#LoginWindow {
            background: #06100f;
        }
        QFrame#AuthPanel, QFrame#Surface {
            background: #ffffff;
            border: 1px solid #dce5d8;
            border-radius: 8px;
        }
        QFrame#GlassLoginPanel {
            background: rgba(230, 255, 244, 33);
            border: 1px solid rgba(196, 255, 226, 128);
            border-radius: 22px;
        }
        QLabel#LoginBadge {
            color: #9ff8d1;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0;
        }
        QLabel#LoginTitle {
            color: #f2fff9;
            font-size: 30px;
            font-weight: 800;
        }
        QLabel#LoginHint {
            color: rgba(221, 255, 241, 185);
            font-size: 15px;
            line-height: 1.5;
        }
        QLabel#LoginFieldLabel {
            color: rgba(238, 255, 247, 220);
            font-size: 14px;
            font-weight: 600;
        }
        QLabel#LoginStatus {
            color: #a8f7d3;
            font-size: 13px;
        }
        QLineEdit#LoginInput {
            min-height: 46px;
            border: 1px solid rgba(169, 255, 214, 140);
            border-radius: 12px;
            background: rgba(9, 30, 27, 138);
            color: #f7fffb;
            padding: 6px 14px;
            selection-background-color: #2e9e72;
        }
        QLineEdit#LoginInput:focus {
            border: 1px solid #7dffd0;
            background: rgba(12, 42, 37, 180);
        }
        QFrame#GlassLoginPanel QCheckBox {
            color: rgba(235, 255, 246, 214);
            spacing: 8px;
        }
        QFrame#GlassLoginPanel QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 5px;
            border: 1px solid rgba(176, 255, 217, 140);
            background: rgba(255, 255, 255, 36);
        }
        QFrame#GlassLoginPanel QCheckBox::indicator:checked {
            background: #67f5bb;
            border-color: #67f5bb;
        }
        QPushButton#LoginPrimary {
            min-height: 44px;
            border-radius: 12px;
            border: 1px solid #6dffbf;
            background: #0fa36c;
            color: #ffffff;
            font-weight: 800;
            padding: 6px 22px;
        }
        QPushButton#LoginPrimary:hover {
            background: #13bd7d;
        }
        QPushButton#LoginPrimary:disabled {
            background: rgba(69, 117, 96, 120);
            border-color: rgba(148, 204, 177, 100);
            color: rgba(255, 255, 255, 150);
        }
        QPushButton#LoginSecondary {
            min-height: 44px;
            border-radius: 12px;
            border: 1px solid rgba(185, 255, 222, 145);
            background: rgba(255, 255, 255, 34);
            color: #ecfff7;
            font-weight: 700;
            padding: 6px 16px;
        }
        QPushButton#LoginSecondary:hover {
            background: rgba(112, 255, 190, 60);
        }
        QLabel#Title {
            font-size: 24px;
            font-weight: 700;
            color: #203a2c;
        }
        QLabel#Hint, QLabel#Muted {
            color: #64756c;
        }
        QPushButton {
            min-height: 32px;
            border-radius: 6px;
            border: 1px solid #9cb69e;
            background: #ffffff;
            padding: 5px 12px;
        }
        QPushButton:hover {
            background: #edf5ec;
        }
        QPushButton#Primary {
            background: #2f7d4f;
            border-color: #2f7d4f;
            color: white;
            font-weight: 600;
        }
        QPushButton#Danger {
            border-color: #c97878;
            color: #9e2f2f;
        }
        QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit {
            min-height: 30px;
            border: 1px solid #cbd8cc;
            border-radius: 6px;
            background: #ffffff;
            padding: 4px 8px;
        }
        QTableWidget {
            background: #ffffff;
            border: 1px solid #dce5d8;
            border-radius: 6px;
            gridline-color: #edf1ea;
            selection-background-color: #dbeedb;
        }
        QHeaderView::section {
            background: #eef4eb;
            padding: 7px;
            border: 0;
            border-right: 1px solid #dce5d8;
            font-weight: 600;
        }
        QListWidget {
            background: #ecf3e9;
            border: 0;
            padding: 8px;
        }
        QListWidget::item {
            min-height: 38px;
            padding: 6px 10px;
            border-radius: 6px;
        }
        QListWidget::item:selected {
            background: #2f7d4f;
            color: #ffffff;
        }
        QStatusBar {
            background: #edf3ea;
        }
        """
    )
