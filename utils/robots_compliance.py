"""Robots.txt compliance checker."""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import logging

logger = logging.getLogger(__name__)

def can_fetch_url(url: str, user_agent: str) -> bool:
    """Check if URL can be fetched according to robots.txt."""
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception as e:
        logger.warning(f"Could not check robots.txt for {url}: {e}")
        return True
