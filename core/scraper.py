"""Core scraping logic for the local Python pipeline."""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

import requests

from utils.html_parser import extract_article_content, extract_article_metadata, extract_jsonld_items
from utils.http_client import get_user_agent, make_session
from utils.robots_compliance import can_fetch_url
from utils.url_extractor import extract_additional_listing_pages, extract_listing_links

logger = logging.getLogger(__name__)

RESULT_COLUMNS = [
    "company_name",
    "id",
    "source_url",
    "url",
    "title",
    "article_content",
    "published_date",
    "s_created_ts",
    "response_time_ms",
]


def _blank_metrics() -> dict[str, float | int]:
    return {
        "urls_attempted": 0,
        "urls_fetched": 0,
        "parse_success_count": 0,
        "error_count": 0,
        "response_time_total_ms": 0.0,
        "response_time_count": 0,
        "avg_response_time_ms": 0.0,
    }


def _finalize_metrics(metrics: dict[str, float | int]) -> dict[str, float | int]:
    metrics = dict(metrics)
    count = int(metrics.get("response_time_count", 0))
    total = float(metrics.get("response_time_total_ms", 0.0))
    metrics["avg_response_time_ms"] = (total / count) if count else 0.0
    return metrics


def _record_timing(metrics: dict[str, float | int], elapsed_ms: float) -> None:
    metrics["response_time_total_ms"] += elapsed_ms
    metrics["response_time_count"] += 1


def _as_utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_later_than_cutoff(value: Any, cutoff: datetime | None) -> bool:
    if cutoff is None:
        return True
    parsed = _as_utc_datetime(value)
    if parsed is None:
        return True
    return parsed > cutoff


def scrape_source(
    company_name: str,
    listing_url: str,
    config: dict[str, Any],
    min_published_date: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, float | int]]:
    """Scrape one company listing page and return article records plus metrics."""
    max_items = int(config["MAX_ITEMS_PER_SOURCE"])
    listing_sleep = float(config["LISTING_SLEEP_SEC"])
    article_sleep = float(config["ARTICLE_SLEEP_SEC"])
    request_timeout = int(config["REQUEST_TIMEOUT_SEC"])

    session = make_session()
    user_agent = get_user_agent(session)
    metrics = _blank_metrics()
    records: list[dict[str, Any]] = []

    if not can_fetch_url(listing_url, user_agent):
        logger.warning("Robots.txt disallows %s", listing_url)
        metrics["error_count"] += 1
        return records, _finalize_metrics(metrics)

    time.sleep(listing_sleep)

    try:
        start_time = time.perf_counter()
        response = session.get(listing_url, timeout=request_timeout)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metrics["urls_attempted"] += 1
        _record_timing(metrics, elapsed_ms)
    except requests.RequestException as exc:
        logger.error("Request failed for listing page %s: %s", listing_url, exc)
        metrics["error_count"] += 1
        return records, _finalize_metrics(metrics)

    content_type = response.headers.get("Content-Type", "")
    if not (response.ok and "text/html" in content_type.lower()):
        logger.warning("Invalid listing response for %s", listing_url)
        metrics["error_count"] += 1
        return records, _finalize_metrics(metrics)

    metrics["urls_fetched"] += 1
    listing_pages: list[tuple[str, str]] = [(response.url, response.text)]
    for page_url in extract_additional_listing_pages(response.text, response.url):
        try:
            start_time = time.perf_counter()
            page_response = session.get(page_url, timeout=request_timeout)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            metrics["urls_attempted"] += 1
            _record_timing(metrics, elapsed_ms)
        except requests.RequestException as exc:
            logger.warning("Request failed for paginated listing page %s: %s", page_url, exc)
            metrics["error_count"] += 1
            continue

        page_content_type = page_response.headers.get("Content-Type", "")
        if page_response.ok and "text/html" in page_content_type.lower():
            metrics["urls_fetched"] += 1
            listing_pages.append((page_response.url, page_response.text))
        else:
            metrics["error_count"] += 1

    candidate_urls: list[str] = []
    jsonld_by_url: dict[str, dict[str, Any]] = {}

    for page_url, listing_html in listing_pages:
        jsonld_items = extract_jsonld_items(listing_html, page_url)
        candidate_urls.extend([item["url"] for item in jsonld_items if isinstance(item.get("url"), str)])
        for item in jsonld_items:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                jsonld_by_url[item["url"]] = item
        if len(candidate_urls) < max_items:
            candidate_urls.extend(extract_listing_links(listing_html, page_url, max_items))

    candidate_urls = list(dict.fromkeys(candidate_urls))
    cutoff = _as_utc_datetime(min_published_date)

    considered_articles = 0
    for article_url in candidate_urls:
        jsonld_item = jsonld_by_url.get(article_url)
        if jsonld_item and not _is_later_than_cutoff(jsonld_item.get("published_date"), cutoff):
            continue
        if considered_articles >= max_items:
            break
        considered_articles += 1

        time.sleep(article_sleep)
        title = None
        published_ts = None
        article_content = None

        try:
            start_time = time.perf_counter()
            article_response = session.get(article_url, timeout=request_timeout)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            metrics["urls_attempted"] += 1
            _record_timing(metrics, elapsed_ms)
        except requests.RequestException as exc:
            logger.warning("Request failed for article %s: %s", article_url, exc)
            metrics["error_count"] += 1
            continue

        article_content_type = article_response.headers.get("Content-Type", "")
        if article_response.ok and "text/html" in article_content_type.lower():
            metrics["urls_fetched"] += 1
            article_html = article_response.text

            if jsonld_item:
                title = jsonld_item.get("title") or title
                published_ts = jsonld_item.get("published_date") or published_ts

            if not title or not published_ts:
                parsed_title, parsed_published_ts = extract_article_metadata(article_html)
                title = title or parsed_title
                published_ts = published_ts or parsed_published_ts

            article_content = extract_article_content(article_html)
            if title:
                metrics["parse_success_count"] += 1
        else:
            metrics["error_count"] += 1
            continue

        if not _is_later_than_cutoff(published_ts, cutoff):
            continue

        records.append(
            {
                "company_name": company_name,
                "id": str(uuid.uuid4()),
                "source_url": listing_url,
                "url": article_url,
                "title": title,
                "article_content": article_content,
                "published_date": published_ts.isoformat() if hasattr(published_ts, "isoformat") else None,
                "s_created_ts": datetime.now(UTC).isoformat(),
                "response_time_ms": round(elapsed_ms, 2),
            }
        )

    return records, _finalize_metrics(metrics)


def scrape_sources(
    sources: list[dict[str, str]],
    config: dict[str, Any],
    max_workers: int,
    min_published_dates: dict[str, datetime] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, float | int], dict[str, dict[str, float | int]]]:
    """Scrape all source URLs in parallel."""
    if not sources:
        return [], _finalize_metrics(_blank_metrics()), {}

    overall_metrics = _blank_metrics()
    company_metrics: dict[str, dict[str, float | int]] = {}
    records: list[dict[str, Any]] = []

    worker_count = max(1, min(int(max_workers), len(sources)))
    logger.info("Starting scrape with %s workers across %s sources", worker_count, len(sources))

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                scrape_source,
                source["company_name"],
                source["url"],
                config,
                (min_published_dates or {}).get(source["company_name"]),
            ): source
            for source in sources
        }
        for future in as_completed(futures):
            source = futures[future]
            company_name = source["company_name"]
            source_records, source_metrics = future.result()
            records.extend(source_records)

            company_metric_bucket = company_metrics.setdefault(company_name, _blank_metrics())
            for key in ["urls_attempted", "urls_fetched", "parse_success_count", "error_count"]:
                company_metric_bucket[key] += int(source_metrics.get(key, 0))
                overall_metrics[key] += int(source_metrics.get(key, 0))

            for key in ["response_time_total_ms", "response_time_count"]:
                company_metric_bucket[key] += float(source_metrics.get(key, 0))
                overall_metrics[key] += float(source_metrics.get(key, 0))

    finalized_company_metrics = {
        company_name: _finalize_metrics(metric_bucket)
        for company_name, metric_bucket in company_metrics.items()
    }
    return records, _finalize_metrics(overall_metrics), finalized_company_metrics
