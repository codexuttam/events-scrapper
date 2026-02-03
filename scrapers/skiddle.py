"""
Simple scraper for Skiddle Sydney listings (https://www.skiddle.com/whats-on/Sydney/).
"""
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .session import create_session, allowed_by_robots

BASE = "https://www.skiddle.com"


def scrape_skiddle(city="Sydney"):
    results = []
    try:
        url = f"{BASE}/whats-on/{city}/"
        if not allowed_by_robots(url):
            print(f"Skipping skiddle due to robots.txt: {url}")
            return results
        s = create_session()
        resp = s.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".card, .searchResultsItem")
        for c in cards[:80]:
            a = c.find("a", href=True)
            if not a:
                continue
            link = urljoin(BASE, a["href"]) if a["href"].startswith("/") else a["href"]
            title_el = c.select_one(".title, .eventTitle")
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            time_el = c.select_one(".date, .dateTime")
            venue_el = c.select_one(".venue, .venueName")
            img = c.find("img")
            image_url = img.get("data-src") or img.get("src") if img else None
            desc = c.select_one(".description, .excerpt")
            results.append({
                "title": title,
                "start_time": time_el.get_text(strip=True) if time_el else None,
                "venue": venue_el.get_text(strip=True) if venue_el else None,
                "address": None,
                "city": city,
                "description": desc.get_text(strip=True) if desc else None,
                "category": None,
                "image_url": image_url,
                "source": "Skiddle",
                "original_url": link,
            })
    except Exception as e:
        print(f"skiddle scraper error: {e}")
    return results
