import datetime

from database import db_session
from models import Client, Holding, Report, ReportTemplate, User
from report_content import resolve_report_content

def _make_report(app, sample_client, template_id):
    with app.app_context():
        report = Report(
            title='Q2 Report', client_id=sample_client, template_id=template_id,
            status='draft', created_by=1,
        )
        db_session.add(report)
        db_session.commit()
        return report.id

def test_resolve_report_content_all_component_types(
    app, sample_client, sample_holding, sample_performance, sample_template,
):
    report_id = _make_report(app, sample_client, sample_template)
    with app.app_context():
        report = db_session.query(Report).filter_by(id=report_id).first()
        template = db_session.query(ReportTemplate).filter_by(id=sample_template).first()
        content = resolve_report_content(report, template)

    assert content['report_title'] == 'Q2 Report'
    assert content['client_name'] == 'Acme Institutional'
    assert len(content['components']) == 3

    holdings_component = next(c for c in content['components'] if c['type'] == 'holdings_table')
    assert holdings_component['rows'] == [['Apple Inc.', 'Equity', 100.0, 17500.0, 12.5]]

    performance_component = next(c for c in content['components'] if c['type'] == 'performance_summary')
    assert performance_component['rows'] == [['QTD', 3.25, 2.9]]

    text_component = next(c for c in content['components'] if c['type'] == 'text_block')
    assert text_component['text'] == 'Markets were steady this quarter.'

def test_resolve_report_content_excludes_other_clients_data(app, sample_client, sample_holding, sample_template):
    with app.app_context():
        other_client = Client(name='Other Institutional')
        db_session.add(other_client)
        db_session.commit()
        other_holding = Holding(
            client_id=other_client.id, as_of_date=datetime.date(2026, 6, 30),
            security_id='MSFT', market_value=999.0,
        )
        db_session.add(other_holding)
        db_session.commit()
        other_client_id = other_client.id

    report_id = _make_report(app, other_client_id, sample_template)
    with app.app_context():
        report = db_session.query(Report).filter_by(id=report_id).first()
        template = db_session.query(ReportTemplate).filter_by(id=sample_template).first()
        content = resolve_report_content(report, template)

    holdings_component = next(c for c in content['components'] if c['type'] == 'holdings_table')
    security_ids = [row[0] for row in holdings_component['rows']]
    assert 'Apple Inc.' not in security_ids
    assert holdings_component['rows'] == [['MSFT', '', '', 999.0, '']]
