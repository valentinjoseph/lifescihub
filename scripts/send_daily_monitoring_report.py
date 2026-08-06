#!/usr/bin/env python3
"""Send a daily pipeline monitoring report from tech.tech_load_monitoring."""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from collections import defaultdict
from datetime import UTC, datetime, time
from email.message import EmailMessage
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import engine  # noqa: E402


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_recipients(value: str) -> list[str]:
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def report_window(timezone_name: str, day: str | None = None) -> tuple[datetime, datetime, str]:
    timezone = ZoneInfo(timezone_name)
    report_date = datetime.now(timezone).date() if not day else datetime.fromisoformat(day).date()
    start_local = datetime.combine(report_date, time.min, tzinfo=timezone)
    end_local = datetime.combine(report_date, time.max, tzinfo=timezone)
    return start_local.astimezone(UTC), end_local.astimezone(UTC), report_date.isoformat()


def fetch_monitoring_rows(start_utc: datetime, end_utc: datetime) -> list[dict]:
    query = text(
        """
        SELECT
            run_id,
            run_name,
            company_name,
            load_type,
            run_status,
            run_message,
            COALESCE(records_inserted, 0) AS records_inserted,
            COALESCE(urls_attempted, 0) AS urls_attempted,
            COALESCE(urls_fetched, 0) AS urls_fetched,
            COALESCE(parse_success_count, 0) AS parse_success_count,
            COALESCE(error_count, 0) AS error_count,
            run_start_ts,
            run_end_ts
        FROM tech.tech_load_monitoring
        WHERE run_end_ts >= :start_utc
          AND run_end_ts <= :end_utc
        ORDER BY run_end_ts DESC, company_name
        """
    )
    with engine.begin() as connection:
        return [dict(row) for row in connection.execute(query, {"start_utc": start_utc, "end_utc": end_utc}).mappings()]


def format_company_table(rows: list[dict]) -> list[str]:
    columns = [
        ("company name", "company_name"),
        ("status", "run_status"),
        ("load_type", "load_type"),
        ("fetched", "urls_fetched"),
        ("parsed", "parse_success_count"),
        ("attempted", "urls_attempted"),
        ("inserted", "records_inserted"),
        ("errors", "error_count"),
    ]
    table_rows = [
        [str(row.get(key, "")) for _, key in columns]
        for row in sorted(rows, key=lambda item: str(item["company_name"]))
    ]
    widths = [
        max(len(header), *(len(row[index]) for row in table_rows))
        for index, (header, _) in enumerate(columns)
    ]

    def format_row(values: list[str]) -> str:
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(values))

    header = format_row([header for header, _ in columns])
    separator = "-+-".join("-" * width for width in widths)
    return [header, separator, *[format_row(row) for row in table_rows]]


def monitoring_summary(rows: list[dict]) -> dict[str, int]:
    return {
        "total_inserted": sum(int(row["records_inserted"]) for row in rows),
        "total_errors": sum(int(row["error_count"]) for row in rows),
        "successful_rows": sum(1 for row in rows if row["run_status"] == "SUCCESS"),
        "failed_rows": sum(1 for row in rows if row["run_status"] != "SUCCESS"),
        "run_count": len({str(row["run_id"]) for row in rows if row.get("run_id")}),
    }


def group_rows_by_run(rows: list[dict]) -> dict[str, list[dict]]:
    by_run: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_run[str(row["run_id"])].append(row)
    return by_run


def format_monitoring_report(
    *,
    rows: list[dict],
    report_date: str,
    pipeline_status: str,
    exit_code: int,
    started_at: str,
    ended_at: str,
) -> str:
    summary = monitoring_summary(rows)

    lines = [
        f"Daily monitoring report for {report_date}",
        "",
        f"Pipeline status: {pipeline_status}",
        f"Pipeline exit code: {exit_code}",
        f"Started at UTC: {started_at}",
        f"Ended at UTC: {ended_at}",
        f"Monitoring rows found: {len(rows)}",
        f"Distinct scraper run IDs: {summary['run_count']}",
        f"Successful company rows: {summary['successful_rows']}",
        f"Failed company rows: {summary['failed_rows']}",
        f"Total records inserted: {summary['total_inserted']}",
        f"Total source errors reported: {summary['total_errors']}",
        "",
    ]

    if not rows:
        lines.extend(
            [
                "No rows were found in tech.tech_load_monitoring for this report day.",
                "This usually means the scraper did not reach the monitoring write step.",
            ]
        )
        return "\n".join(lines)

    for run_id, run_rows in group_rows_by_run(rows).items():
        run_inserted = sum(int(row["records_inserted"]) for row in run_rows)
        run_status = "SUCCESS" if all(row["run_status"] == "SUCCESS" for row in run_rows) else "FAILED"
        lines.extend(
            [
                f"Run ID: {run_id}",
                f"Run status from company rows: {run_status}",
                f"Companies processed: {len(run_rows)}",
                f"Records inserted: {run_inserted}",
                "",
                "Company details:",
            ]
        )
        lines.extend(format_company_table(run_rows))
        lines.append("")

    return "\n".join(lines).rstrip()


def format_monitoring_report_html(
    *,
    rows: list[dict],
    report_date: str,
    pipeline_status: str,
    exit_code: int,
    started_at: str,
    ended_at: str,
) -> str:
    summary = monitoring_summary(rows)
    status_color = {
        "SUCCESS": "#166534",
        "FAILED": "#991b1b",
        "SKIPPED": "#92400e",
    }.get(pipeline_status, "#111827")

    html = [
        "<!doctype html>",
        "<html>",
        "<body style=\"font-family: Arial, sans-serif; color: #111827;\">",
        f"<h2 style=\"margin-bottom: 8px;\">Daily monitoring report for {escape(report_date)}</h2>",
        "<table style=\"border-collapse: collapse; margin-bottom: 20px;\">",
    ]
    summary_rows = [
        ("Pipeline status", pipeline_status),
        ("Pipeline exit code", str(exit_code)),
        ("Started at UTC", started_at),
        ("Ended at UTC", ended_at),
        ("Monitoring rows found", str(len(rows))),
        ("Distinct scraper run IDs", str(summary["run_count"])),
        ("Successful company rows", str(summary["successful_rows"])),
        ("Failed company rows", str(summary["failed_rows"])),
        ("Total records inserted", str(summary["total_inserted"])),
        ("Total source errors reported", str(summary["total_errors"])),
    ]
    for label, value in summary_rows:
        value_style = f"color: {status_color}; font-weight: 700;" if label == "Pipeline status" else ""
        html.append(
            "<tr>"
            f"<th style=\"text-align: left; padding: 5px 12px 5px 0;\">{escape(label)}</th>"
            f"<td style=\"padding: 5px 0; {value_style}\">{escape(value)}</td>"
            "</tr>"
        )
    html.append("</table>")

    if not rows:
        html.extend(
            [
                "<p>No rows were found in <code>tech.tech_load_monitoring</code> for this report day.</p>",
                "<p>This usually means the scraper did not reach the monitoring write step.</p>",
                "</body></html>",
            ]
        )
        return "\n".join(html)

    columns = [
        ("company name", "company_name"),
        ("status", "run_status"),
        ("load_type", "load_type"),
        ("fetched", "urls_fetched"),
        ("parsed", "parse_success_count"),
        ("attempted", "urls_attempted"),
        ("inserted", "records_inserted"),
        ("errors", "error_count"),
    ]

    for run_id, run_rows in group_rows_by_run(rows).items():
        run_inserted = sum(int(row["records_inserted"]) for row in run_rows)
        run_status = "SUCCESS" if all(row["run_status"] == "SUCCESS" for row in run_rows) else "FAILED"
        html.extend(
            [
                f"<h3 style=\"margin: 20px 0 8px;\">Run ID: {escape(run_id)}</h3>",
                "<p style=\"margin: 0 0 10px;\">"
                f"Run status from company rows: <strong>{escape(run_status)}</strong><br>"
                f"Companies processed: {len(run_rows)}<br>"
                f"Records inserted: {run_inserted}"
                "</p>",
                "<table style=\"border-collapse: collapse; width: 100%; font-size: 13px;\">",
                "<thead><tr>",
            ]
        )
        for header, _ in columns:
            html.append(
                f"<th style=\"border: 1px solid #d1d5db; background: #f3f4f6; padding: 7px; text-align: left;\">{escape(header)}</th>"
            )
        html.append("</tr></thead><tbody>")
        for row in sorted(run_rows, key=lambda item: str(item["company_name"])):
            inserted = int(row["records_inserted"])
            errors = int(row["error_count"])
            if errors:
                row_style = "background: #fee2e2; color: #7f1d1d;"
            elif inserted:
                row_style = "background: #dcfce7; color: #14532d;"
            else:
                row_style = ""
            html.append(f"<tr style=\"{row_style}\">")
            for _, key in columns:
                html.append(f"<td style=\"border: 1px solid #d1d5db; padding: 7px;\">{escape(str(row.get(key, '')))}</td>")
            html.append("</tr>")
        html.append("</tbody></table>")

    html.append("</body></html>")
    return "\n".join(html)


def build_message(subject: str, body: str, html_body: str | None = None) -> EmailMessage:
    sender = os.getenv("DAILY_REPORT_EMAIL_FROM", "")
    recipients = parse_recipients(os.getenv("DAILY_REPORT_EMAIL_TO", ""))
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    return message


def send_message(message: EmailMessage) -> None:
    host = os.getenv("DAILY_REPORT_SMTP_HOST", "")
    port = int(os.getenv("DAILY_REPORT_SMTP_PORT", "587"))
    username = os.getenv("DAILY_REPORT_SMTP_USERNAME", "")
    password = os.getenv("DAILY_REPORT_SMTP_PASSWORD", "")
    timeout = int(os.getenv("DAILY_REPORT_SMTP_TIMEOUT_SECONDS", "30"))
    use_ssl = env_flag("DAILY_REPORT_SMTP_SSL", False)
    use_starttls = env_flag("DAILY_REPORT_SMTP_STARTTLS", not use_ssl)

    if use_ssl:
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=timeout)
    else:
        smtp = smtplib.SMTP(host, port, timeout=timeout)

    with smtp:
        if use_starttls:
            smtp.starttls()
        if username or password:
            smtp.login(username, password)
        smtp.send_message(message)


def main_with_args(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send daily monitoring report email.")
    parser.add_argument("--pipeline-status", required=True, choices=["SUCCESS", "FAILED", "SKIPPED"])
    parser.add_argument("--exit-code", required=True, type=int)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--ended-at", required=True)
    parser.add_argument("--day", help="Report day in YYYY-MM-DD format. Defaults to today in report timezone.")
    args = parser.parse_args(argv)

    if not env_flag("DAILY_REPORT_EMAIL_ENABLED", False):
        print("daily monitoring email disabled")
        return 0

    missing = [
        name
        for name in ("DAILY_REPORT_EMAIL_FROM", "DAILY_REPORT_EMAIL_TO", "DAILY_REPORT_SMTP_HOST")
        if not os.getenv(name)
    ]
    if missing:
        print(f"daily monitoring email skipped; missing env vars: {', '.join(missing)}")
        return 0

    timezone_name = os.getenv("DAILY_REPORT_TIMEZONE", "Europe/Paris")
    start_utc, end_utc, report_date = report_window(timezone_name, args.day)
    rows = fetch_monitoring_rows(start_utc, end_utc)
    body = format_monitoring_report(
        rows=rows,
        report_date=report_date,
        pipeline_status=args.pipeline_status,
        exit_code=args.exit_code,
        started_at=args.started_at,
        ended_at=args.ended_at,
    )
    html_body = format_monitoring_report_html(
        rows=rows,
        report_date=report_date,
        pipeline_status=args.pipeline_status,
        exit_code=args.exit_code,
        started_at=args.started_at,
        ended_at=args.ended_at,
    )
    project = os.getenv("DAILY_REPORT_PROJECT", "GTM Advisor")
    subject_prefix = os.getenv("DAILY_REPORT_SUBJECT_PREFIX", f"[{project}]")
    subject = f"{subject_prefix} daily monitoring {report_date}: {args.pipeline_status}"
    message = build_message(subject, body, html_body)

    try:
        send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        print(f"daily monitoring email authentication failed: {exc.smtp_code} {exc.smtp_error!r}", file=sys.stderr)
        return 1
    except smtplib.SMTPException as exc:
        print(f"daily monitoring email SMTP error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"daily monitoring email connection error: {exc}", file=sys.stderr)
        return 1

    print("daily monitoring email sent")
    return 0


def main() -> int:
    return main_with_args()


if __name__ == "__main__":
    raise SystemExit(main())
