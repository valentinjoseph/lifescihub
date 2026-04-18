"""Robots.txt compliance checker."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


def _compile_rule(pattern: str) -> re.Pattern[str]:
    escaped = re.escape(pattern).replace(r"\*", ".*")
    if escaped.endswith(r"\$"):
        escaped = escaped[:-2] + "$"
    else:
        escaped = f"{escaped}.*"
    return re.compile(f"^{escaped}")


def _parse_robots(text: str) -> list[dict[str, list[str]]]:
    groups: list[dict[str, list[str]]] = []
    current_agents: list[str] = []
    current_rules: list[tuple[str, str]] = []

    def flush_group() -> None:
        nonlocal current_agents, current_rules
        if current_agents:
            groups.append(
                {
                    "agents": current_agents[:],
                    "rules": [f"{directive}:{value}" for directive, value in current_rules],
                }
            )
        current_agents = []
        current_rules = []

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = [part.strip() for part in line.split(":", 1)]
        field = field.lower()
        if field == "user-agent":
            if current_rules:
                flush_group()
            current_agents.append(value.lower())
        elif field in {"allow", "disallow"} and current_agents:
            current_rules.append((field, value))

    flush_group()
    return groups


def _match_agents(groups: list[dict[str, list[str]]], user_agent: str) -> list[str]:
    ua = user_agent.lower()
    matched_rules: list[str] = []
    wildcard_rules: list[str] = []
    for group in groups:
        agents = group["agents"]
        rules = group["rules"]
        if any(agent != "*" and agent in ua for agent in agents):
            matched_rules.extend(rules)
        elif "*" in agents:
            wildcard_rules.extend(rules)
    return matched_rules or wildcard_rules


def can_fetch_url(url: str, user_agent: str) -> bool:
    """Check if URL can be fetched according to robots.txt.

    This implementation is intentionally tolerant of missing/blocked robots.txt
    responses because a number of target sites either return 403 for robots.txt
    or publish files that the stdlib parser misinterprets.
    """

    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        response = requests.get(robots_url, timeout=15)
        if response.status_code >= 400:
            logger.info("robots.txt unavailable for %s (status=%s); allowing fetch", url, response.status_code)
            return True

        rules = _match_agents(_parse_robots(response.text), user_agent)
        if not rules:
            return True

        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        best_match_length = -1
        allow_fetch = True

        for rule in rules:
            directive, pattern = rule.split(":", 1)
            directive = directive.strip()
            pattern = pattern.strip()
            if not pattern:
                if directive == "allow" and best_match_length < 0:
                    allow_fetch = True
                continue
            if _compile_rule(pattern).match(path):
                match_length = len(pattern)
                if match_length >= best_match_length:
                    best_match_length = match_length
                    allow_fetch = directive == "allow"

        return allow_fetch
    except Exception as exc:
        logger.warning("Could not check robots.txt for %s: %s", url, exc)
        return True
