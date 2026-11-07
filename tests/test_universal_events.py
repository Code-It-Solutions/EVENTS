"""Organiser isolation + free public registration. Run: python -m pytest tests -q"""
import os
import tempfile

_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name
os.environ['DATABASE_URL'] = f'sqlite:///{_db}'

import pytest
from datetime import date, timedelta
from app import create_app, db
from app.models import User, Event, Delegate

SECRETS = ['Kayo Secret Person', 'Legacy Secret Person', 'Bob Attendee Zed']


@pytest.fixture(scope='module')
def app():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(name='Admin', email='admin@example.com', role='super_admin', is_approved=True, approval_status='approved')
        admin.set_password('x')
        db.session.add(admin)
        db.session.commit()
        kayo = Event(name='KAYO', slug='kayo', start_date=date.today(), end_date=date.today(),
                     created_by=admin.id, is_published=True)
        db.session.add(kayo)
        db.session.commit()
        for name, ev in [(SECRETS[0], kayo.id), (SECRETS[1], None)]:
            db.session.add(Delegate(ticket_number=name[:4] + '-1', name=name, local_church='c', parish='p',
                                    archdeaconry='a', gender='male', registered_by=admin.id, event_id=ev))
        db.session.commit()
    yield app
    with app.app_context():
        db.engine.dispose()
    os.remove(_db)


def login(app, email, password):
    c = app.test_client()
    c.post('/login', data={'email': email, 'password': password})
    return c


def make_organiser(app, name, email):
    r = app.test_client().post('/signup', data={'name': name, 'email': email, 'password': 'password1'})
    assert r.status_code == 302
    return login(app, email, 'password1')


def test_organiser_flow_and_isolation(app):
    a = make_organiser(app, 'Alice', 'alice@example.com')
    b = make_organiser(app, 'Bob', 'bob@example.com')
    day = (date.today() + timedelta(days=7)).isoformat()

    for client, name, slug in [(a, 'Alice Fest', 'alice-fest'), (b, 'Bob Meetup', 'bob-meetup')]:
        r = client.post('/events/create', data={'name': name, 'slug': slug, 'start_date': day,
                                                'end_date': day, 'is_published': 'on'})
        assert r.status_code == 302, r.data[:300]

    # duplicate slug is rejected, not a crash
    r = b.post('/events/create', data={'name': 'x', 'slug': 'alice-fest', 'start_date': day, 'end_date': day})
    assert r.status_code == 200 and b'already taken' in r.data

    with app.app_context():
        ev_a = Event.query.filter_by(slug='alice-fest').one()
        ev_b = Event.query.filter_by(slug='bob-meetup').one()
        ev_a.set_custom_fields([{'name': 'T-Shirt', 'type': 'select', 'required': True, 'options': ['S', 'M']}])
        db.session.commit()
        a_id, b_id = ev_a.id, ev_b.id

    # free public registration issues a ticket; required custom field enforced
    pub = app.test_client()
    assert b'T-Shirt is required' in pub.post('/register/e/alice-fest', data={'name': 'Ann'}).data
    r = pub.post('/register/e/alice-fest', data={'name': 'Ann Attendee', 'phone': '0700000001', 'cf_0': 'M'})
    assert r.status_code == 200 and b'registered' in r.data
    assert b'already registered' in pub.post('/register/e/alice-fest',
                                             data={'name': 'Ann2', 'phone': '0700000001', 'cf_0': 'S'}).data
    pub.post('/register/e/bob-meetup', data={'name': SECRETS[2]})

    with app.app_context():
        ann = Delegate.query.filter_by(name='Ann Attendee').one()
        assert ann.is_paid and ann.event_id == a_id and ann.ticket_number.startswith('ALICE-FEST-')
        assert ann.get_custom_field_values() == {'T-Shirt': 'M'}
        ann_id, ann_ticket = ann.id, ann.ticket_number

    # Bob cannot reach Alice's event or attendee
    assert b.get(f'/events/{a_id}').status_code == 404
    assert b.get(f'/badges/print/{ann_id}').status_code == 404
    assert b.post('/checkin/api/manual', json={'delegate_id': ann_id}).get_json()['success'] is False
    assert b.post('/checkin/api/scan', json={'qr_data': f'KAYO|{ann_ticket}|x|y'}).get_json()['success'] is False
    assert b.get('/checkin/api/search-delegate?q=Ann').get_json()['results'] == []
    assert b.post('/checkin/api/manual', json={'delegate_id': ann_id, 'event_id': b_id}).get_json()['success'] is False

    # Alice can check her attendee in
    assert a.post('/checkin/api/manual', json={'delegate_id': ann_id, 'event_id': a_id}).get_json()['success'] is True
    assert b'Ann Attendee' in a.get(f'/events/{a_id}').data
    with app.app_context():
        assert db.session.get(Delegate, ann_id).checked_in_at is not None

    # Sweep every GET page as Alice: no crashes, no other people's attendees
    errors, leaks = [], []
    for rule in app.url_map.iter_rules():
        if 'GET' not in rule.methods or rule.arguments or 'logout' in rule.rule:
            continue
        r = a.get(rule.rule)
        if r.status_code >= 500:
            errors.append(rule.rule)
        if any(s.encode() in r.data for s in SECRETS):
            leaks.append(rule.rule)
    for url in ['/api/search?q=Secret', '/api/search?q=Zed', '/api/check-duplicate?name=Kayo+Secret+Person',
                '/checkin/api/search-delegate?q=Secret', '/delegates/export']:
        r = a.get(url)
        if r.status_code >= 500:
            errors.append(url)
        if any(s.encode() in r.data for s in SECRETS):
            leaks.append(url)
    assert not errors, errors
    assert not leaks, leaks


def test_unpublished_event_has_no_public_page(app):
    with app.app_context():
        ev = Event(name='Hidden', slug='hidden', start_date=date.today(), end_date=date.today(), is_published=False)
        db.session.add(ev)
        db.session.commit()
    assert app.test_client().get('/register/e/hidden').status_code == 404


def test_admin_still_sees_kayo(app):
    admin = login(app, 'admin@example.com', 'x')
    assert b'KAYO' in admin.get('/events/').data
