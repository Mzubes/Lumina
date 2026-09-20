VALID_COMPONENTS = [
    {"id": "comp-1", "type": "holdings_table", "title": "Portfolio Holdings",
     "data_binding": {"dataset": "holdings", "filters": {"as_of": "latest"}}},
    {"id": "comp-2", "type": "text_block", "title": "Commentary",
     "data_binding": {"static_text": "Markets were steady this quarter."}},
]

def test_create_template_requires_editor_or_admin(client, viewer_headers):
    response = client.post('/api/templates', headers=viewer_headers, json={
        'name': 'Quarterly Report', 'components': VALID_COMPONENTS,
    })
    assert response.status_code == 403

def test_create_template_success(client, editor_headers):
    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Quarterly Report', 'description': 'Standard quarterly pack',
        'components': VALID_COMPONENTS,
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body['name'] == 'Quarterly Report'
    assert len(body['components']) == 2

def test_create_template_rejects_invalid_type(client, editor_headers):
    bad_components = [{"id": "c1", "type": "bogus_widget", "title": "X", "data_binding": {}}]
    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Bad Template', 'components': bad_components,
    })
    assert response.status_code == 400

def test_create_template_rejects_duplicate_ids(client, editor_headers):
    dup_components = [
        {"id": "c1", "type": "text_block", "title": "A", "data_binding": {"static_text": "x"}},
        {"id": "c1", "type": "text_block", "title": "B", "data_binding": {"static_text": "y"}},
    ]
    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Dup Template', 'components': dup_components,
    })
    assert response.status_code == 400

def test_create_template_rejects_text_block_without_text(client, editor_headers):
    components = [{"id": "c1", "type": "text_block", "title": "Commentary", "data_binding": {}}]
    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Missing Text', 'components': components,
    })
    assert response.status_code == 400

def test_update_and_get_template(client, editor_headers):
    created = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Quarterly Report', 'components': VALID_COMPONENTS,
    }).get_json()

    updated = client.put(f"/api/templates/{created['id']}", headers=editor_headers, json={
        'name': 'Quarterly Report v2', 'components': VALID_COMPONENTS,
    })
    assert updated.status_code == 200
    assert updated.get_json()['name'] == 'Quarterly Report v2'

    fetched = client.get(f"/api/templates/{created['id']}", headers=editor_headers)
    assert fetched.get_json()['name'] == 'Quarterly Report v2'

def test_delete_template_not_in_use(client, editor_headers):
    created = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Disposable', 'components': VALID_COMPONENTS,
    }).get_json()
    response = client.delete(f"/api/templates/{created['id']}", headers=editor_headers)
    assert response.status_code == 204
    assert client.get(f"/api/templates/{created['id']}", headers=editor_headers).status_code == 404

def test_create_template_with_data_table_and_people_grid(client, editor_headers):
    components = [
        {"id": "c1", "type": "data_table", "title": "Strategy Facts",
         "data_binding": {"columns": ["Metric", "Value"], "rows": [["Inception", "April 2021"], ["AUM", "$0.5B"]]}},
        {"id": "c2", "type": "people_grid", "title": "Portfolio Managers",
         "data_binding": {"rows": [{"name": "Evan Fox, CFA", "title": "PM", "detail": "With firm since 2007"}]}},
    ]
    response = client.post('/api/templates', headers=editor_headers, json={'name': 'Factsheet', 'components': components})
    assert response.status_code == 201
    body = response.get_json()
    assert body['components'][0]['type'] == 'data_table'
    assert body['components'][1]['type'] == 'people_grid'

def test_data_table_rejects_mismatched_row_length(client, editor_headers):
    components = [{"id": "c1", "type": "data_table", "title": "Bad Table",
                   "data_binding": {"columns": ["A", "B"], "rows": [["only one"]]}}]
    response = client.post('/api/templates', headers=editor_headers, json={'name': 'Bad', 'components': components})
    assert response.status_code == 400

def test_people_grid_rejects_person_without_name(client, editor_headers):
    components = [{"id": "c1", "type": "people_grid", "title": "Team",
                   "data_binding": {"rows": [{"title": "PM"}]}}]
    response = client.post('/api/templates', headers=editor_headers, json={'name': 'Bad', 'components': components})
    assert response.status_code == 400

def test_create_template_with_header_footer_and_disclosures(client, editor_headers):
    disclosure = client.post('/api/disclosures', headers=editor_headers, json={
        'title': 'General Risk', 'body': 'All investments involve risk.',
    }).get_json()

    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Factsheet', 'components': VALID_COMPONENTS,
        'disclosure_ids': [disclosure['id']],
        'header_config': {'title': 'ACME STRATEGY', 'subtitle': 'As of June 30, 2026'},
        'footer_config': {'text': 'Acme Asset Management'},
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body['disclosure_ids'] == [disclosure['id']]
    assert body['header_config']['title'] == 'ACME STRATEGY'
    assert body['footer_config']['text'] == 'Acme Asset Management'

def test_create_template_with_theme_config(client, editor_headers):
    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Themed Factsheet', 'components': VALID_COMPONENTS,
        'theme_config': {'primary_color': '#0d6b5f', 'accent_color': '#c9bd9a', 'logo_url': 'https://example.com/logo.png'},
    })
    assert response.status_code == 201
    body = response.get_json()
    assert body['theme_config']['primary_color'] == '#0d6b5f'
    assert body['theme_config']['logo_url'] == 'https://example.com/logo.png'

    updated = client.put(f"/api/templates/{body['id']}", headers=editor_headers, json={
        'theme_config': {'primary_color': '#111111'},
    }).get_json()
    assert updated['theme_config']['primary_color'] == '#111111'
    assert 'logo_url' not in updated['theme_config']

def test_data_table_chart_type_validation(client, editor_headers):
    valid_chart_component = [{"id": "c1", "type": "data_table", "title": "Sector Weights",
                               "data_binding": {"columns": ["Sector", "Strategy", "Index"],
                                                 "rows": [["Tech", "10%", "20%"]], "chart_type": "bar_comparison"}}]
    response = client.post('/api/templates', headers=editor_headers, json={'name': 'Chart Table', 'components': valid_chart_component})
    assert response.status_code == 201
    assert response.get_json()['components'][0]['data_binding']['chart_type'] == 'bar_comparison'

    invalid_chart_component = [{"id": "c1", "type": "data_table", "title": "Sector Weights",
                                 "data_binding": {"columns": ["A", "B"], "rows": [["x", "1"]], "chart_type": "pie"}}]
    bad_response = client.post('/api/templates', headers=editor_headers, json={'name': 'Bad Chart', 'components': invalid_chart_component})
    assert bad_response.status_code == 400

def test_create_template_rejects_unknown_disclosure_id(client, editor_headers):
    response = client.post('/api/templates', headers=editor_headers, json={
        'name': 'Factsheet', 'components': VALID_COMPONENTS, 'disclosure_ids': [999999],
    })
    assert response.status_code == 400

def test_delete_template_in_use_is_blocked(app, client, editor_headers, sample_client):
    created = client.post('/api/templates', headers=editor_headers, json={
        'name': 'In Use Template', 'components': VALID_COMPONENTS,
    }).get_json()

    from database import db_session
    from models import Report
    with app.app_context():
        report = Report(
            title='Report using template', client_id=sample_client,
            template_id=created['id'], status='draft', created_by=1,
        )
        db_session.add(report)
        db_session.commit()

    response = client.delete(f"/api/templates/{created['id']}", headers=editor_headers)
    assert response.status_code == 409
