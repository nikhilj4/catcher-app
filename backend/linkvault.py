"""
LinkVault - Web Scraping and Metadata Extraction
"""

from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

PLATFORM_MAP = {
    "youtube.com": "youtube", "youtu.be": "youtube",
    "twitter.com": "twitter", "x.com": "twitter",
    "reddit.com": "reddit",
    "github.com": "github",
    "medium.com": "article",
    "instagram.com": "instagram",
    "tiktok.com": "tiktok",
    "vimeo.com": "vimeo",
    "pinterest.com": "pinterest",
    "notion.so": "notion",
    "figma.com": "figma",
}

def detect_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().replace("www.", "")
    for domain, platform in PLATFORM_MAP.items():
        if host.endswith(domain):
            return platform
    return "generic"

def extract(url: str, platform: str) -> dict:
    """Fast extraction for Open Graph tags"""
    try:
        response = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            return _fallback_extraction(url)
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract OpenGraph metadata
        title = soup.find("meta", property="og:title")
        description = soup.find("meta", property="og:description")
        thumbnail = soup.find("meta", property="og:image")
        
        # Fallback to standard tags
        if not title:
            title = soup.title
            
        return {
            "title": title.get("content", "") if title and hasattr(title, "get") else (title.string if title else None),
            "description": description.get("content", "") if description else None,
            "author": None,
            "published": None,
            "thumbnail": thumbnail.get("content", "") if thumbnail else None
        }
    except Exception as e:
        logger.warning(f"Metadata extraction failed: {e}")
        return _fallback_extraction(url)

def _extract_full_content(url: str) -> dict:
    """Deep extraction for full content, headings, and paragraphs"""
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            return {"full_text": "", "headings": [], "paragraphs": [], "price": None, "rating": None}
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
            
        text = soup.get_text(separator=' ')
        # compact whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        headings = [h.text.strip() for h in soup.find_all(['h1', 'h2', 'h3'])]
        paragraphs = [p.text.strip() for p in soup.find_all('p')]
        
        return {
            "full_text": text[:15000], # Limit full text size
            "headings": headings,
            "paragraphs": paragraphs,
            "price": None,
            "rating": None
        }
    except Exception as e:
        logger.error(f"Full content extraction failed: {e}")
        return {"full_text": "", "headings": [], "paragraphs": [], "price": None, "rating": None}

def _fallback_extraction(url: str) -> dict:
    path = urlparse(url).path.strip("/").replace("-", " ").replace("_", " ")
    host = (urlparse(url).hostname or url).replace("www.", "")
    title = path.split("/")[-1].title() if path else host
    return {
        "title": title or host,
        "description": f"Saved from {host}",
        "author": host,
        "published": None,
        "thumbnail": None
    }
