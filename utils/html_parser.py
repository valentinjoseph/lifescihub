"""HTML parsing utilities."""

import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

ISO_DATETIME_RE = re.compile(
    r"\b(20\d{2}-\d{2}-\d{2})(?:[T\s]\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?)?\b",
    re.IGNORECASE,
)

def extract_article_content(html: str, max_length: int = 50000) -> Optional[str]:
    """Extract main article content from HTML.
    
    Args:
        html: Raw HTML content
        max_length: Maximum length of extracted content (default 50000 chars)
        
    Returns:
        Cleaned article text or None if extraction fails
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script, style, nav, header, footer elements
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        
        # Try to find main content area (common selectors)
        content = None
        for selector in [
            ('article', {}),
            ('div', {'class': re.compile(r'article|content|post|entry', re.I)}),
            ('div', {'id': re.compile(r'article|content|post|entry', re.I)}),
            ('main', {}),
        ]:
            content_tag = soup.find(*selector)
            if content_tag:
                content = content_tag.get_text(separator=' ', strip=True)
                break
        
        # Fallback: get all paragraph text
        if not content or len(content) < 100:
            paragraphs = soup.find_all('p')
            content = ' '.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        
        # Clean up whitespace
        if content:
            content = re.sub(r'\s+', ' ', content).strip()
            # Truncate if too long
            if len(content) > max_length:
                content = content[:max_length]
            return content if len(content) > 50 else None
        
        return None
    except Exception as e:
        logger.error(f"Error extracting article content: {e}")
        return None

def extract_article_metadata(html: str) -> Tuple[Optional[str], Optional[datetime]]:
    """Extract title and published date from article HTML."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.string.strip() if soup.title and soup.title.string else None)
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = title or og.get("content").strip()
        
        published_ts = None
        for selector in [
            ('meta', {'property': 'article:published_time'}),
            ('meta', {'name': 'pubdate'}),
            ('meta', {'itemprop': 'datePublished'}),
            ('time', {}),
        ]:
            tag = soup.find(*selector)
            if tag:
                content = tag.get("content") or tag.get_text(strip=True)
                if content:
                    m = ISO_DATETIME_RE.search(content)
                    if m:
                        dt_str = m.group(0)
                        try:
                            if "T" in dt_str or ":" in dt_str:
                                published_ts = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                            else:
                                published_ts = datetime.fromisoformat(dt_str)
                        except ValueError:
                            pass
                        if published_ts:
                            break
        
        if not published_ts:
            m = ISO_DATETIME_RE.search(html[:200_000])
            if m:
                try:
                    published_ts = datetime.fromisoformat(m.group(0).replace("Z", "+00:00"))
                except ValueError:
                    pass
        
        return title, published_ts
    except Exception as e:
        logger.error(f"Error extracting metadata: {e}")
        return None, None

def extract_jsonld_items(html: str, base_url: str) -> List[Dict]:
    """Extract articles from JSON-LD structured data."""
    items = []
    base_netloc = urlparse(base_url).netloc
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            text = script.string or script.get_text() or ""
            if not text.strip():
                continue
            
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            
            def handle_obj(obj):
                if not isinstance(obj, dict):
                    return
                
                typ = obj.get("@type")
                if isinstance(typ, list):
                    typ = next((t for t in typ if isinstance(t, str)), None)
                
                if isinstance(typ, str) and typ.lower() in {"newsarticle", "article", "blogposting", "report"}:
                    url = obj.get("url")
                    if not url and isinstance(obj.get("mainEntityOfPage"), dict):
                        url = obj["mainEntityOfPage"].get("@id") or obj["mainEntityOfPage"].get("url")
                    
                    title = obj.get("headline") or obj.get("name")
                    date_str = obj.get("datePublished") or obj.get("dateCreated")
                    published_ts = None
                    if isinstance(date_str, str):
                        try:
                            published_ts = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        except ValueError:
                            pass
                    
                    if isinstance(url, str):
                        full = urljoin(base_url, url)
                        if urlparse(full).netloc == base_netloc:
                            items.append({"url": full, "title": title, "published_date": published_ts})
                
                if "@graph" in obj and isinstance(obj["@graph"], list):
                    for node in obj["@graph"]:
                        handle_obj(node)
            
            if isinstance(data, list):
                for obj in data:
                    handle_obj(obj)
            else:
                handle_obj(data)
    except Exception as e:
        logger.error(f"Error extracting JSON-LD: {e}")
    
    return items
