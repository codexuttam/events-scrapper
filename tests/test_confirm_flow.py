import uuid
from datetime import datetime, timezone

import app as appmod


def test_confirm_endpoint_marks_request_confirmed(tmp_path, monkeypatch):
    # Use a fresh in-memory DB by overriding DB_PATH for this import context if needed
    client = appmod.app.test_client()
    # create a ticket request via POST
    resp = client.post('/api/ticket-request', json={
        'email': 'tester@example.com',
        'consent': True,
        'event_url': 'https://example.com/event/1'
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True

    # find the TicketRequest in DB (use a fresh session)
    db = appmod.SessionLocal()
    tr = db.query(appmod.TicketRequest).filter(appmod.TicketRequest.email == 'tester@example.com').first()
    assert tr is not None
    token = tr.confirm_token

    # call confirm endpoint
    r2 = client.get(f'/api/ticket-request/confirm?token={token}')
    # should redirect to event_url
    assert r2.status_code in (302, 301, 200)

    # reload from DB (expire local session cache first to pick up external changes)
    db.expire_all()
    tr2 = db.query(appmod.TicketRequest).filter(appmod.TicketRequest.id == tr.id).first()
    assert tr2.confirmed is True
    assert tr2.confirmed_at is not None
    db.close()
