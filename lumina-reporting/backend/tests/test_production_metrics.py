import datetime

import production_metrics
from database import db_session
from models import Client, DataSource, Report, ReportStepInstance, ReportTransition, WorkflowGroup


def _report(app, client_id, title='Report', status='draft', team=None, due_date=None, created_days_ago=0):
    with app.app_context():
        report = Report(
            title=title, client_id=client_id, status=status, team=team, due_date=due_date, created_by=1,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=created_days_ago),
        )
        db_session.add(report)
        db_session.commit()
        return report.id


def _step(app, report_id, node_name, state='active', group_id=None, entered_days_ago=0, hours=None):
    with app.app_context():
        entered = datetime.datetime.utcnow() - datetime.timedelta(days=entered_days_ago)
        db_session.add(ReportStepInstance(
            report_id=report_id, node_id=node_name.lower().replace(' ', '_'), node_name=node_name,
            group_id=group_id, state=state, entered_at=entered,
            completed_at=(entered + datetime.timedelta(hours=hours)) if hours is not None else None,
        ))
        db_session.commit()


def _group(app, name):
    with app.app_context():
        group = WorkflowGroup(name=name, created_by=1)
        db_session.add(group)
        db_session.commit()
        return group.id


# ---------- workflow_stage_progress ----------

def test_stage_progress_counts_active_steps_only(app, sample_client):
    report_id = _report(app, sample_client)
    _step(app, report_id, 'Compliance review', state='active')
    _step(app, report_id, 'Drafting', state='done', hours=4)
    with app.app_context():
        assert production_metrics.workflow_stage_progress() == [{'label': 'Compliance review', 'count': 1}]


def test_stage_progress_counts_a_report_on_two_parallel_branches_twice(app, sample_client):
    # This is the whole reason it reads step instances instead of
    # Report.status -- one report genuinely occupies two steps at once.
    report_id = _report(app, sample_client)
    _step(app, report_id, 'Compliance review')
    _step(app, report_id, 'Portfolio sign-off')
    with app.app_context():
        assert sum(row['count'] for row in production_metrics.workflow_stage_progress()) == 2


# ---------- slowest_steps ----------

def test_slowest_step_averages_completed_visits_and_sorts_slowest_first(app, sample_client):
    report_id = _report(app, sample_client)
    _step(app, report_id, 'Compliance review', state='done', hours=48)
    _step(app, report_id, 'Compliance review', state='done', hours=24)
    _step(app, report_id, 'Drafting', state='done', hours=2)
    _step(app, report_id, 'Drafting', state='done', hours=4)
    with app.app_context():
        steps = production_metrics.slowest_steps()
    assert [step['label'] for step in steps] == ['Compliance review', 'Drafting']
    assert steps[0]['avgHours'] == 36.0
    assert steps[0]['visits'] == 2
    assert steps[1]['avgHours'] == 3.0


def test_a_step_with_one_visit_is_not_reported_as_a_bottleneck(app, sample_client):
    # One slow visit is an anecdote; the threshold keeps it out of the list.
    report_id = _report(app, sample_client)
    _step(app, report_id, 'Compliance review', state='done', hours=200)
    with app.app_context():
        assert production_metrics.slowest_steps() == []


def test_an_in_flight_step_contributes_no_duration(app, sample_client):
    report_id = _report(app, sample_client)
    _step(app, report_id, 'Drafting', state='done', hours=10)
    _step(app, report_id, 'Drafting', state='done', hours=10)
    _step(app, report_id, 'Drafting', state='active', entered_days_ago=30)
    with app.app_context():
        steps = production_metrics.slowest_steps()
    assert steps[0]['avgHours'] == 10.0 and steps[0]['visits'] == 2


# ---------- bottleneck_by_group ----------

def test_bottleneck_groups_active_work_and_reports_the_oldest_wait(app, sample_client):
    compliance = _group(app, 'Compliance')
    report_id = _report(app, sample_client)
    _step(app, report_id, 'Compliance review', group_id=compliance, entered_days_ago=5)
    _step(app, report_id, 'Compliance review', group_id=compliance, entered_days_ago=1)
    with app.app_context():
        rows = production_metrics.bottleneck_by_group()
    assert rows[0]['label'] == 'Compliance'
    assert rows[0]['count'] == 2
    assert rows[0]['oldestDays'] == 5.0


def test_ungrouped_work_is_surfaced_not_dropped(app, sample_client):
    report_id = _report(app, sample_client)
    _step(app, report_id, 'Drafting', group_id=None, entered_days_ago=2)
    with app.app_context():
        rows = production_metrics.bottleneck_by_group()
    assert rows == [{'label': 'Unassigned', 'count': 1, 'oldestDays': 2.0}]


def test_completed_work_is_not_a_bottleneck(app, sample_client):
    compliance = _group(app, 'Compliance')
    report_id = _report(app, sample_client)
    _step(app, report_id, 'Compliance review', group_id=compliance, state='done', hours=3)
    with app.app_context():
        assert production_metrics.bottleneck_by_group() == []


# ---------- team_scorecard ----------

def test_scorecard_splits_open_from_delivered_per_team(app, sample_client):
    _report(app, sample_client, title='A', team='Wealth', status='draft')
    _report(app, sample_client, title='B', team='Wealth', status='distributed')
    _report(app, sample_client, title='C', team='Sales', status='draft')
    with app.app_context():
        rows = {row['label']: row for row in production_metrics.team_scorecard()}
    assert rows['Wealth']['total'] == 2 and rows['Wealth']['open'] == 1 and rows['Wealth']['delivered'] == 1
    assert rows['Sales']['total'] == 1 and rows['Sales']['delivered'] == 0


def test_scorecard_turnaround_is_null_until_something_is_delivered(app, sample_client):
    _report(app, sample_client, team='Wealth', status='draft', created_days_ago=10)
    with app.app_context():
        assert production_metrics.team_scorecard()[0]['avgTurnaroundDays'] is None


def test_scorecard_turnaround_measures_creation_to_the_delivering_transition(app, sample_client):
    report_id = _report(app, sample_client, team='Wealth', status='distributed', created_days_ago=10)
    with app.app_context():
        db_session.add(ReportTransition(
            report_id=report_id, from_status='approved', to_status='distributed', actor_id=1,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=4),
        ))
        db_session.commit()
        assert production_metrics.team_scorecard()[0]['avgTurnaroundDays'] == 6.0


def test_scorecard_labels_teamless_reports_unassigned(app, sample_client):
    _report(app, sample_client, team=None)
    with app.app_context():
        assert production_metrics.team_scorecard()[0]['label'] == 'Unassigned'


# ---------- sla_at_risk ----------

def test_sla_at_risk_splits_breached_from_approaching(app, sample_client):
    today = datetime.date.today()
    _report(app, sample_client, title='Late', due_date=today - datetime.timedelta(days=1))
    _report(app, sample_client, title='Soon', due_date=today + datetime.timedelta(days=1))
    _report(app, sample_client, title='Later', due_date=today + datetime.timedelta(days=60))
    with app.app_context():
        at_risk = production_metrics.sla_at_risk()
    assert at_risk['breached'] == 1
    assert at_risk['approaching'] == 1


def test_a_report_with_no_due_date_is_not_at_risk(app, sample_client):
    # An absent deadline is not a met one -- it just isn't measurable.
    _report(app, sample_client, due_date=None, created_days_ago=400)
    with app.app_context():
        assert production_metrics.sla_at_risk() == {'breached': 0, 'approaching': 0, 'windowDays': 3}


def test_a_delivered_report_past_its_due_date_is_not_at_risk(app, sample_client):
    _report(
        app, sample_client, status='distributed',
        due_date=datetime.date.today() - datetime.timedelta(days=30),
    )
    with app.app_context():
        assert production_metrics.sla_at_risk()['breached'] == 0


# ---------- endpoints ----------

def test_dashboard_exposes_the_new_day_to_day_keys(client, auth_headers):
    body = client.get('/api/dashboard', headers=auth_headers).get_json()
    for key in ('dataSources', 'missingContent', 'workflowStageProgress', 'slaAtRisk', 'deliverySla'):
        assert key in body, key


def test_data_sources_lists_every_source_not_only_broken_ones(client, auth_headers, app):
    with app.app_context():
        db_session.add(DataSource(name='Healthy', type='api', config='{}', last_sync_status='success', created_by=1))
        db_session.add(DataSource(name='Broken', type='api', config='{}', last_sync_status='error',
                                  last_sync_message='timeout', created_by=1))
        db_session.add(DataSource(name='Never run', type='api', config='{}', created_by=1))
        db_session.commit()

    body = client.get('/api/dashboard', headers=auth_headers).get_json()
    assert {row['name']: row['status'] for row in body['dataSources']} == {
        'Healthy': 'success', 'Broken': 'error', 'Never run': 'never',
    }
    # failedDataSources still means only the broken ones -- the alert banner
    # and several existing callers depend on that.
    assert [row['name'] for row in body['failedDataSources']] == ['Broken']


def test_pending_component_reviews_still_equals_the_length_of_missing_content(client, auth_headers):
    body = client.get('/api/dashboard', headers=auth_headers).get_json()
    assert body['pendingComponentReviews'] == len(body['missingContent'])


def test_management_endpoint_requires_staff_and_returns_its_keys(client, auth_headers, client_portal_headers):
    assert client.get('/api/dashboard/management', headers=client_portal_headers).status_code == 403
    body = client.get('/api/dashboard/management', headers=auth_headers).get_json()
    for key in ('slowestSteps', 'bottleneckByGroup', 'teamScorecard', 'minVisitsForAverage'):
        assert key in body, key
