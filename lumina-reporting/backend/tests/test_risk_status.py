import datetime

import risk_status
from database import db_session
from models import PerformanceSnapshot, Report, ReportTransition

TODAY = datetime.date(2026, 9, 19)

def _make_report(app, client_id, title='Q3 Factsheet', status='draft', due_date=None):
    with app.app_context():
        report = Report(title=title, client_id=client_id, status=status, due_date=due_date, created_by=1)
        db_session.add(report)
        db_session.commit()
        return report.id

def _transition(app, report_id, from_status, to_status, days_ago=0):
    with app.app_context():
        db_session.add(ReportTransition(
            report_id=report_id, from_status=from_status, to_status=to_status, actor_id=1,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=days_ago),
        ))
        db_session.commit()

def test_client_with_nothing_on_file_is_on_track(app, sample_client):
    with app.app_context():
        assert risk_status.client_risk(sample_client, today=TODAY)['status'] == risk_status.ON_TRACK

def test_past_due_open_report_breaches_sla(app, sample_client):
    _make_report(app, sample_client, due_date=TODAY - datetime.timedelta(days=4))
    with app.app_context():
        result = risk_status.client_risk(sample_client, today=TODAY)
    assert result['status'] == risk_status.SLA_BREACHED
    # The reason has to name the actual report and date, since the UI shows it verbatim.
    assert 'Q3 Factsheet' in result['reason']
    assert '2026-09-15' in result['reason']
    assert '4 days ago' in result['reason']

def test_past_due_report_that_already_went_out_does_not_breach(app, sample_client):
    # A delivered report can't be overdue -- 'distributed' is the legacy
    # terminal status for a report with no workflow diagram.
    _make_report(app, sample_client, status='distributed', due_date=TODAY - datetime.timedelta(days=4))
    with app.app_context():
        assert risk_status.client_risk(sample_client, today=TODAY)['status'] == risk_status.ON_TRACK

def test_report_due_soon_is_a_watch(app, sample_client):
    _make_report(app, sample_client, due_date=TODAY + datetime.timedelta(days=2))
    with app.app_context():
        result = risk_status.client_risk(sample_client, today=TODAY)
    assert result['status'] == risk_status.WATCH
    assert 'in 2 days' in result['reason']

def test_report_due_far_out_is_not_a_watch(app, sample_client):
    _make_report(app, sample_client, due_date=TODAY + datetime.timedelta(days=30))
    with app.app_context():
        assert risk_status.client_risk(sample_client, today=TODAY)['status'] == risk_status.ON_TRACK

def test_underperformance_against_benchmark_is_a_watch(app, sample_client):
    with app.app_context():
        db_session.add(PerformanceSnapshot(
            client_id=sample_client, as_of_date=datetime.date(2026, 6, 30),
            period_type='YTD', return_pct=5.1, benchmark_return_pct=8.1,
        ))
        db_session.commit()
        result = risk_status.client_risk(sample_client, today=TODAY)
    assert result['status'] == risk_status.WATCH
    assert '300bps' in result['reason']

def test_outperformance_is_on_track(app, sample_client):
    with app.app_context():
        db_session.add(PerformanceSnapshot(
            client_id=sample_client, as_of_date=datetime.date(2026, 6, 30),
            period_type='YTD', return_pct=9.4, benchmark_return_pct=8.1,
        ))
        db_session.commit()
        assert risk_status.client_risk(sample_client, today=TODAY)['status'] == risk_status.ON_TRACK

def test_report_sent_back_to_an_earlier_status_is_flagged(app, sample_client):
    report_id = _make_report(app, sample_client)
    # draft -> review -> back to draft. The revisit is what marks it, not a
    # hardcoded status ordering, so this works for firm-defined diagrams too.
    _transition(app, report_id, 'draft', 'review', days_ago=5)
    _transition(app, report_id, 'review', 'draft', days_ago=2)
    with app.app_context():
        result = risk_status.client_risk(sample_client, today=TODAY)
    assert result['status'] == risk_status.FLAGGED
    assert 'sent back to draft' in result['reason']

def test_forward_only_progress_is_not_flagged(app, sample_client):
    report_id = _make_report(app, sample_client)
    _transition(app, report_id, 'draft', 'review', days_ago=5)
    _transition(app, report_id, 'review', 'approved', days_ago=2)
    with app.app_context():
        assert risk_status.client_risk(sample_client, today=TODAY)['status'] == risk_status.ON_TRACK

def test_old_rework_no_longer_flags_the_client(app, sample_client):
    report_id = _make_report(app, sample_client)
    _transition(app, report_id, 'draft', 'review', days_ago=90)
    _transition(app, report_id, 'review', 'draft', days_ago=80)
    with app.app_context():
        assert risk_status.client_risk(sample_client, today=TODAY)['status'] == risk_status.ON_TRACK

def test_breach_outranks_rework_and_watch(app, sample_client):
    # All three signals present at once -- the worst one has to win.
    report_id = _make_report(app, sample_client, due_date=TODAY - datetime.timedelta(days=1))
    _transition(app, report_id, 'draft', 'review', days_ago=5)
    _transition(app, report_id, 'review', 'draft', days_ago=2)
    with app.app_context():
        db_session.add(PerformanceSnapshot(
            client_id=sample_client, as_of_date=datetime.date(2026, 6, 30),
            period_type='YTD', return_pct=5.1, benchmark_return_pct=8.1,
        ))
        db_session.commit()
        result = risk_status.client_risk(sample_client, today=TODAY)
    assert result['status'] == risk_status.SLA_BREACHED

def test_rework_outranks_watch(app, sample_client):
    report_id = _make_report(app, sample_client)
    _transition(app, report_id, 'draft', 'review', days_ago=5)
    _transition(app, report_id, 'review', 'draft', days_ago=2)
    with app.app_context():
        db_session.add(PerformanceSnapshot(
            client_id=sample_client, as_of_date=datetime.date(2026, 6, 30),
            period_type='YTD', return_pct=5.1, benchmark_return_pct=8.1,
        ))
        db_session.commit()
        assert risk_status.client_risk(sample_client, today=TODAY)['status'] == risk_status.FLAGGED
