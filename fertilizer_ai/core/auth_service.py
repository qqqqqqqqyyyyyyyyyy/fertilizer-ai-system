from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from fertilizer_ai.data.repository import AppRepository


@dataclass(slots=True)
class AuthResult:
    ok: bool
    message: str
    user: dict | None = None
    locked_seconds: int = 0


class AuthService:
    def __init__(self, repository: AppRepository) -> None:
        self.repository = repository
        self._failures: dict[str, list[datetime]] = {}
        self._locked_until: dict[str, datetime] = {}

    def login(self, username: str, password: str) -> AuthResult:
        username = username.strip()
        validation = self._validate(username, password)
        if validation:
            self.repository.record_login_attempt(username or "-", False, validation)
            return AuthResult(False, validation)

        locked = self._locked_until.get(username)
        now = datetime.now()
        if locked and locked > now:
            seconds = int((locked - now).total_seconds())
            return AuthResult(False, f"账号临时锁定，请 {seconds} 秒后再试。", locked_seconds=seconds)

        user = self.repository.authenticate(username, password)
        if user:
            self._failures.pop(username, None)
            self._locked_until.pop(username, None)
            self.repository.record_login_attempt(username, True, "登录成功")
            return AuthResult(True, "登录成功", user)

        self._add_failure(username)
        count = len(self._failures.get(username, []))
        message = f"用户名或密码不正确，剩余尝试次数 {max(0, 5 - count)}。"
        if count >= 5:
            locked_until = now + timedelta(seconds=45)
            self._locked_until[username] = locked_until
            message = "连续失败次数过多，账号已临时锁定 45 秒。"
        self.repository.record_login_attempt(username, False, message)
        return AuthResult(False, message)

    def _validate(self, username: str, password: str) -> str:
        if not username:
            return "请输入用户名。"
        if len(username) < 3:
            return "用户名至少 3 个字符。"
        if not password:
            return "请输入密码。"
        if len(password) < 6:
            return "密码至少 6 位。"
        if any(ch.isspace() for ch in username):
            return "用户名不能包含空格。"
        return ""

    def _add_failure(self, username: str) -> None:
        cutoff = datetime.now() - timedelta(minutes=10)
        failures = [time for time in self._failures.get(username, []) if time >= cutoff]
        failures.append(datetime.now())
        self._failures[username] = failures
