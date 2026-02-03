"""
Lightweight scraper for https://www.sydney.com/events
This attempts to parse the events listing page and extract title, date, venue and link.
Selectors are tolerant and may need tuning if the target site changes.
"""
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .session import create_session, allowed_by_robots

BASE = "https://www.sydney.com"


def scrape_sydney_com(city="Sydney"):
    results = []
    try:
        url = f"{BASE}/events"
        if not allowed_by_robots(url):
            print(f"Skipping sydney.com due to robots.txt: {url}")
            return results
        s = create_session()
        resp = s.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # common event link selectors
        anchors = soup.select("a[href*='/events/'], a[href*='/event/'], a[class*='event']")
        seen = set()
        for a in anchors[:120]:
            href = a.get('href')
            if not href:
                continue
            link = urljoin(BASE, href)
            if link in seen:
                continue
            seen.add(link)

            # try to extract a title
            title = (a.get_text(strip=True) or a.get('title') or '').strip()
            # sometimes title is in child elements
            if not title:
                title_el = a.select_one('.title, .headline, h3, h2')
                title = title_el.get_text(strip=True) if title_el else ''

            # find parent card for date/venue
            parent = a
            for _ in range(3):
                if parent is None:
                    break
                if parent.select_one('.date, .event-date, time, .meta'):
                    break
                parent = parent.parent

            time_el = parent.select_one('.date, .event-date, time, .meta') if parent else None
            venue_el = parent.select_one('.venue, .location, .place') if parent else None
            desc = parent.select_one('.desc, .excerpt, p') if parent else None
            img = parent.select_one('img') if parent else None
            image_url = None
            if img:
                image_url = img.get('data-src') or img.get('src')

            results.append({
                'title': title or None,
                'start_time': time_el.get_text(strip=True) if time_el else None,
                'venue': venue_el.get_text(strip=True) if venue_el else None,
                'address': None,
                'city': city,
                'description': desc.get_text(strip=True) if desc else None,
                'category': None,
                'image_url': image_url,
                'source': 'Sydney.com',
                'original_url': link,
            })
    except Exception as e:
        print(f"sydney.com scraper error: {e}")
    return results
