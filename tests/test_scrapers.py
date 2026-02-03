import types
from unittest.mock import patch

from scrapers import allevents, eventfinda, skiddle


class DummyResp:
    def __init__(self, text):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        return None


class DummySession:
    def __init__(self, text):
        self._text = text

    def get(self, url, timeout=10):
        return DummyResp(self._text)


SAMPLE_HTML = """
<html><body>
<div class="event-card"><a href="/sydney/test-event">Test Event</a><span class="date">2026-02-20</span><span class="venue">Test Venue</span></div>
<div class="ef-event"><a href="/event/1">EF Event</a><span class="ef-date">2026-02-21</span></div>
<div class="card"><a href="/skiddle/1">Skiddle Event</a><span class="date">2026-02-22</span></div>
</body></html>
"""


@patch("scrapers.session.create_session")
def test_allevents_returns_list(mock_session):
    mock_session.return_value = DummySession(SAMPLE_HTML)
    items = allevents.scrape_allevents(city="Sydney")
    assert isinstance(items, list)
    assert len(items) > 0


@patch("scrapers.session.create_session")
def test_eventfinda_returns_list(mock_session):
    mock_session.return_value = DummySession(SAMPLE_HTML)
    items = eventfinda.scrape_eventfinda(city="Sydney")
    assert isinstance(items, list)


@patch("scrapers.session.create_session")
def test_skiddle_returns_list(mock_session):
    mock_session.return_value = DummySession(SAMPLE_HTML)
    items = skiddle.scrape_skiddle(city="Sydney")
    assert isinstance(items, list)
