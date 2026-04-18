"""URL extraction from listing pages."""

from typing import List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def extract_listing_links(html: str, base_url: str, max_items: int) -> List[str]:
    """Extract article links from listing page HTML."""
    urls = []
    seen = set()
    base_netloc = urlparse(base_url).netloc
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        selectors = [
            "article a[href]", ".news a[href]", ".press a[href]",
            ".story a[href]", ".post a[href]", ".card a[href]",
            "a[href*='press']", "a[href*='news']", "a[href*='article']",
        ]
        
        for sel in selectors:
            for a in soup.select(sel):
                href = a.get("href")
                if not href:
                    continue
                
                full = urljoin(base_url, href)
                parsed = urlparse(full)
                
                if not parsed.scheme.startswith("http") or parsed.netloc != base_netloc:
                    continue
                
                if full.rstrip("/") == base_url.rstrip("/") or full in seen:
                    continue
                
                seen.add(full)
                urls.append(full)
                
                if len(urls) >= max_items:
                    return urls
    except Exception as e:
        logger.error(f"Error extracting links: {e}")
    
    return urls
