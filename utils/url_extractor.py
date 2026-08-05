"""URL extraction from listing pages."""

from __future__ import annotations

import logging
import re
from typing import List
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SKIP_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".jpg", ".jpeg", ".png", ".gif")
PAGINATION_QUERY_KEYS = {"l", "o", "cat", "page", "pagenum", "offset", "sort"}


def _normalize_url(base_url: str, href: str) -> str:
    full = urljoin(base_url, href)
    parsed = urlparse(full)
    base_path = urlparse(base_url).path.rstrip("/")
    duplicate_prefix = f"{base_path}{base_path}"
    if base_path and parsed.path.startswith(duplicate_prefix):
        full = parsed._replace(path=parsed.path.replace(base_path, "", 1)).geturl()
    return full


def _is_article_like_url(url: str, base_url: str, link_text: str) -> bool:
    parsed = urlparse(url)
    base_netloc = urlparse(base_url).netloc
    host = parsed.netloc.lower()
    base_host = base_netloc.lower()
    same_orange_network = host.endswith(".orange.fr") and base_host.endswith(".orange.fr")
    if not parsed.scheme.startswith("http") or (parsed.netloc != base_netloc and not same_orange_network):
        return False

    lowered = url.lower()
    if lowered.endswith(SKIP_EXTENSIONS):
        return False

    query = parse_qs(parsed.query)
    if query and set(query).issubset(PAGINATION_QUERY_KEYS):
        return False

    path = parsed.path.lower().rstrip("/")
    text = link_text.lower()

    if parsed.path.rstrip("/") == urlparse(base_url).path.rstrip("/"):
        return False

    if "alliance-healthcare.com" in host:
        return "/magazine/" in path or "/newsroom/press-releases/" in path
    if "sebia.com" in host:
        return "/ressources/" in path and len(link_text.strip()) > 10
    if "eurofins.com" in host:
        return bool(re.search(r"/media-centre/press-releases/\d{4}-\d{2}-\d{2}/?$", path))
    if "newsroom.viatris.com" in host:
        return bool(re.search(r"/20\d{2}-\d{2}-\d{2}-", path))
    if "delpharm.com" in host:
        return "/article/" in path
    if "ceva.com" in host:
        return "/press-release/" in path or "/wildlife-research-fund/" in path
    if "hsbc.com" in host:
        return bool(
            re.search(r"/news-and-views/views/hsbc-views/.+", path)
            or re.search(r"/news-and-views/news/media-releases/.+", path)
        )
    if host.endswith(".orange.fr"):
        return bool(re.search(r"/.+-cnt[0-9a-z]+\.html$", path))

    patterns = [
        r"/news/",
        r"/news-and-views/",
        r"/press-release",
        r"/article/",
        r"/story/",
        r"/post/",
        r"/media-centre/press-releases/\d{4}-\d{2}-\d{2}",
        r"/magazine/",
        r"/ressources/",
        r"/20\d{2}-\d{2}-\d{2}-",
    ]
    if any(re.search(pattern, path) for pattern in patterns):
        return True

    return any(token in text for token in ("press", "news", "article", "release"))


def extract_listing_links(html: str, base_url: str, max_items: int) -> List[str]:
    """Extract article links from listing page HTML."""
    urls: list[str] = []
    seen: set[str] = set()

    try:
        soup = BeautifulSoup(html, "html.parser")
        selectors = [
            "article a[href]",
            ".news a[href]",
            ".press a[href]",
            ".story a[href]",
            ".post a[href]",
            ".card a[href]",
            ".listing a[href]",
            ".resource a[href]",
            ".results a[href]",
            "a[href*='/press-release/']",
            "a[href*='/news-and-views/']",
            "a[href*='/media-centre/press-releases/20']",
            "a[href*='/magazine/']",
            "a[href*='/ressources/']",
            "a[href*='/article/']",
            "a[href*='CNT'][href$='.html']",
            "a[href*='20'][href*='-'][href*='Viatris']",
            "a[href*='20'][href*='-']",
        ]

        for selector in selectors:
            for anchor in soup.select(selector):
                href = anchor.get("href")
                if not href:
                    continue
                full = _normalize_url(base_url, href)
                text = anchor.get_text(" ", strip=True)
                if full in seen or not _is_article_like_url(full, base_url, text):
                    continue
                seen.add(full)
                urls.append(full)
                if len(urls) >= max_items:
                    return urls
    except Exception as exc:
        logger.error("Error extracting links from %s: %s", base_url, exc)

    return urls


def extract_additional_listing_pages(html: str, base_url: str, max_pages: int = 12) -> List[str]:
    """Extract pagination/archive listing pages for sites that split press releases."""
    soup = BeautifulSoup(html, "html.parser")
    parsed_base = urlparse(base_url)
    host = parsed_base.netloc.lower()
    candidates: list[str] = []
    seen: set[str] = set()

    for anchor in soup.select("a[href]"):
        href = anchor.get("href") or ""
        full = _normalize_url(base_url, href)
        parsed = urlparse(full)
        if parsed.netloc != parsed_base.netloc or full == base_url or full in seen:
            continue

        if "newsroom.viatris.com" in host:
            if parsed.path.rstrip("/") == parsed_base.path.rstrip("/") and "o" in parse_qs(parsed.query):
                seen.add(full)
                candidates.append(full)
        elif "eurofins.com" in host:
            if re.search(r"/media-centre/press-releases-\d{4}/?$", parsed.path.lower()):
                seen.add(full)
                candidates.append(full)
        elif "ceva.com" in host:
            if parsed.path.rstrip("/") == parsed_base.path.rstrip("/") and "cat" in parse_qs(parsed.query):
                seen.add(full)
                candidates.append(full)

        if len(candidates) >= max_pages:
            break

    return candidates
