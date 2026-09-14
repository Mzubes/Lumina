import json

VALID_COMPONENTS = [
    {"id": "comp-1", "type": "holdings_table", "title": "Portfolio Holdings",
     "data_binding": {"dataset": "holdings", "filters": {"as_of": "latest"}}},
    {"id": "comp-2", "type": "text_block", "title": "Commentary",
     "data_binding": {"static_text": "Markets were steady this quarter."}},
]

def _create_template(client, headers):
    return client.post('/api/templates', headers=headers, json={
        'name': 'Quarterly Report', 'components': VALID_COMPONENTS,
    }).get_json()

def _create_templated_report(client, headers, sample_client, template_id):
    return client.post('/api/reports', headers=headers, json={
        'title': 'Q2 Report', 'client_id': sample_client, 'template_id': template_id,
    }).get_json()

def test_create_report_with_template_sets_template_id_and_file(client, auth_headers, sample_client):
    template = _create_template(client, auth_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])
    assert report['template_id'] == template['id']
    assert report['status'] == 'draft'
    assert report['file_path'].endswith('.pdf')

def test_export_pdf_for_templated_report(client, auth_headers, sample_client, sample_holding):
    template = _create_template(client, auth_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])

    response = client.get(f"/api/reports/{report['id']}/export?format=pdf", headers=auth_headers)
    assert response.status_code == 200
    assert response.content_type == 'application/pdf'
    assert response.data[:4] == b'%PDF'

def test_export_pptx_and_xlsx_for_templated_report(client, auth_headers, sample_client):
    template = _create_template(client, auth_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])

    pptx_response = client.get(f"/api/reports/{report['id']}/export?format=pptx", headers=auth_headers)
    assert pptx_response.status_code == 200
    assert pptx_response.data[:2] == b'PK'

    xlsx_response = client.get(f"/api/reports/{report['id']}/export?format=xlsx", headers=auth_headers)
    assert xlsx_response.status_code == 200
    assert xlsx_response.data[:2] == b'PK'

def test_export_raw_json_and_csv(client, auth_headers, sample_client):
    template = _create_template(client, auth_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])

    json_response = client.get(f"/api/reports/{report['id']}/export?format=raw&raw_format=json", headers=auth_headers)
    assert json_response.status_code == 200
    body = json.loads(json_response.data)
    assert body['report_title'] == 'Q2 Report'

    csv_response = client.get(f"/api/reports/{report['id']}/export?format=raw&raw_format=csv", headers=auth_headers)
    assert csv_response.status_code == 200
    assert b'# Commentary' in csv_response.data

def test_export_legacy_report_only_allows_pdf(client, auth_headers, sample_client):
    legacy = client.post('/api/reports', headers=auth_headers, json={
        'title': 'Legacy Freeform Report', 'client_id': sample_client,
    }).get_json()
    assert legacy['template_id'] is None

    pdf_response = client.get(f"/api/reports/{legacy['id']}/export?format=pdf", headers=auth_headers)
    assert pdf_response.status_code == 200
    assert pdf_response.data[:4] == b'%PDF'

    xlsx_response = client.get(f"/api/reports/{legacy['id']}/export?format=xlsx", headers=auth_headers)
    assert xlsx_response.status_code == 400

def test_export_respects_client_portal_scoping(
    client, auth_headers, client_portal_headers, other_client_portal_headers, sample_client,
):
    template = _create_template(client, auth_headers)
    report = _create_templated_report(client, auth_headers, sample_client, template['id'])
    report_id = report['id']

    # Not yet distributed -> invisible to the client portal.
    assert client.get(f"/api/reports/{report_id}/export?format=pdf", headers=client_portal_headers).status_code == 404

    client.post(f"/api/reports/{report_id}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report_id}/approve", headers=auth_headers)
    client.post(f"/api/reports/{report_id}/distribute", headers=auth_headers)

    own = client.get(f"/api/reports/{report_id}/export?format=raw&raw_format=json", headers=client_portal_headers)
    assert own.status_code == 200

    other = client.get(f"/api/reports/{report_id}/export?format=pdf", headers=other_client_portal_headers)
    assert other.status_code == 404
