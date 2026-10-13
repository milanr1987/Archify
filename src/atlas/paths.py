"""Putanje aplikacije. Sve je relativno korijenu aplikacije, ne cwd-u."""
from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_APP_ROOT = PACKAGE_DIR.parents[1]
UI_DIR = PACKAGE_DIR / "ui"


class AppPaths:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else DEFAULT_APP_ROOT
        self.config_dir = self.root / "config"
        self.default_config = self.config_dir / "sources.local.json"
        self.example_config = self.config_dir / "sources.example.json"
        self.data_dir = self.root / "data"
        self.output_dir = self.root / "output"
        self.inventory = self.data_dir / "inventory.json"
        self.report = self.data_dir / "scan-report.md"
        self.catalog = self.output_dir / "index.html"
        self.lock = self.data_dir / ".atlas.lock"
        self.journal = self.data_dir / ".publish-journal.json"

    def resolve_config(self, value: str | None) -> Path:
        if not value:
            return self.default_config
        path = Path(value)
        return path if path.is_absolute() else self.root / path
