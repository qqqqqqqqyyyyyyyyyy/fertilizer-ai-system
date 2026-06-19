from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any


class AppRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else self._default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._seed()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("select * from users where username=?", (username.strip(),)).fetchone()
        if not row:
            return None
        if self._hash_password(password, row["salt"]) != row["password_hash"]:
            return None
        return dict(row)

    def register_user(self, username: str, password: str, role: str = "农技员") -> None:
        if len(username.strip()) < 3:
            raise ValueError("用户名至少 3 个字符")
        if len(password) < 6:
            raise ValueError("密码至少 6 位")
        salt = secrets.token_hex(12)
        password_hash = self._hash_password(password, salt)
        with self.connect() as conn:
            conn.execute(
                "insert into users(username, password_hash, salt, role, created_at) values(?,?,?,?,?)",
                (username.strip(), password_hash, salt, role, datetime.now().isoformat(timespec="seconds")),
            )

    def list_users(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select id, username, role, created_at from users order by id desc"
            ).fetchall()
        return [dict(row) for row in rows]

    def update_user_role(self, user_id: int, role: str) -> None:
        with self.connect() as conn:
            conn.execute("update users set role=? where id=?", (role, user_id))

    def delete_user(self, user_id: int) -> None:
        with self.connect() as conn:
            total = conn.execute("select count(*) as total from users").fetchone()["total"]
            if total <= 1:
                raise ValueError("至少保留一个用户")
            conn.execute("delete from users where id=?", (user_id,))

    def list_records(self, table: str) -> list[dict[str, Any]]:
        self._guard_table(table)
        with self.connect() as conn:
            rows = conn.execute(f"select * from {table} order by id desc").fetchall()
        return [dict(row) for row in rows]

    def create_record(self, table: str, values: dict[str, Any]) -> int:
        self._guard_table(table)
        payload = {k: v for k, v in values.items() if k != "id"}
        columns = ", ".join(payload)
        holders = ", ".join("?" for _ in payload)
        with self.connect() as conn:
            cursor = conn.execute(f"insert into {table}({columns}) values({holders})", tuple(payload.values()))
            return int(cursor.lastrowid)

    def update_record(self, table: str, record_id: int, values: dict[str, Any]) -> None:
        self._guard_table(table)
        payload = {k: v for k, v in values.items() if k != "id"}
        clause = ", ".join(f"{column}=?" for column in payload)
        with self.connect() as conn:
            conn.execute(f"update {table} set {clause} where id=?", (*payload.values(), record_id))

    def delete_record(self, table: str, record_id: int) -> None:
        self._guard_table(table)
        with self.connect() as conn:
            conn.execute(f"delete from {table} where id=?", (record_id,))

    def save_decision(self, payload: dict[str, Any]) -> int:
        payload.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        return self.create_record("fertilizer_decisions", payload)

    def overview_metrics(self) -> dict[str, Any]:
        with self.connect() as conn:
            plots = conn.execute("select count(*) as total from plots").fetchone()["total"]
            decisions = conn.execute("select count(*) as total from fertilizer_decisions").fetchone()["total"]
            avg_risk = conn.execute(
                "select avg(case risk_level when '高' then 3 when '中' then 2 else 1 end) as value "
                "from fertilizer_decisions"
            ).fetchone()["value"]
        return {"plots": plots, "decisions": decisions, "risk_index": round(avg_risk or 0, 2)}

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists users(
                    id integer primary key autoincrement,
                    username text not null unique,
                    password_hash text not null,
                    salt text not null,
                    role text not null,
                    created_at text not null
                );
                create table if not exists login_attempts(
                    id integer primary key autoincrement,
                    username text not null,
                    success integer not null,
                    message text not null,
                    created_at text not null
                );
                create table if not exists app_preferences(
                    key text primary key,
                    value text not null
                );
                create table if not exists plots(
                    id integer primary key autoincrement,
                    name text not null,
                    crop text not null,
                    area_mu real not null,
                    location text not null,
                    manager text not null,
                    status text not null
                );
                create table if not exists soil_samples(
                    id integer primary key autoincrement,
                    plot_name text not null,
                    crop text not null,
                    area_mu real not null,
                    ph real not null,
                    organic_matter real not null,
                    nitrogen real not null,
                    phosphorus real not null,
                    potassium real not null,
                    moisture real not null,
                    sampling_date text not null
                );
                create table if not exists weather_profiles(
                    id integer primary key autoincrement,
                    station text not null,
                    rainfall_7d real not null,
                    temperature_avg real not null,
                    evapotranspiration real not null,
                    irrigation_available text not null,
                    observed_at text not null
                );
                create table if not exists fertilizer_decisions(
                    id integer primary key autoincrement,
                    plot_name text not null,
                    crop text not null,
                    nitrogen_kg real not null,
                    phosphorus_kg real not null,
                    potassium_kg real not null,
                    organic_kg real not null,
                    risk_level text not null,
                    confidence real not null,
                    notes text not null,
                    created_at text not null
                );
                create table if not exists inventory(
                    id integer primary key autoincrement,
                    material_name text not null,
                    category text not null,
                    stock_kg real not null,
                    unit_price real not null,
                    supplier text not null
                );
                create table if not exists tasks(
                    id integer primary key autoincrement,
                    task_name text not null,
                    plot_name text not null,
                    assignee text not null,
                    due_date text not null,
                    progress integer not null,
                    status text not null
                );
                create table if not exists alerts(
                    id integer primary key autoincrement,
                    title text not null,
                    level text not null,
                    source text not null,
                    content text not null,
                    created_at text not null
                );
                """
            )

    def record_login_attempt(self, username: str, success: bool, message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "insert into login_attempts(username, success, message, created_at) values(?,?,?,?)",
                (username.strip(), 1 if success else 0, message, datetime.now().isoformat(timespec="seconds")),
            )

    def recent_login_attempts(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select username, success, message, created_at from login_attempts order by id desc limit ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def preference(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            row = conn.execute("select value from app_preferences where key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_preference(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "insert into app_preferences(key, value) values(?,?) "
                "on conflict(key) do update set value=excluded.value",
                (key, value),
            )

    def _seed(self) -> None:
        with self.connect() as conn:
            user_count = conn.execute("select count(*) as total from users").fetchone()["total"]
        if user_count == 0:
            self.register_user("admin", "admin123", "管理员")

        if not self.list_records("plots"):
            self.create_record("plots", {
                "name": "东区一号田",
                "crop": "水稻",
                "area_mu": 48.5,
                "location": "河湾示范区",
                "manager": "李青",
                "status": "生长期",
            })
        if not self.list_records("soil_samples"):
            self.create_record("soil_samples", {
                "plot_name": "东区一号田",
                "crop": "水稻",
                "area_mu": 48.5,
                "ph": 6.3,
                "organic_matter": 21.6,
                "nitrogen": 11.2,
                "phosphorus": 4.8,
                "potassium": 8.4,
                "moisture": 56.0,
                "sampling_date": date.today().isoformat(),
            })
        if not self.list_records("weather_profiles"):
            self.create_record("weather_profiles", {
                "station": "河湾气象点",
                "rainfall_7d": 24.0,
                "temperature_avg": 25.6,
                "evapotranspiration": 3.9,
                "irrigation_available": "是",
                "observed_at": date.today().isoformat(),
            })
        if not self.list_records("inventory"):
            self.create_record("inventory", {
                "material_name": "尿素",
                "category": "氮肥",
                "stock_kg": 1800.0,
                "unit_price": 2.7,
                "supplier": "绿源农资",
            })

    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()

    def _default_db_path(self) -> Path:
        if os.name == "nt":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            return base / "AI精准施肥决策系统" / "fertilizer_ai.db"
        return Path("data/fertilizer_ai.db")

    def _guard_table(self, table: str) -> None:
        allowed = {
            "plots",
            "soil_samples",
            "weather_profiles",
            "fertilizer_decisions",
            "inventory",
            "tasks",
            "alerts",
        }
        if table not in allowed:
            raise ValueError(f"不允许访问表：{table}")
