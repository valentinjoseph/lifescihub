"""Configuration helpers backed by PostgreSQL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

from db.session import engine

DEFAULT_CONFIG: dict[str, Any] = {
    "MAX_ITEMS_PER_SOURCE": 25,
    "MAX_WORKERS": 8,
    "LISTING_SLEEP_SEC": 0.2,
    "ARTICLE_SLEEP_SEC": 0.15,
    "REQUEST_TIMEOUT_SEC": 25,
    "MIN_TITLE_LENGTH": 10,
    "EXPORT_RESULTS": True,
}


class ScrapingConfig:
    """Load and manage scraper settings from tech.tech_scraping_config."""

    def __init__(self, config_path: str | Path | None = None, overrides: dict[str, Any] | None = None):
        self.config_path = Path(config_path) if config_path else None
        self.config = self._load_config()
        if overrides:
            self.config.update({key: value for key, value in overrides.items() if value is not None})

    def _load_config(self) -> dict[str, Any]:
        config = dict(DEFAULT_CONFIG)
        with engine.begin() as connection:
            rows = connection.execute(
                text("SELECT param_name, param_value FROM tech.tech_scraping_config ORDER BY param_name")
            ).mappings().all()

        if not rows and self.config_path and self.config_path.exists():
            loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError(f"Config file {self.config_path} must contain a JSON object")
            config.update(loaded)
            return config

        for row in rows:
            raw_value = row["param_value"]
            if row["param_name"] == "EXPORT_RESULTS":
                config[row["param_name"]] = str(raw_value).strip().lower() in {"true", "1", "yes", "on"}
            elif row["param_name"] in {"MAX_ITEMS_PER_SOURCE", "MAX_WORKERS", "REQUEST_TIMEOUT_SEC", "MIN_TITLE_LENGTH"}:
                config[row["param_name"]] = int(raw_value)
            elif row["param_name"] in {"LISTING_SLEEP_SEC", "ARTICLE_SLEEP_SEC"}:
                config[row["param_name"]] = float(raw_value)
            else:
                config[row["param_name"]] = raw_value
        return config

    def ensure_file(self) -> Path | None:
        """Preserve a local JSON config file for bootstrap or inspection."""
        if not self.config_path:
            return None
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.config_path.write_text(
                json.dumps(DEFAULT_CONFIG, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return self.config_path

    def get_worker_count(self) -> int:
        return max(1, int(self.config["MAX_WORKERS"]))

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.config[key]
