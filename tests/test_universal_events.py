"""Organiser isolation + free public registration. Run: python -m pytest tests -q"""
import os
import tempfile

import pytest
from datetime import date, timedelta
from app import create_app, db
from app.models import User, Event, Delegate

SECRETS = ['Kayo Secret Person', 'Legacy Secret Person', 'Bob Attendee Zed']


@pytest.fixture(scope='module')
def app():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    # never drop a real database: refuse unless bound to the temp file set in conftest.py
    uri = app.config['SQLALCHEMY_DATABASE_URI']
    assert uri == os.environ['DATABASE_URL'] and tempfile.gettempdir().replace('\\', '/') in uri.replace('\\', '/'), uri
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


def test_organiser_budgets_are_private(app):
    """Runs after test_organiser_flow_and_isolation (Alice/Bob and their events exist)."""
    from app.models.budget import Budget, BudgetItem
    a = login(app, 'alice@example.com', 'password1')
    b = login(app, 'bob@example.com', 'password1')
    with app.app_context():
        a_ev = Event.query.filter_by(slug='alice-fest').one().id
        b_ev = Event.query.filter_by(slug='bob-meetup').one().id

    # Bob cannot attach a budget to Alice's event; an organiser budget must have an event
    b.post('/budget/create', data={'name': 'Sneaky', 'event_id': a_ev})
    b.post('/budget/create', data={'name': 'Unlinked', 'event_id': ''})
    with app.app_context():
        assert Budget.query.filter(Budget.name.in_(['Sneaky', 'Unlinked'])).count() == 0

    r = a.post('/budget/create', data={'name': 'Fest budget', 'event_id': a_ev})
    assert r.status_code == 302
    with app.app_context():
        bid = Budget.query.filter_by(name='Fest budget').one().id

    # items: junk numbers are a 400, not a crash
    assert a.post(f'/budget/{bid}/item/add', data={'name': 'Tent', 'budgeted_amount': 'abc'}).status_code == 400
    assert a.post(f'/budget/{bid}/item/add', data={'name': 'Tent', 'budgeted_amount': '-5'}).status_code == 400
    a.post(f'/budget/{bid}/item/add', data={'name': 'Tent', 'category': 'venue', 'quantity': '2', 'unit_cost': '1500'})
    a.post(f'/budget/{bid}/activate')
    with app.app_context():
        item_id = BudgetItem.query.filter_by(budget_id=bid).one().id
    a.post(f'/budget/item/{item_id}/expenditure/add',
           data={'date': date.today().isoformat(), 'description': 'Deposit', 'amount': '1000'})
    with app.app_context():
        budget = db.session.get(Budget, bid)
        assert budget.total_budgeted == 3000 and budget.total_spent == 1000  # organiser entries auto-approved

    # Bob sees none of it
    assert b'Fest budget' not in b.get('/budget/').data
    for url in [f'/budget/{bid}', f'/budget/{bid}/report', f'/budget/{bid}/edit', f'/budget/item/{item_id}/edit']:
        assert b.get(url).status_code == 404, url
    assert b.post(f'/budget/{bid}/delete').status_code == 404
    assert b.post(f'/budget/{bid}/item/add', data={'name': 'x', 'budgeted_amount': '1'}).status_code == 404
    with app.app_context():
        assert db.session.get(Budget, bid) is not None and BudgetItem.query.filter_by(budget_id=bid).count() == 1

    # Bob can still budget for his own event
    assert b.post('/budget/create', data={'name': 'Meetup budget', 'event_id': b_ev}).status_code == 302
    assert b'Meetup budget' in b.get('/budget/').data and b'Fest budget' in a.get('/budget/').data


def test_organisers_cannot_open_kayo_pages(app):
    a = login(app, 'alice@example.com', 'password1')
    for url in ['/delegates/', '/delegates/register', '/payments/', '/funds/pledges', '/admin/',
                '/help', '/complete-profile', '/finance/', '/communications/']:
        r = a.get(url)
        assert r.status_code == 302 and r.location.endswith('/events/'), (url, r.status_code, r.location)
    assert a.get('/events/').status_code == 200
    assert b'KAYO' not in a.get('/login').data
    r = app.test_client().post('/signup', data={'name': 'T', 'email': 't@yopmail.com', 'password': 'password1'})
    assert b'permanent email' in r.data
