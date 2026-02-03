"""Shared requests session with retries and robots.txt helper."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin, urlparse
import urllib.robotparser as robotparser

DEFAULT_UA = "EventScraperBot/1.0 (+https://example.com)"


def create_session(user_agent: str = DEFAULT_UA, retries: int = 3, backoff: float = 0.3):
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent})
    retry = Retry(total=retries, backoff_factor=backoff, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST"])
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def allowed_by_robots(url: str, user_agent: str = DEFAULT_UA) -> bool:
    parsed = urlparse(url)
    robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
    rp = robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        # if robots cannot be fetched, assume allowed but callers should be cautious
        return True
