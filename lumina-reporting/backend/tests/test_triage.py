import datetime

from database import db_session
from models import Report, ReportTransition

def _make_report(app, client_id, title='Q3 Factsheet', status='draft', due_date=None, created_days_ago=0):
    with app.app_context():
        report = Report(
            title=title, client_id=client_id, status=status, due_date=due_date, created_by=1,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=created_days_ago),
        )
        db_session.add(report)
        db_session.commit()
        return report.id

def _move(app, report_id, from_status, to_status, days_ago=0):
    with app.app_context():
        db_session.add(ReportTransition(
            report_id=report_id, from_status=from_status, to_status=to_status, actor_id=1,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=days_ago),
        ))
        db_session.commit()

def _triage(client, headers):
    response = client.get('/api/triage', headers=headers)
    assert response.status_code == 200
    return response.get_json()

def test_triage_requires_staff_role(client, auth_headers, client_portal_headers):
    assert client.get('/api/triage', headers=auth_headers).status_code == 200
    assert client.get('/api/triage', headers=client_portal_headers).status_code == 403

def test_empty_instance_reports_all_zeroes(client, auth_headers):
    body = _triage(client, auth_headers)
    assert body['respondingCount'] == 0
    assert body['stuckCount'] == 0
    assert body['overdueCount'] == 0
    assert body['readyToDistributeCount'] == 0

def test_untouched_old_draft_counts_as_stuck(client, auth_headers, sample_client, app):
    # No transitions at all -- creation time is the only signal that it's
    # been sitting, so it still has to age into 'stuck'.
    _make_report(app, sample_client, created_days_ago=10)
    assert _triage(client, auth_headers)['stuckCount'] == 1

def test_recently_created_draft_is_not_stuck(client, auth_headers, sample_client, app):
    _make_report(app, sample_client, created_days_ago=0)
    assert _triage(client, auth_headers)['stuckCount'] == 0

def test_report_with_recent_movement_is_not_stuck(client, auth_headers, sample_client, app):
    report_id = _make_report(app, sample_client, created_days_ago=30)
    _move(app, report_id, 'draft', 'review', days_ago=1)
    assert _triage(client, auth_headers)['stuckCount'] == 0

def test_report_whose_last_movement_is_old_is_stuck(client, auth_headers, sample_client, app):
    report_id = _make_report(app, sample_client, created_days_ago=30)
    _move(app, report_id, 'draft', 'review', days_ago=9)
    assert _triage(client, auth_headers)['stuckCount'] == 1

def test_delivered_report_is_neither_stuck_nor_overdue(client, auth_headers, sample_client, app):
    # Already out the door: it can't be overdue, stuck, or awaiting sending.
    _make_report(
        app, sample_client, status='distributed', created_days_ago=60,
        due_date=datetime.date.today() - datetime.timedelta(days=30),
    )
    body = _triage(client, auth_headers)
    assert body['stuckCount'] == 0
    assert body['overdueCount'] == 0
    assert body['readyToDistributeCount'] == 0

def test_past_due_open_report_counts_as_overdue(client, auth_headers, sample_client, app):
    _make_report(app, sample_client, due_date=datetime.date.today() - datetime.timedelta(days=2))
    assert _triage(client, auth_headers)['overdueCount'] == 1

def test_future_due_date_is_not_overdue(client, auth_headers, sample_client, app):
    _make_report(app, sample_client, due_date=datetime.date.today() + datetime.timedelta(days=5))
    assert _triage(client, auth_headers)['overdueCount'] == 0

def test_report_with_no_due_date_is_never_overdue(client, auth_headers, sample_client, app):
    _make_report(app, sample_client, due_date=None, created_days_ago=90)
    assert _triage(client, auth_headers)['overdueCount'] == 0

def test_approved_legacy_report_is_ready_to_distribute(client, auth_headers, sample_client, app):
    _make_report(app, sample_client, status='approved')
    assert _triage(client, auth_headers)['readyToDistributeCount'] == 1

def test_draft_is_not_ready_to_distribute(client, auth_headers, sample_client, app):
    _make_report(app, sample_client, status='draft')
    assert _triage(client, auth_headers)['readyToDistributeCount'] == 0

def test_responding_count_matches_my_queue(client, auth_headers, sample_client):
    # The two have to agree -- the card links straight to that queue, so a
    # count that disagrees with the page it opens is a bug users would see.
    created = client.post('/api/reports', headers=auth_headers, json={'title': 'Q3', 'client_id': sample_client})
    client.post(f"/api/reports/{created.get_json()['id']}/submit", headers=auth_headers)

    queue = client.get('/api/reports/my-queue', headers=auth_headers).get_json()
    assert _triage(client, auth_headers)['respondingCount'] == len(queue)

def test_stuck_filter_returns_the_same_reports_the_card_counts(client, auth_headers, sample_client, app):
    # The card links to /reports?stuck=1, so the list it opens has to be the
    # set the count was taken from -- both go through report_filters.
    stuck_id = _make_report(app, sample_client, title='Stale', created_days_ago=10)
    _make_report(app, sample_client, title='Fresh', created_days_ago=0)

    assert _triage(client, auth_headers)['stuckCount'] == 1
    rows = client.get('/api/reports?stuck=1', headers=auth_headers).get_json()
    assert [row['id'] for row in rows] == [stuck_id]

def test_overdue_filter_returns_the_same_reports_the_card_counts(client, auth_headers, sample_client, app):
    overdue_id = _make_report(
        app, sample_client, title='Late', due_date=datetime.date.today() - datetime.timedelta(days=2),
    )
    _make_report(app, sample_client, title='On time', due_date=datetime.date.today() + datetime.timedelta(days=2))
    _make_report(app, sample_client, title='No deadline')

    assert _triage(client, auth_headers)['overdueCount'] == 1
    rows = client.get('/api/reports?overdue=1', headers=auth_headers).get_json()
    assert [row['id'] for row in rows] == [overdue_id]

def test_filters_combine_and_leave_the_unfiltered_list_alone(client, auth_headers, sample_client, app):
    both_id = _make_report(
        app, sample_client, title='Late and stale', created_days_ago=10,
        due_date=datetime.date.today() - datetime.timedelta(days=2),
    )
    _make_report(app, sample_client, title='Only stale', created_days_ago=10)
    _make_report(app, sample_client, title='Only late', due_date=datetime.date.today() - datetime.timedelta(days=1))

    rows = client.get('/api/reports?stuck=1&overdue=1', headers=auth_headers).get_json()
    assert [row['id'] for row in rows] == [both_id]
    assert len(client.get('/api/reports', headers=auth_headers).get_json()) == 3

def test_distributed_report_is_excluded_from_both_filters(client, auth_headers, sample_client, app):
    _make_report(
        app, sample_client, status='distributed', created_days_ago=60,
        due_date=datetime.date.today() - datetime.timedelta(days=30),
    )
    assert client.get('/api/reports?stuck=1', headers=auth_headers).get_json() == []
    assert client.get('/api/reports?overdue=1', headers=auth_headers).get_json() == []
