import os
import json
from datetime import datetime, timezone

from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
from sqlalchemy import (Column, Integer, String, DateTime, Boolean, Text, create_engine, text)
from sqlalchemy.orm import declarative_base, sessionmaker

from apscheduler.schedulers.background import BackgroundScheduler

from scrapers.allevents import scrape_allevents
from scrapers.eventfinda import scrape_eventfinda
from scrapers.skiddle import scrape_skiddle
from scrapers.sydney_com import scrape_sydney_com
from scrapers.cityofsydney import scrape_cityofsydney
import re
import uuid
import socket
try:
    import dns.resolver
except Exception:
    dns = None
import smtplib
from email.message import EmailMessage
import threading
import time
from functools import wraps
from flask import make_response
from threading import Lock

DB_PATH = os.environ.get("DB_PATH", "sqlite:///events.db")

Base = declarative_base()


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    title = Column(String(512), nullable=False)
    start_time = Column(String(128))
    end_time = Column(String(128))
    venue = Column(String(512))
    address = Column(String(1024))
    city = Column(String(128))
    description = Column(Text)
    category = Column(String(256))
    image_url = Column(String(1024))
    source = Column(String(256))
    original_url = Column(String(1024), unique=True, index=True)
    last_scraped_time = Column(DateTime)
    active = Column(Boolean, default=True)
    featured = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "venue": self.venue,
            "address": self.address,
            "city": self.city,
            "description": self.description,
            "category": self.category,
            "image_url": self.image_url,
            "source": self.source,
            "original_url": self.original_url,
            "last_scraped_time": self.last_scraped_time.isoformat() if self.last_scraped_time else None,
            "active": self.active,
            "featured": self.featured,
        }


class TicketRequest(Base):
    __tablename__ = "ticket_requests"
    id = Column(Integer, primary_key=True)
    email = Column(String(320), nullable=False)
    consent = Column(Boolean, default=False)
    event_id = Column(Integer, nullable=True)
    event_url = Column(String(1024))
    created_at = Column(DateTime)
    confirmed = Column(Boolean, default=False)
    confirm_token = Column(String(128), nullable=True)
    confirm_sent_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "consent": self.consent,
            "event_id": self.event_id,
            "event_url": self.event_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "confirmed": self.confirmed,
            "confirm_sent_at": self.confirm_sent_at.isoformat() if self.confirm_sent_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


engine = create_engine(DB_PATH, connect_args={"check_same_thread": False} if "sqlite" in DB_PATH else {})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)


def ensure_schema():
    # ensure 'featured' column exists for sqlite (simple migration)
    if "sqlite" in DB_PATH:
        conn = engine.connect()
        try:
            # Use text() to execute PRAGMA via SQLAlchemy connection
            res = conn.execute(text("PRAGMA table_info('events')"))
            cols = [r[1] for r in res.fetchall()]
            if 'featured' not in cols:
                try:
                    conn.execute(text("ALTER TABLE events ADD COLUMN featured BOOLEAN DEFAULT 0"))
                    print("Added 'featured' column to events table")
                except Exception as e:
                    # best-effort: ignore if cannot alter
                    print(f"Could not add 'featured' column: {e}")
        except Exception as e:
            print(f"ensure_schema error: {e}")
        finally:
            conn.close()

    # Also ensure ticket_requests columns exist (best-effort)
    if "sqlite" in DB_PATH:
        conn = engine.connect()
        try:
            res = conn.execute(text("PRAGMA table_info('ticket_requests')"))
            cols = [r[1] for r in res.fetchall()]
            add_cols = []
            if 'confirmed' not in cols:
                add_cols.append("ALTER TABLE ticket_requests ADD COLUMN confirmed BOOLEAN DEFAULT 0")
            if 'confirm_token' not in cols:
                add_cols.append("ALTER TABLE ticket_requests ADD COLUMN confirm_token VARCHAR(128)")
            if 'confirm_sent_at' not in cols:
                add_cols.append("ALTER TABLE ticket_requests ADD COLUMN confirm_sent_at DATETIME")
            if 'confirmed_at' not in cols:
                add_cols.append("ALTER TABLE ticket_requests ADD COLUMN confirmed_at DATETIME")
            if 'ip_address' not in cols:
                add_cols.append("ALTER TABLE ticket_requests ADD COLUMN ip_address VARCHAR(64)")
            if 'user_agent' not in cols:
                add_cols.append("ALTER TABLE ticket_requests ADD COLUMN user_agent VARCHAR(512)")
            for sql in add_cols:
                try:
                    conn.execute(text(sql))
                    print(f"Executed: {sql}")
                except Exception as e:
                    print(f"Could not execute '{sql}': {e}")
        except Exception as e:
            # table may not exist yet; create_all will handle it
            print(f"ensure_schema ticket_requests error: {e}")
        finally:
            conn.close()


ensure_schema()

app = Flask(__name__)
CORS(app)

# Simple in-memory rate limiter: { ip: [timestamps] }
_rate_limiter = {}
_rate_lock = Lock()
RATE_LIMIT_MAX = int(os.environ.get('RATE_LIMIT_MAX', '5'))
RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', str(60 * 60)))  # seconds

# Simple in-memory admin session store: { token: expiry_timestamp }
_admin_sessions = {}
_admin_lock = Lock()
ADMIN_SESSION_TTL = int(os.environ.get('ADMIN_SESSION_TTL', str(60 * 60)))  # seconds


def require_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # allow bypass if ADMIN_TOKEN env var set and matches
        admin_token_env = os.environ.get('ADMIN_TOKEN')
        header = request.headers.get('X-Admin-Token') or request.args.get('admin_token')
        if admin_token_env and header and header == admin_token_env:
            return func(*args, **kwargs)

        # otherwise check in-memory admin sessions
        if header:
            now_ts = time.time()
            with _admin_lock:
                exp = _admin_sessions.get(header)
                if exp and exp > now_ts:
                    return func(*args, **kwargs)
                else:
                    # expired or missing
                    if header in _admin_sessions:
                        del _admin_sessions[header]
        return jsonify({'error': 'unauthorized'}), 401
    return wrapper


def normalize_event(d):
    # expected keys from scrapers: title, start_time, end_time, venue, address, city, description, category, image_url, source, original_url
    now = datetime.now(timezone.utc)
    return {
        "title": d.get("title") or "",
        "start_time": d.get("start_time"),
        "end_time": d.get("end_time"),
        "venue": d.get("venue"),
        "address": d.get("address"),
        "city": d.get("city") or "Sydney",
        "description": d.get("description"),
        "category": d.get("category"),
        "image_url": d.get("image_url"),
        "source": d.get("source"),
        "original_url": d.get("original_url"),
        "last_scraped_time": now,
    }


def run_scrapers():
    print("Running scrapers...")
    scrapers = [
        scrape_allevents,
        scrape_eventfinda,
        scrape_skiddle,
        scrape_sydney_com,
        scrape_cityofsydney,
    ]
    all_events = []
    for s in scrapers:
        try:
            items = s(city="Sydney")
            if items:
                all_events.extend(items)
        except Exception as e:
            print(f"Scraper {s.__name__} failed: {e}")

    db = SessionLocal()
    seen_urls = set()
    now = datetime.now(timezone.utc)

    for raw in all_events:
        ev = normalize_event(raw)
        url = ev.get("original_url")
        if not url:
            continue
        seen_urls.add(url)
        existing = db.query(Event).filter(Event.original_url == url).first()
        if existing:
            # detect updates
            changed = False
            for field in ["title", "start_time", "end_time", "venue", "address", "description", "category", "image_url"]:
                if getattr(existing, field) != ev.get(field):
                    setattr(existing, field, ev.get(field))
                    changed = True
            if not existing.active:
                existing.active = True
                changed = True
            existing.last_scraped_time = now
            if changed:
                print(f"Updated event: {existing.original_url}")
        else:
            new = Event(
                title=ev.get("title"),
                start_time=ev.get("start_time"),
                end_time=ev.get("end_time"),
                venue=ev.get("venue"),
                address=ev.get("address"),
                city=ev.get("city"),
                description=ev.get("description"),
                category=ev.get("category"),
                image_url=ev.get("image_url"),
                source=ev.get("source"),
                original_url=ev.get("original_url"),
                last_scraped_time=now,
                active=True,
            )
            db.add(new)
            print(f"Added event: {new.original_url}")

    # mark events not seen in this run as inactive if their last_scraped_time is older than 3 days
    cutoff = now
    existing_events = db.query(Event).all()
    for e in existing_events:
        if e.original_url not in seen_urls:
            # if last scraped more than 3 days ago, mark inactive
            if e.last_scraped_time and (now - e.last_scraped_time).days >= 3:
                if e.active:
                    e.active = False
                    print(f"Marked inactive: {e.original_url}")

    db.commit()
    db.close()
    print("Scrape complete")


@app.route("/api/ticket-request", methods=["POST"])
def ticket_request():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip()
    consent = bool(data.get("consent"))
    event_id = data.get("event_id")
    event_url = data.get("event_url") or data.get("original_url")
    if not email:
        return jsonify({"error": "email required"}), 400

    # basic email format validation
    email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    if not email_re.match(email):
        return jsonify({"error": "invalid email format"}), 400

    # optional MX lookup (best-effort)
    mx_ok = None
    domain = email.split('@')[-1]
    if dns:
        try:
            answers = dns.resolver.resolve(domain, 'MX')
            mx_ok = len(answers) > 0
        except Exception:
            mx_ok = False
    else:
        # dns library not available; leave as None
        mx_ok = None

    token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    ua = request.headers.get('User-Agent')

    # rate limiting per IP
    with _rate_lock:
        ts = _rate_limiter.get(ip, [])
        now_ts = time.time()
        # remove old timestamps
        ts = [t for t in ts if now_ts - t < RATE_LIMIT_WINDOW]
        if len(ts) >= RATE_LIMIT_MAX:
            return jsonify({'error': 'rate_limited'}), 429
        ts.append(now_ts)
        _rate_limiter[ip] = ts

    db = SessionLocal()
    tr = TicketRequest(
        email=email,
        consent=consent,
        event_id=event_id,
        event_url=event_url,
        created_at=now,
        confirmed=False,
        confirm_token=token,
        confirm_sent_at=None,
        confirmed_at=None,
        ip_address=ip,
        user_agent=ua,
    )
    db.add(tr)
    db.commit()
    tr_id = tr.id

    # send confirmation email (best-effort)
    def _send_and_update(email_to, token, tr_id, event_title=None):
        smtp_host = os.environ.get('SMTP_HOST')
        smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        smtp_user = os.environ.get('SMTP_USER')
        smtp_pass = os.environ.get('SMTP_PASS')
        from_email = os.environ.get('FROM_EMAIL', 'no-reply@example.com')
        confirm_url = os.environ.get('BASE_URL', f'http://localhost:5000') + f"/api/ticket-request/confirm?token={token}"
        subj = f"Confirm your email for event{(' - ' + event_title) if event_title else ''}"
        body = f"Please confirm your email by clicking the link below:\n\n{confirm_url}\n\nIf you didn't request this, ignore this message."
        sent = False
        try:
            if smtp_host and smtp_user and smtp_pass:
                msg = EmailMessage()
                msg['Subject'] = subj
                msg['From'] = from_email
                msg['To'] = email_to
                msg.set_content(body)
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
                    s.starttls()
                    s.login(smtp_user, smtp_pass)
                    s.send_message(msg)
                sent = True
            else:
                # no smtp configured; just log
                print(f"Confirmation link for {email_to}: {confirm_url}")
                sent = False
        except Exception as e:
            print(f"Failed to send confirmation email: {e}")
            sent = False

        # update DB
        try:
            db2 = SessionLocal()
            tr2 = db2.query(TicketRequest).filter(TicketRequest.id == tr_id).first()
            if tr2:
                if sent:
                    tr2.confirm_sent_at = datetime.now(timezone.utc)
                db2.add(tr2)
                db2.commit()
        except Exception as e:
            print(f"Failed to update TicketRequest after sending: {e}")
        finally:
            try:
                db2.close()
            except Exception:
                pass

    # send confirmation asynchronously
    t = threading.Thread(target=_send_and_update, args=(email, token, tr_id, None), daemon=True)
    t.start()

    db.close()
    # note: confirmation sending happens asynchronously; return redirect for UX
    return jsonify({"ok": True, "redirect": event_url, "mx_ok": mx_ok, "confirmation_sent": False})


@app.route('/api/ticket-requests')
def list_ticket_requests():
    """Return JSON list of recent ticket requests, include event title when available."""
    db = SessionLocal()
    items = db.query(TicketRequest).order_by(TicketRequest.created_at.desc()).limit(1000).all()
    out = []
    for t in items:
        ev_title = None
        if t.event_id:
            ev = db.query(Event).filter(Event.id == t.event_id).first()
            if ev:
                ev_title = ev.title
        out.append({
            'id': t.id,
            'email': t.email,
            'consent': bool(t.consent),
            'confirmed': bool(t.confirmed),
            'event_id': t.event_id,
            'event_url': t.event_url,
            'event_title': ev_title,
            'created_at': t.created_at.isoformat() if t.created_at else None,
            'confirm_sent_at': t.confirm_sent_at.isoformat() if t.confirm_sent_at else None,
            'confirmed_at': t.confirmed_at.isoformat() if t.confirmed_at else None,
            'ip_address': t.ip_address,
            'user_agent': t.user_agent,
        })
    db.close()
    return jsonify(out)


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    env_user = os.environ.get('ADMIN_USER')
    env_pass = os.environ.get('ADMIN_PASS')
    if not env_user or not env_pass:
        return jsonify({'error': 'admin not configured'}), 503
    if username != env_user or password != env_pass:
        return jsonify({'error': 'invalid credentials'}), 401
    # generate session token
    token = uuid.uuid4().hex
    expiry = time.time() + ADMIN_SESSION_TTL
    with _admin_lock:
        _admin_sessions[token] = expiry
    return jsonify({'ok': True, 'token': token, 'expires_in': ADMIN_SESSION_TTL})


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    data = request.get_json() or {}
    token = (data.get('token') or request.headers.get('X-Admin-Token'))
    if not token:
        return jsonify({'ok': True})
    with _admin_lock:
        if token in _admin_sessions:
            del _admin_sessions[token]
    return jsonify({'ok': True})


@app.route('/api/ticket-requests.csv')
def ticket_requests_csv():
    import csv
    from io import StringIO
    db = SessionLocal()
    items = db.query(TicketRequest).order_by(TicketRequest.created_at.desc()).all()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['id','email','consent','event_id','event_title','event_url','created_at'])
    for t in items:
        ev_title = ''
        if t.event_id:
            ev = db.query(Event).filter(Event.id == t.event_id).first()
            if ev:
                ev_title = ev.title
        writer.writerow([t.id, t.email, int(bool(t.consent)), t.event_id or '', ev_title, t.event_url or '', t.created_at.isoformat() if t.created_at else ''])
    db.close()
    output = si.getvalue()
    return app.response_class(output, mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=ticket_requests.csv"})


@app.route('/api/ticket-request/confirm')
def confirm_ticket_request():
    token = request.args.get('token')
    if not token:
        return "Missing token", 400
    db = SessionLocal()
    tr = db.query(TicketRequest).filter(TicketRequest.confirm_token == token).first()
    if not tr:
        db.close()
        return "Invalid token", 404
    if not tr.confirmed:
        tr.confirmed = True
        tr.confirmed_at = datetime.now(timezone.utc)
        db.add(tr)
        db.commit()

    # resolve redirect target while session still open
    target = tr.event_url if tr.event_url else None
    if not target and tr.event_id:
        ev = db.query(Event).filter(Event.id == tr.event_id).first()
        if ev:
            target = ev.original_url

    db.close()
    if target:
        return redirect(target)
    # simple confirmation page
    html = """
    <html>
      <head><title>Confirmed</title></head>
      <body>
        <h1>Email confirmed</h1>
        <p>Thank you — your email has been confirmed.</p>
      </body>
    </html>
    """
    resp = make_response(html, 200)
    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
    return resp


scheduler = BackgroundScheduler()
scheduler.add_job(func=run_scrapers, trigger="interval", minutes=30)
scheduler.start()


@app.route("/api/events")
def list_events():
    city = request.args.get("city", "Sydney")
    db = SessionLocal()
    items = db.query(Event).filter(Event.city.ilike(f"%{city}%"), Event.active == True).order_by(Event.start_time).all()
    out = [i.to_dict() for i in items]
    db.close()
    return jsonify(out)


@app.route("/api/scrape", methods=["POST", "GET"])
def trigger_scrape():
    run_scrapers()
    return jsonify({"status": "ok"})


@app.route("/api/events/<int:event_id>", methods=["PATCH"])
def update_event(event_id):
    db = SessionLocal()
    ev = db.query(Event).filter(Event.id == event_id).first()
    if not ev:
        db.close()
        return jsonify({"error": "not found"}), 404
    data = request.get_json() or {}
    allowed = {"active": bool, "featured": bool}
    changed = False
    for key, typ in allowed.items():
        if key in data:
            setattr(ev, key, bool(data[key]))
            changed = True
    if changed:
        ev.last_scraped_time = datetime.now(timezone.utc)
        db.add(ev)
        db.commit()
    out = ev.to_dict()
    db.close()
    return jsonify(out)


if __name__ == "__main__":
    # initial run
    run_scrapers()
    app.run(host="0.0.0.0", port=5000)
