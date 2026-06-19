from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class HotReloadWatcher(QObject):
    changed = pyqtSignal(str)

    def __init__(self, watched_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.watched_dir = watched_dir
        self._snapshot: dict[Path, float] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(1200)
        self._timer.timeout.connect(self.scan)

    def start(self) -> None:
        self._snapshot = self._collect()
        self._timer.start()

    def scan(self) -> None:
        current = self._collect()
        changed_files = [
            str(path)
            for path, mtime in current.items()
            if self._snapshot.get(path) not in (None, mtime)
        ]
        self._snapshot = current
        if changed_files:
            self.changed.emit(changed_files[0])

    def _collect(self) -> dict[Path, float]:
        files = {}
        for path in self.watched_dir.rglob("*.py"):
            if "__pycache__" not in path.parts:
                files[path] = path.stat().st_mtime
        return files
