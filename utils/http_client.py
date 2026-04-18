"""HTTP client utilities with retry logic."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

logger = logging.getLogger(__name__)

def make_session() -> requests.Session:
    """Create a configured requests session with retry logic."""
    session = requests.Session()
    retries = Retry(
        total=3, connect=3, read=3, backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"]
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=50, pool_maxsize=50)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; LSBusinessWatchBot/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en,fr;q=0.9",
        "Cache-Control": "no-cache",
    })
    return session

def get_user_agent(session: requests.Session) -> str:
    """Extract User-Agent from session."""
    return session.headers.get("User-Agent", "LSBusinessWatchBot")
