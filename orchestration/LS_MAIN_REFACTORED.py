"""Standalone entry point for the Life Science Watch scraping pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.scraping_config import ScrapingConfig
from db.bootstrap import bootstrap_postgres
from db.session import engine
from core.monitoring import ScrapingMonitor
from core.scraper import RESULT_COLUMNS, scrape_sources
from db.table_manager import PostgresTableManager, ensure_schema_and_table, get_target_schema_and_table, merge_data
from utils.data_quality import aggregate_metrics, validate_scraped_data


LOGGER = logging.getLogger("lifescience_watch")
FLOW_NAME = "LS_SOURCE_SCRAPING"
CATALOG = "local"


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


def ensure_sources_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "COMPANY_NAME,SOURCE_1,SOURCE_2,SOURCE_3,SOURCE_4,SOURCE_5\n"
            "Moderna,https://investors.modernatx.com/news-releases/,,,,\n"
            "Pfizer,https://www.pfizer.com/news/press-releases/,,,,\n",
            encoding="utf-8",
        )


def ensure_load_config_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "COMPANY_NAME,FLOW_NAME,LOAD_TYPE,ACTIVE_FLAG\n"
            "Moderna,LS_SOURCE_SCRAPING,FULL,Y\n"
            "Pfizer,LS_SOURCE_SCRAPING,FULL,Y\n",
            encoding="utf-8",
        )


def load_sources_from_postgres() -> list[dict[str, str]]:
    with engine.begin() as connection:
        df_sources = pd.read_sql_query(
            text(
                """
                SELECT company_name, source_1, source_2, source_3, source_4, source_5
                FROM tech.ls_load_sources
                ORDER BY company_name
                """
            ),
            connection,
        ).fillna("")

    source_columns = [column for column in df_sources.columns if column.upper().startswith("SOURCE_")]
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _, row in df_sources.iterrows():
        company_name = str(row.get("company_name", "")).strip()
        if not company_name:
            continue
        for column in source_columns:
            url = str(row.get(column, "")).strip()
            if not url.startswith(("http://", "https://")):
                continue
            key = (company_name, url)
            if key in seen:
                continue
            seen.add(key)
            records.append({"company_name": company_name, "url": url})
    return records


def load_sources(path: Path) -> list[dict[str, str]]:
    ensure_sources_file(path)
    return load_sources_from_postgres()


def load_company_config(path: Path) -> dict[str, str]:
    ensure_load_config_file(path)
    with engine.begin() as connection:
        cfg_df = pd.read_sql_query(
            text(
                """
                SELECT flow_name, company_name, load_type, active_flag
                FROM tech.ls_load_config
                WHERE flow_name = :flow_name
                """
            ),
            connection,
            params={"flow_name": FLOW_NAME},
        ).fillna("")
    active_df = cfg_df[cfg_df["active_flag"].astype(str).str.upper() == "Y"]
    return {
        str(row["company_name"]).strip(): (str(row["load_type"]).strip().upper() or "FULL")
        for _, row in active_df.iterrows()
        if str(row["company_name"]).strip()
    }


def persist_company_config(path: Path, cfg_df: pd.DataFrame) -> None:
    del path
    rows = [
        {
            "flow_name": str(row["flow_name"]),
            "company_name": str(row["company_name"]),
            "load_type": str(row["load_type"]),
            "active_flag": str(row["active_flag"]),
        }
        for row in cfg_df.to_dict(orient="records")
    ]
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE tech.ls_load_config"))
        connection.execute(
            text(
                """
                INSERT INTO tech.ls_load_config (flow_name, company_name, load_type, active_flag)
                VALUES (:flow_name, :company_name, :load_type, :active_flag)
                """
            ),
            rows,
        )


def update_successful_companies_to_delta(path: Path, companies: list[str]) -> None:
    if not companies:
        return
    with engine.begin() as connection:
        cfg_df = pd.read_sql_query(
            text("SELECT flow_name, company_name, load_type, active_flag FROM tech.ls_load_config"),
            connection,
        ).fillna("")
    mask = cfg_df["company_name"].isin(companies) & (cfg_df["flow_name"] == FLOW_NAME)
    cfg_df.loc[mask & (cfg_df["load_type"] == "FULL"), "load_type"] = "DELTA"
    persist_company_config(path, cfg_df)


def filter_delta_records(df_company: pd.DataFrame, last_success_ts) -> pd.DataFrame:
    if last_success_ts is None or df_company.empty:
        return df_company
    published_dates = pd.to_datetime(df_company["published_date"], utc=True, errors="coerce")
    last_success = pd.Timestamp(last_success_ts)
    if last_success.tzinfo is None:
        last_success = last_success.tz_localize("UTC")
    else:
        last_success = last_success.tz_convert("UTC")
    return df_company[published_dates.isna() | (published_dates > last_success)].reset_index(drop=True)


def build_monitoring_metrics(df_company: pd.DataFrame, scrape_metrics: dict | None = None) -> dict:
    scrape_metrics = dict(scrape_metrics or {})
    eligible_count = 0 if df_company.empty else int(len(df_company))
    avg_response_time_ms = 0.0
    if not df_company.empty and "response_time_ms" in df_company:
        response_times = pd.to_numeric(df_company["response_time_ms"], errors="coerce").dropna()
        if not response_times.empty:
            avg_response_time_ms = float(response_times.mean())

    return {
        "urls_attempted": eligible_count,
        "urls_fetched": eligible_count,
        "parse_success_count": eligible_count,
        "avg_response_time_ms": avg_response_time_ms or float(scrape_metrics.get("avg_response_time_ms", 0.0)),
        "error_count": int(scrape_metrics.get("error_count", 0)),
        "unique_urls": 0 if df_company.empty else int(df_company["url"].nunique()),
    }


def export_results(df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "latest_results.csv"
    df.to_csv(output_file, index=False)
    LOGGER.info("Exported validated results to %s", output_file)


def run_pipeline(args: argparse.Namespace) -> int:
    run_id = str(uuid.uuid4())
    config = ScrapingConfig(args.scraping_config, overrides={"MAX_WORKERS": args.max_workers})
    config.ensure_file()

    sources_path = Path(args.sources)
    load_config_path = Path(args.load_config)
    db_path = Path(args.db_path)
    output_dir = Path(args.output_dir)

    bootstrap_postgres(sources_path, load_config_path, Path(args.scraping_config), db_path)

    sources = load_sources(sources_path)
    cfg_map = load_company_config(load_config_path)
    storage = PostgresTableManager()
    monitor = ScrapingMonitor(FLOW_NAME, run_id)

    LOGGER.info("Run ID: %s", run_id)
    LOGGER.info("Loaded %s company source URLs", len(sources))
    LOGGER.info("Loaded configuration for %s companies", len(cfg_map))

    if args.dry_run:
        LOGGER.info("Dry run complete. Sources, config, and PostgreSQL storage are ready.")
        return 0

    delta_cutoffs = {
        company_name: monitor.get_last_success_timestamp(company_name)
        for company_name, load_type in cfg_map.items()
        if load_type == "DELTA"
    }

    records, scrape_metrics, company_metrics = scrape_sources(
        sources,
        config.config,
        config.get_worker_count(),
        min_published_dates=delta_cutoffs,
    )
    validated_df = validate_scraped_data(records, min_title_length=config["MIN_TITLE_LENGTH"])
    overall_metrics = aggregate_metrics(validated_df, scrape_metrics)

    LOGGER.info("Validation complete: %s records passed quality checks", len(validated_df))
    LOGGER.info("Metrics: %s", json.dumps(overall_metrics, indent=2, sort_keys=True))

    success_companies: list[str] = []
    failed_companies: list[str] = []

    for company_name in sorted({source["company_name"] for source in sources}):
        target_schema, target_table = get_target_schema_and_table(company_name)
        ensure_schema_and_table(storage, CATALOG, target_schema, target_table)

        load_type = cfg_map.get(company_name, "FULL")
        company_df = validated_df[validated_df["company_name"] == company_name].copy()
        company_df = company_df[[column for column in RESULT_COLUMNS if column in company_df.columns]]

        if load_type == "DELTA":
            last_success_ts = delta_cutoffs.get(company_name)
            company_df = filter_delta_records(company_df, last_success_ts)

        if company_df.empty:
            company_write_df = pd.DataFrame(
                columns=["id", "url", "title", "article_content", "published_date", "s_created_ts"]
            )
        else:
            company_write_df = company_df[
                ["id", "url", "title", "article_content", "published_date", "s_created_ts"]
            ].copy()

        company_metric_summary = build_monitoring_metrics(company_df, company_metrics.get(company_name, {}))

        try:
            inserted_count = merge_data(storage, CATALOG, target_schema, target_table, company_write_df)
            success_companies.append(company_name)
            monitor.log_completion(
                company_name=company_name,
                target_schema=target_schema,
                target_table=target_table,
                load_type=load_type,
                status="SUCCESS",
                message="Data loaded successfully",
                records_inserted=inserted_count,
                metrics=company_metric_summary,
            )
            LOGGER.info("%s -> %s records inserted into %s/%s", company_name, inserted_count, target_schema, target_table)
        except Exception as exc:
            failed_companies.append(company_name)
            monitor.log_completion(
                company_name=company_name,
                target_schema=target_schema,
                target_table=target_table,
                load_type=load_type,
                status="FAILURE",
                message=str(exc),
                records_inserted=0,
                metrics={"error_count": 1},
            )
            LOGGER.exception("Failed processing %s", company_name)

    update_successful_companies_to_delta(load_config_path, success_companies)

    if config.get("EXPORT_RESULTS", True):
        export_results(validated_df, output_dir)

    LOGGER.info("Pipeline complete. Successful=%s Failed=%s", len(success_companies), len(failed_companies))
    return 1 if failed_companies else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Life Science Watch scraping pipeline locally.")
    parser.add_argument("--sources", default=str(PROJECT_ROOT / "data" / "sources.csv"), help="CSV file containing company sources")
    parser.add_argument(
        "--load-config",
        default=str(PROJECT_ROOT / "data" / "load_config.csv"),
        help="CSV file containing company load modes",
    )
    parser.add_argument(
        "--scraping-config",
        default=str(PROJECT_ROOT / "data" / "scraping_config.json"),
        help="JSON file containing scraper settings",
    )
    parser.add_argument(
        "--db-path",
        default=str(PROJECT_ROOT / "data" / "lifescience_watch.db"),
        help="Legacy SQLite database path used only for one-time bootstrap into PostgreSQL",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "outputs"),
        help="Directory where validated CSV exports are written",
    )
    parser.add_argument("--max-workers", type=int, default=None, help="Override the worker count from the config file")
    parser.add_argument("--dry-run", action="store_true", help="Validate configuration and storage setup without scraping")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    arguments = parser.parse_args()
    configure_logging(arguments.verbose)
    raise SystemExit(run_pipeline(arguments))
