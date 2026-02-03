"""
Simple scraper for eventfinda.com.au search results for Sydney.
Very lightweight; adapt selectors if site changes.
"""
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .session import create_session, allowed_by_robots

BASE = "https://www.eventfinda.com.au"


def scrape_eventfinda(city="Sydney"):
    results = []
    try:
        url = f"{BASE}/search?q={city}"
        if not allowed_by_robots(url):
            print(f"Skipping eventfinda due to robots.txt: {url}")
            return results
        s = create_session()
        resp = s.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".ef-event, .searchResult, .card")
        for c in cards[:80]:
            a = c.find("a", href=True)
            if not a:
                continue
            link = urljoin(BASE, a["href"])
            title_el = c.select_one(".ef-title, .title")
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            time_el = c.select_one(".ef-date, .date")
            venue_el = c.select_one(".ef-venue, .venue")
            img = c.find("img")
            image_url = img.get("src") if img and img.has_attr("src") else None
            desc = c.select_one(".ef-desc, .excerpt")
            results.append({
                "title": title,
                "start_time": time_el.get_text(strip=True) if time_el else None,
                "venue": venue_el.get_text(strip=True) if venue_el else None,
                "address": None,
                "city": city,
                "description": desc.get_text(strip=True) if desc else None,
                "category": None,
                "image_url": image_url,
                "source": "Eventfinda",
                "original_url": link,
            })
    except Exception as e:
        print(f"eventfinda scraper error: {e}")
    return results
