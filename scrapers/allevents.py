"""
Simple scraper for allevents.in search results for Sydney.
This is a lightweight parser - may need tuning depending on site changes.
"""
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .session import create_session, allowed_by_robots

BASE = "https://allevents.in"


def scrape_allevents(city="Sydney"):
    results = []
    try:
        url = f"{BASE}/{city}"
        if not allowed_by_robots(url):
            print(f"Skipping allevents due to robots.txt: {url}")
            return results
        s = create_session()
        resp = s.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".event-card, .event-item, .col-event")
        for c in cards[:80]:
            a = c.find("a", href=True)
            if not a:
                continue
            link = urljoin(BASE, a["href"])
            title = a.get_text(strip=True)
            img = c.find("img")
            image_url = None
            if img:
                image_url = img.get("data-src") or img.get("src")
            time_el = c.select_one(".date, .time, .event-date")
            venue_el = c.select_one(".venue, .place")
            desc = c.select_one(".desc, .event-desc")
            results.append({
                "title": title,
                "start_time": time_el.get_text(strip=True) if time_el else None,
                "venue": venue_el.get_text(strip=True) if venue_el else None,
                "address": None,
                "city": city,
                "description": desc.get_text(strip=True) if desc else None,
                "category": None,
                "image_url": image_url,
                "source": "Allevents",
                "original_url": link,
            })
    except Exception as e:
        print(f"allevents scraper error: {e}")
    return results
