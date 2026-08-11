"""Scrape job description text from a public URL."""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Tags whose content we always discard
_SKIP_TAGS = {"script", "style", "noscript", "header", "footer", "nav", "aside"}

# CSS class/id fragments that typically indicate boilerplate (nav, cookie banners, etc.)
_SKIP_PATTERNS = re.compile(
    r"(nav|menu|cookie|banner|footer|header|sidebar|ad-|advertisement|social|share|modal)",
    re.IGNORECASE,
)


def scrape_job_url(url: str, timeout: int = 15) -> str:
    """
    Fetch a job posting page and return cleaned plain text.
    Raises ValueError if the page can't be fetched or yields no text.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise ValueError(f"HTTP error fetching URL: {e}")
    except requests.exceptions.ConnectionError:
        raise ValueError("Could not connect to the URL. Check the link and your internet connection.")
    except requests.exceptions.Timeout:
        raise ValueError("Request timed out. The site may be slow or blocking scrapers.")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove boilerplate tags
    for tag in soup.find_all(_SKIP_TAGS):
        tag.decompose()

    # Remove elements whose class or id looks like navigation/ads
    # Collect first, decompose after — avoids corrupting the tree mid-iteration
    to_remove = []
    for tag in soup.find_all(True):
        try:
            classes = " ".join(tag.get("class") or [])
            tag_id = tag.get("id") or ""
        except AttributeError:
            continue
        if _SKIP_PATTERNS.search(classes) or _SKIP_PATTERNS.search(tag_id):
            to_remove.append(tag)
    for tag in to_remove:
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Collapse excessive blank lines
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = "\n".join(ln for ln in lines if ln)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    if len(cleaned.split()) < 30:
        raise ValueError(
            "Could not extract meaningful text from this page. "
            "The site may require login, use JavaScript rendering, or block scrapers."
        )

    return cleaned
