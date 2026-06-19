import sys

from PyQt6.QtWidgets import QApplication

from fertilizer_ai import APP_NAME
from fertilizer_ai.data.repository import AppRepository
from fertilizer_ai.ui.login_window import LoginWindow
from fertilizer_ai.ui.styles import apply_app_style


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    apply_app_style(app)

    repository = AppRepository()
    login = LoginWindow(repository)
    login.show()

    return app.exec()
