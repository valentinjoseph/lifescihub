"""Homelab-friendly web wrapper for the Life Science Watch pipeline."""

from __future__ import annotations

import os
import sqlite3
import threading
from argparse import Namespace
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from sqlalchemy import text

from core.config import API_ENABLE_DOCS, API_TITLE, API_VERSION
from db.session import engine
from orchestration.LS_MAIN_REFACTORED import PROJECT_ROOT, run_pipeline


app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    docs_url="/docs" if API_ENABLE_DOCS else None,
    redoc_url="/redoc" if API_ENABLE_DOCS else None,
    openapi_url="/openapi.json" if API_ENABLE_DOCS else None,
)
_run_lock = threading.Lock()
RUN_TOKEN = os.getenv("LSW_RUN_TOKEN")


def _default_paths() -> dict[str, str]:
    data_dir = PROJECT_ROOT / "data"
    outputs_dir = PROJECT_ROOT / "outputs"
    return {
        "sources": os.getenv("LSW_SOURCES", str(data_dir / "sources.csv")),
        "load_config": os.getenv("LSW_LOAD_CONFIG", str(data_dir / "load_config.csv")),
        "scraping_config": os.getenv("LSW_SCRAPING_CONFIG", str(data_dir / "scraping_config.json")),
        "db_path": os.getenv("LSW_DB_PATH", str(data_dir / "lifescience_watch.db")),
        "output_dir": os.getenv("LSW_OUTPUT_DIR", str(outputs_dir)),
    }


def _pipeline_args(dry_run: bool = False, max_workers: int | None = None, verbose: bool = False) -> Namespace:
    paths = _default_paths()
    return Namespace(
        sources=paths["sources"],
        load_config=paths["load_config"],
        scraping_config=paths["scraping_config"],
        db_path=paths["db_path"],
        output_dir=paths["output_dir"],
        max_workers=max_workers,
        dry_run=dry_run,
        verbose=verbose,
    )


def _db_info() -> dict[str, Any]:
    db_path = Path(_default_paths()["db_path"])
    if not db_path.exists():
        return {"exists": False}

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        tables = [row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        latest_run = connection.execute(
            """
            SELECT run_id, run_name, company_name, run_status, records_inserted, run_end_ts
            FROM load_monitoring
            ORDER BY run_end_ts DESC
            LIMIT 1
            """
        ).fetchone()

    return {
        "exists": True,
        "tables": tables,
        "latest_run": dict(latest_run) if latest_run else None,
    }


def _postgres_info() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            current = connection.execute(
                text("SELECT current_database() AS db, current_user AS user")
            ).mappings().one()
            schemas = [
                row["schema_name"]
                for row in connection.execute(
                    text(
                        """
                        SELECT schema_name
                        FROM information_schema.schemata
                        WHERE schema_name IN ('public', 'tech')
                        ORDER BY schema_name
                        """
                    )
                ).mappings()
            ]
        return {
            "reachable": True,
            "current_database": current["db"],
            "current_user": current["user"],
            "schemas": schemas,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "error": str(exc),
        }


def _require_run_token(x_run_token: str | None) -> None:
    if not RUN_TOKEN:
        raise HTTPException(status_code=503, detail="Run token is not configured")
    if x_run_token != RUN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid run token")


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "lifescience_watch",
        "status": "ok",
        "endpoints": ["/health", "/status", "/run"],
    }


@app.get("/health")
def health(x_run_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_run_token(x_run_token)
    return {
        "status": "ok",
        "service": "lifescience_watch",
        "sqlite": _db_info(),
        "postgres": _postgres_info(),
        "lock_held": _run_lock.locked(),
    }


@app.get("/status")
def status(x_run_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_run_token(x_run_token)
    return {
        "service": "lifescience_watch",
        "sqlite": _db_info(),
        "postgres": _postgres_info(),
        "config": {
            "sources_configured": Path(_default_paths()["sources"]).exists(),
            "load_config_configured": Path(_default_paths()["load_config"]).exists(),
            "scraping_config_configured": Path(_default_paths()["scraping_config"]).exists(),
            "output_dir_exists": Path(_default_paths()["output_dir"]).exists(),
        },
    }


@app.post("/run")
def run_now(x_run_token: str | None = Header(default=None)) -> dict[str, Any]:
    _require_run_token(x_run_token)

    if not _run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A pipeline run is already in progress")

    try:
        exit_code = run_pipeline(_pipeline_args())
    finally:
        _run_lock.release()

    return {
        "service": "lifescience_watch",
        "exit_code": exit_code,
        "sqlite": _db_info(),
        "postgres": _postgres_info(),
    }
