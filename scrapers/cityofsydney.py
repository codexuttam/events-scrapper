"""
Scraper for City of Sydney 'What's On' listings (whatson.cityofsydney.nsw.gov.au)
This parser is forgiving and extracts event links, titles, dates and venues from listing pages.
"""
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .session import create_session, allowed_by_robots

BASE = "https://whatson.cityofsydney.nsw.gov.au"


def scrape_cityofsydney(city="Sydney"):
    results = []
    try:
        url = f"{BASE}/"
        if not allowed_by_robots(url):
            print(f"Skipping whatson.cityofsydney due to robots.txt: {url}")
            return results
        s = create_session()
        resp = s.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        anchors = soup.select("a[href*='/events/'], a[href*='/Event/'], .card a, .listing a")
        seen = set()
        for a in anchors[:150]:
            href = a.get('href')
            if not href:
                continue
            link = urljoin(BASE, href)
            if link in seen:
                continue
            seen.add(link)

            title = (a.get_text(strip=True) or a.get('title') or '').strip()
            if not title:
                title_el = a.select_one('h3, h2, .title')
                title = title_el.get_text(strip=True) if title_el else ''

            parent = a
            for _ in range(3):
                if parent is None:
                    break
                if parent.select_one('time, .date, .meta'):
                    break
                parent = parent.parent

            time_el = parent.select_one('time, .date, .meta') if parent else None
            venue_el = parent.select_one('.venue, .location, .place') if parent else None
            desc = parent.select_one('p, .summary, .excerpt') if parent else None
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
                'source': 'CityOfSydney',
                'original_url': link,
            })
    except Exception as e:
        print(f"cityofsydney scraper error: {e}")
    return results
