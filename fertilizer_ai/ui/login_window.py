from __future__ import annotations

from sqlite3 import IntegrityError
from pathlib import Path

from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fertilizer_ai import APP_NAME
from fertilizer_ai.core.auth_service import AuthService
from fertilizer_ai.data.repository import AppRepository
from fertilizer_ai.ui.main_window import MainWindow


class LoginScene(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        asset = Path(__file__).resolve().parents[1] / "assets" / "login_agri_park.png"
        self.hero = QPixmap(str(asset))
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        gradient = QLinearGradient(0, 0, rect.width(), rect.height())
        gradient.setColorAt(0.0, QColor("#06100f"))
        gradient.setColorAt(0.48, QColor("#0a1d1b"))
        gradient.setColorAt(1.0, QColor("#102c27"))
        painter.fillRect(rect, gradient)

        self._draw_data_streams(painter, rect)
        self._draw_right_visual(painter, rect)
        self._draw_bottom_glow(painter, rect)

    def _draw_data_streams(self, painter: QPainter, rect: QRect) -> None:
        for row in range(9):
            y = 40 + row * 54 + (self.phase % 54)
            color = QColor(97, 255, 191, 38 if row % 2 else 62)
            painter.setPen(QPen(color, 1))
            start = -160 + row * 23
            painter.drawLine(start, y, rect.width() + 80, y - 96)
        for col in range(11):
            x = 90 + col * 112 - (self.phase * 2 % 112)
            painter.setPen(QPen(QColor(180, 255, 225, 28), 1))
            painter.drawLine(x, 0, x + 140, rect.height())

        painter.setFont(QFont("Menlo", 8))
        painter.setPen(QColor(153, 255, 210, 52))
        for i in range(16):
            x = 40 + (i * 97 + self.phase * 3) % max(1, rect.width() - 80)
            y = 36 + (i * 61) % max(1, rect.height() - 80)
            painter.drawText(x, y, "01  AI  NPK  SENSOR")

    def _draw_right_visual(self, painter: QPainter, rect: QRect) -> None:
        visual_rect = QRect(int(rect.width() * 0.48), 44, int(rect.width() * 0.47), rect.height() - 88)
        center = visual_rect.center()
        glow = QRadialGradient(float(center.x()), float(center.y()), visual_rect.width() * 0.62)
        glow.setColorAt(0.0, QColor(92, 255, 188, 92))
        glow.setColorAt(0.58, QColor(70, 176, 139, 32))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(visual_rect.adjusted(-60, -40, 60, 40), glow)

        if not self.hero.isNull():
            scaled = self.hero.scaled(
                visual_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            source_x = max(0, int((scaled.width() - visual_rect.width()) * 0.54))
            source_y = max(0, int((scaled.height() - visual_rect.height()) * 0.5))
            painter.setOpacity(0.94)
            painter.drawPixmap(visual_rect, scaled, QRect(source_x, source_y, visual_rect.width(), visual_rect.height()))
            painter.setOpacity(1.0)

        painter.setPen(QPen(QColor(193, 255, 226, 82), 1))
        painter.setBrush(QColor(255, 255, 255, 18))
        painter.drawRoundedRect(visual_rect.adjusted(8, 10, -8, -10), 22, 22)

    def _draw_bottom_glow(self, painter: QPainter, rect: QRect) -> None:
        base = QRect(int(rect.width() * 0.52), rect.height() - 90, int(rect.width() * 0.38), 38)
        center = base.center()
        gradient = QRadialGradient(float(center.x()), float(center.y()), base.width() * 0.55)
        gradient.setColorAt(0.0, QColor(114, 255, 201, 125))
        gradient.setColorAt(0.55, QColor(79, 192, 145, 50))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(base.adjusted(-60, -42, 60, 48), gradient)

    def _tick(self) -> None:
        self.phase = (self.phase + 1) % 720
        self.update()


class LoginWindow(QDialog):
    def __init__(self, repository: AppRepository) -> None:
        super().__init__()
        self.repository = repository
        self.auth_service = AuthService(repository)
        self.main_window: MainWindow | None = None
        self.login_locked = False
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1180, 720)
        self._build_ui()
        self._load_defaults()

    def _build_ui(self) -> None:
        self.setObjectName("LoginWindow")
        scene = LoginScene(self)
        root = QHBoxLayout(scene)
        root.setContentsMargins(58, 54, 58, 54)
        root.setSpacing(28)

        panel = QFrame()
        panel.setObjectName("GlassLoginPanel")
        panel.setFixedWidth(420)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(34, 34, 34, 34)
        layout.setSpacing(14)

        badge = QLabel("AI PRECISION FERTILIZATION")
        badge.setObjectName("LoginBadge")

        title = QLabel(APP_NAME)
        title.setObjectName("LoginTitle")
        hint = QLabel("登录后进入田间精准施肥业务工作台")
        hint.setObjectName("LoginHint")
        hint.setWordWrap(True)

        self.username = QLineEdit()
        self.username.setObjectName("LoginInput")
        self.username.setPlaceholderText("用户名")
        self.password = QLineEdit()
        self.password.setObjectName("LoginInput")
        self.password.setPlaceholderText("密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.status_label = QLabel("默认账号：admin / admin123")
        self.status_label.setObjectName("LoginStatus")
        self.status_label.setWordWrap(True)

        self.remember_user = QCheckBox("记住账号")
        self.remember_user.setChecked(True)
        self.show_password = QCheckBox("显示密码")
        self.show_password.toggled.connect(self._toggle_password)
        options = QHBoxLayout()
        options.addWidget(self.remember_user)
        options.addWidget(self.show_password)
        options.addStretch(1)

        actions = QHBoxLayout()
        self.login_btn = QPushButton("登录")
        self.login_btn.setObjectName("LoginPrimary")
        register_btn = QPushButton("注册")
        register_btn.setObjectName("LoginSecondary")
        fill_btn = QPushButton("填入默认账号")
        fill_btn.setObjectName("LoginSecondary")
        self.login_btn.clicked.connect(self.login)
        register_btn.clicked.connect(self.register)
        fill_btn.clicked.connect(self.fill_default_account)
        actions.addWidget(self.login_btn)
        actions.addWidget(register_btn)
        actions.addWidget(fill_btn)

        self.username.textChanged.connect(self._validate_inputs)
        self.password.textChanged.connect(self._validate_inputs)
        self.username.returnPressed.connect(self.login)
        self.password.returnPressed.connect(self.login)

        account_label = QLabel("账号")
        account_label.setObjectName("LoginFieldLabel")
        password_label = QLabel("密码")
        password_label.setObjectName("LoginFieldLabel")

        layout.addWidget(badge)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(18)
        layout.addWidget(account_label)
        layout.addWidget(self.username)
        layout.addWidget(password_label)
        layout.addWidget(self.password)
        layout.addLayout(options)
        layout.addWidget(self.status_label)
        layout.addSpacing(10)
        layout.addLayout(actions)
        layout.addStretch(1)

        root.addWidget(panel)
        root.addStretch(1)
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(scene)

    def login(self) -> None:
        if self.login_locked:
            return
        self._set_busy(True)
        result = self.auth_service.login(self.username.text(), self.password.text())
        if not result.ok:
            self._set_busy(False)
            self.status_label.setText(result.message)
            if result.locked_seconds:
                self._lock_login_button(result.locked_seconds)
            else:
                QMessageBox.warning(self, "登录失败", result.message)
            return
        self._save_preferences()
        self.status_label.setText("登录成功，正在进入系统。")
        self.main_window = MainWindow(self.repository, result.user)
        self.main_window.show()
        self.close()

    def register(self) -> None:
        username = self.username.text().strip()
        password = self.password.text()
        try:
            self.repository.register_user(username, password)
        except IntegrityError:
            QMessageBox.warning(self, "注册失败", "用户名已经存在。")
        except Exception as exc:
            QMessageBox.warning(self, "注册失败", str(exc))
        else:
            QMessageBox.information(self, "注册成功", "账号已创建，可以直接登录。")

    def fill_default_account(self) -> None:
        self.username.setText("admin")
        self.password.setText("admin123")
        self.status_label.setText("已填入默认账号，可以直接登录。")

    def _load_defaults(self) -> None:
        remembered = self.repository.preference("remember_username", "admin")
        self.username.setText(remembered or "admin")
        self.password.setText("admin123")
        self._validate_inputs()

    def _save_preferences(self) -> None:
        if self.remember_user.isChecked():
            self.repository.set_preference("remember_username", self.username.text().strip())
        else:
            self.repository.set_preference("remember_username", "")

    def _toggle_password(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.password.setEchoMode(mode)

    def _validate_inputs(self) -> None:
        username = self.username.text().strip()
        password = self.password.text()
        ready = len(username) >= 3 and len(password) >= 6 and not any(ch.isspace() for ch in username)
        self.login_btn.setEnabled(ready and not self.login_locked)
        if not ready:
            self.status_label.setText("用户名至少 3 位，密码至少 6 位，用户名不能含空格。")
        elif self.status_label.text().startswith("用户名至少"):
            self.status_label.setText("输入有效，可以登录。")

    def _set_busy(self, busy: bool) -> None:
        self.login_btn.setEnabled(not busy)
        self.login_btn.setText("验证中..." if busy else "登录")

    def _lock_login_button(self, seconds: int) -> None:
        self.login_locked = True
        self.login_btn.setEnabled(False)
        self.login_btn.setText(f"{seconds}s 后重试")
        self._remaining_seconds = seconds
        self._lock_timer = QTimer(self)
        self._lock_timer.setInterval(1000)
        self._lock_timer.timeout.connect(self._tick_lock)
        self._lock_timer.start()

    def _tick_lock(self) -> None:
        self._remaining_seconds -= 1
        if self._remaining_seconds <= 0:
            self._lock_timer.stop()
            self.login_locked = False
            self.login_btn.setText("登录")
            self._validate_inputs()
            self.status_label.setText("可以重新尝试登录。")
            return
        self.login_btn.setText(f"{self._remaining_seconds}s 后重试")
