import os
os.environ['DB_PATH'] = 'sqlite:///:memory:'
import json
from importlib import reload
import app as appmod
reload(appmod)
app = appmod.app
SessionLocal = appmod.SessionLocal
Event = appmod.Event
from datetime import datetime, timezone


def setup_module(module):
    # insert a test event
    db = SessionLocal()
    ev = Event(title='Test API Event', original_url='http://example.com/test-api', city='Sydney', last_scraped_time=datetime.now(timezone.utc), active=True)
    db.add(ev)
    db.commit()
    db.close()


def teardown_module(module):
    db = SessionLocal()
    db.query(Event).filter(Event.original_url == 'http://example.com/test-api').delete()
    db.commit()
    db.close()


def test_list_events():
    client = app.test_client()
    r = client.get('/api/events')
    assert r.status_code == 200
    data = json.loads(r.data)
    assert isinstance(data, list)
    # at least one event should be present (the one we added)
    assert any(e.get('original_url') == 'http://example.com/test-api' for e in data)
