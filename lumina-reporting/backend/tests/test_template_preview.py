from database import db_session
from models import Report, ReportTemplate

def test_preview_renders_a_pdf_with_no_client_selected(client, auth_headers):
    response = client.post('/api/templates/preview', headers=auth_headers, json={
        'name': 'Draft template',
        'components': [{'id': 'c1', 'type': 'text_block', 'title': 'Intro', 'data_binding': {'static_text': 'Hello'}}],
    })
    assert response.status_code == 200
    assert response.content_type == 'application/pdf'
    assert response.data.startswith(b'%PDF')

def test_preview_renders_against_a_real_client(client, auth_headers, sample_client, sample_holding, sample_performance):
    response = client.post('/api/templates/preview', headers=auth_headers, json={
        'name': 'Draft template',
        'client_id': sample_client,
        'components': [
            {'id': 'c1', 'type': 'holdings_table', 'title': 'Holdings', 'data_binding': {'dataset': 'holdings', 'filters': {'as_of': 'latest'}}},
            {'id': 'c2', 'type': 'performance_summary', 'title': 'Performance', 'data_binding': {'dataset': 'performance', 'filters': {'period_types': ['QTD']}}},
        ],
    })
    assert response.status_code == 200
    assert response.data.startswith(b'%PDF')

def test_preview_reflects_theme_and_header_without_saving(client, auth_headers):
    response = client.post('/api/templates/preview', headers=auth_headers, json={
        'name': 'Draft template',
        'components': [{'id': 'c1', 'type': 'text_block', 'title': 'Intro', 'data_binding': {'static_text': 'Hello'}}],
        'header_config': {'title': 'ACME GLOBAL EQUITY', 'subtitle': 'Draft — not yet saved'},
        'theme_config': {'primary_color': '#123456'},
    })
    assert response.status_code == 200
    assert response.data.startswith(b'%PDF')

def test_preview_unknown_client_id_404s(client, auth_headers):
    response = client.post('/api/templates/preview', headers=auth_headers, json={
        'components': [{'id': 'c1', 'type': 'text_block', 'title': 'Intro', 'data_binding': {'static_text': 'Hello'}}],
        'client_id': 999999,
    })
    assert response.status_code == 404

def test_preview_rejects_malformed_components(client, auth_headers):
    response = client.post('/api/templates/preview', headers=auth_headers, json={
        'components': [{'id': 'c1', 'type': 'not_a_real_type'}],
    })
    assert response.status_code == 400

def test_preview_requires_editor_or_admin(client, viewer_headers):
    response = client.post('/api/templates/preview', headers=viewer_headers, json={
        'components': [{'id': 'c1', 'type': 'text_block', 'title': 'Intro', 'data_binding': {'static_text': 'Hello'}}],
    })
    assert response.status_code == 403

def test_preview_never_persists_anything(app, client, auth_headers):
    client.post('/api/templates/preview', headers=auth_headers, json={
        'name': 'Should never be saved',
        'components': [{'id': 'c1', 'type': 'text_block', 'title': 'Intro', 'data_binding': {'static_text': 'Hello'}}],
    })
    with app.app_context():
        assert db_session.query(ReportTemplate).filter_by(name='Should never be saved').first() is None
        assert db_session.query(Report).filter_by(title='Should never be saved').first() is None
