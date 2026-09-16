import json

from database import db_session
from models import Client, Report, ReportTemplate
from report_content import resolve_report_content
from renderers import RENDERERS

FACTSHEET_COMPONENTS = [
    {"id": "fc-1", "type": "holdings_table", "title": "Portfolio Holdings",
     "data_binding": {"dataset": "holdings", "filters": {"as_of": "latest"}}},
    {"id": "fc-2", "type": "text_block", "title": "Overview",
     "data_binding": {"static_text": "Fund overview text."}},
]

def _make_template(app, components, name='Template'):
    with app.app_context():
        template = ReportTemplate(name=name, components=json.dumps(components), created_by=1)
        db_session.add(template)
        db_session.commit()
        return template.id

def _make_report(app, client_id, template_id=None, **overrides):
    with app.app_context():
        report = Report(
            title=overrides.pop('title', 'Report'), client_id=client_id, template_id=template_id,
            status='draft', created_by=1, **overrides,
        )
        db_session.add(report)
        db_session.commit()
        return report.id

def _pitchbook_components(referenced_report_id):
    return [
        {"id": "pb-1", "type": "text_block", "title": "Intro",
         "data_binding": {"static_text": "Welcome slide."}},
        {"id": "pb-2", "type": "report_reference", "title": "Fund Factsheet",
         "data_binding": {"report_id": referenced_report_id}},
    ]

def test_report_reference_inlines_referenced_components(app, sample_client, sample_holding):
    factsheet_template_id = _make_template(app, FACTSHEET_COMPONENTS, name='Factsheet Template')
    factsheet_report_id = _make_report(app, sample_client, template_id=factsheet_template_id, title='Fund Factsheet')

    pitchbook_template_id = _make_template(app, _pitchbook_components(factsheet_report_id), name='Pitchbook Template')
    pitchbook_report_id = _make_report(app, sample_client, template_id=pitchbook_template_id, title='Pitch Book')

    with app.app_context():
        report = db_session.query(Report).filter_by(id=pitchbook_report_id).first()
        template = db_session.query(ReportTemplate).filter_by(id=pitchbook_template_id).first()
        content = resolve_report_content(report, template)

    types = [c['type'] for c in content['components']]
    assert types == ['text_block', 'holdings_table', 'text_block']
    holdings_component = content['components'][1]
    assert holdings_component['rows'] == [['Apple Inc.', 'Equity', 100.0, 17500.0, 12.5]]

def test_report_reference_cross_client_is_refused(app, sample_client):
    with app.app_context():
        other_client = Client(name='Other Institutional')
        db_session.add(other_client)
        db_session.commit()
        other_client_id = other_client.id

    factsheet_template_id = _make_template(app, FACTSHEET_COMPONENTS)
    factsheet_report_id = _make_report(app, other_client_id, template_id=factsheet_template_id)

    pitchbook_template_id = _make_template(app, _pitchbook_components(factsheet_report_id))
    pitchbook_report_id = _make_report(app, sample_client, template_id=pitchbook_template_id)

    with app.app_context():
        report = db_session.query(Report).filter_by(id=pitchbook_report_id).first()
        template = db_session.query(ReportTemplate).filter_by(id=pitchbook_template_id).first()
        content = resolve_report_content(report, template)

    reference_result = content['components'][1]
    assert reference_result['type'] == 'text_block'
    assert 'not found or not accessible' in reference_result['text']

def test_report_reference_missing_report_degrades_gracefully(app, sample_client):
    pitchbook_template_id = _make_template(app, _pitchbook_components(999999))
    pitchbook_report_id = _make_report(app, sample_client, template_id=pitchbook_template_id)

    with app.app_context():
        report = db_session.query(Report).filter_by(id=pitchbook_report_id).first()
        template = db_session.query(ReportTemplate).filter_by(id=pitchbook_template_id).first()
        content = resolve_report_content(report, template)

    assert content['components'][1]['type'] == 'text_block'
    assert 'not found' in content['components'][1]['text']

def test_report_reference_without_template_degrades_gracefully(app, sample_client):
    templateless_report_id = _make_report(app, sample_client, template_id=None, title='No Template Report')
    pitchbook_template_id = _make_template(app, _pitchbook_components(templateless_report_id))
    pitchbook_report_id = _make_report(app, sample_client, template_id=pitchbook_template_id)

    with app.app_context():
        report = db_session.query(Report).filter_by(id=pitchbook_report_id).first()
        template = db_session.query(ReportTemplate).filter_by(id=pitchbook_template_id).first()
        content = resolve_report_content(report, template)

    assert content['components'][1]['type'] == 'text_block'
    assert 'no structured content' in content['components'][1]['text']

def test_nested_report_reference_is_not_expanded(app, sample_client, sample_holding):
    factsheet_template_id = _make_template(app, FACTSHEET_COMPONENTS)
    factsheet_report_id = _make_report(app, sample_client, template_id=factsheet_template_id)

    # A pitchbook that references another pitchbook, which itself references the factsheet.
    inner_pitchbook_template_id = _make_template(app, _pitchbook_components(factsheet_report_id))
    inner_pitchbook_report_id = _make_report(app, sample_client, template_id=inner_pitchbook_template_id)

    outer_pitchbook_template_id = _make_template(app, _pitchbook_components(inner_pitchbook_report_id))
    outer_pitchbook_report_id = _make_report(app, sample_client, template_id=outer_pitchbook_template_id)

    with app.app_context():
        report = db_session.query(Report).filter_by(id=outer_pitchbook_report_id).first()
        template = db_session.query(ReportTemplate).filter_by(id=outer_pitchbook_template_id).first()
        content = resolve_report_content(report, template)

    # intro text, then the inner pitchbook's own intro + a placeholder for its nested reference.
    types = [c['type'] for c in content['components']]
    assert types == ['text_block', 'text_block', 'text_block']
    assert 'Nested report references are not supported' in content['components'][2]['text']

def test_report_reference_renders_through_all_formats(app, sample_client, sample_holding):
    factsheet_template_id = _make_template(app, FACTSHEET_COMPONENTS)
    factsheet_report_id = _make_report(app, sample_client, template_id=factsheet_template_id)
    pitchbook_template_id = _make_template(app, _pitchbook_components(factsheet_report_id))
    pitchbook_report_id = _make_report(app, sample_client, template_id=pitchbook_template_id)

    with app.app_context():
        report = db_session.query(Report).filter_by(id=pitchbook_report_id).first()
        template = db_session.query(ReportTemplate).filter_by(id=pitchbook_template_id).first()
        content = resolve_report_content(report, template)

    assert RENDERERS['pdf'](content)[:4] == b'%PDF'
    assert RENDERERS['pptx'](content)[:2] == b'PK'
    assert RENDERERS['xlsx'](content)[:2] == b'PK'
    raw = json.loads(RENDERERS['raw'](content, raw_format='json'))
    assert raw['components'][1]['type'] == 'holdings_table'
