from database import db_session
from models import Report

def _create_report(client, auth_headers, sample_template, client_id=None, fund_id=None):
    payload = {'title': 'Q2 Report', 'template_id': sample_template}
    if client_id:
        payload['client_id'] = client_id
    if fund_id:
        payload['fund_id'] = fund_id
    return client.post('/api/reports', headers=auth_headers, json=payload).get_json()

def _distribute(client, auth_headers, report_id):
    client.post(f"/api/reports/{report_id}/submit", headers=auth_headers)
    client.post(f"/api/reports/{report_id}/approve", headers=auth_headers)
    client.post(f"/api/reports/{report_id}/distribute", headers=auth_headers)

def test_create_link_requires_distributed_report(client, auth_headers, sample_client, sample_template):
    report = _create_report(client, auth_headers, sample_template, client_id=sample_client)
    response = client.post(f"/api/reports/{report['id']}/distribution-links", headers=auth_headers, json={})
    assert response.status_code == 409

def test_create_and_list_link(client, auth_headers, sample_client, sample_template):
    report = _create_report(client, auth_headers, sample_template, client_id=sample_client)
    _distribute(client, auth_headers, report['id'])

    create_response = client.post(f"/api/reports/{report['id']}/distribution-links", headers=auth_headers, json={})
    assert create_response.status_code == 201
    link = create_response.get_json()
    assert link['token']
    assert link['report_id'] == report['id']
    assert link['contact_id'] is None
    assert link['revoked_at'] is None

    list_response = client.get(f"/api/reports/{report['id']}/distribution-links", headers=auth_headers)
    assert list_response.status_code == 200
    assert [row['id'] for row in list_response.get_json()] == [link['id']]

def test_create_link_with_contact_validates_client_scope(client, auth_headers, sample_client, sample_template):
    report = _create_report(client, auth_headers, sample_template, client_id=sample_client)
    _distribute(client, auth_headers, report['id'])

    contact = client.post(
        f"/api/clients/{sample_client}/contacts", headers=auth_headers,
        json={'name': 'Dana Whitfield', 'email': 'dana@example.com'},
    ).get_json()

    ok_response = client.post(
        f"/api/reports/{report['id']}/distribution-links", headers=auth_headers, json={'contact_id': contact['id']},
    )
    assert ok_response.status_code == 201
    assert ok_response.get_json()['contact_id'] == contact['id']

    other_client = client.post('/api/clients', headers=auth_headers, json={'name': 'Other Client'}).get_json()
    other_contact = client.post(
        f"/api/clients/{other_client['id']}/contacts", headers=auth_headers, json={'name': 'Wrong Client Contact'},
    ).get_json()
    bad_response = client.post(
        f"/api/reports/{report['id']}/distribution-links", headers=auth_headers,
        json={'contact_id': other_contact['id']},
    )
    assert bad_response.status_code == 400

def test_create_link_with_contact_rejected_for_fund_scoped_report(client, auth_headers, sample_fund, sample_template):
    report = _create_report(client, auth_headers, sample_template, fund_id=sample_fund)
    _distribute(client, auth_headers, report['id'])
    response = client.post(
        f"/api/reports/{report['id']}/distribution-links", headers=auth_headers, json={'contact_id': 1},
    )
    assert response.status_code == 400

def test_revoke_link_is_idempotent(client, auth_headers, sample_client, sample_template):
    report = _create_report(client, auth_headers, sample_template, client_id=sample_client)
    _distribute(client, auth_headers, report['id'])
    link = client.post(f"/api/reports/{report['id']}/distribution-links", headers=auth_headers, json={}).get_json()

    first = client.post(
        f"/api/reports/{report['id']}/distribution-links/{link['id']}/revoke", headers=auth_headers,
    ).get_json()
    assert first['revoked_at'] is not None

    second = client.post(
        f"/api/reports/{report['id']}/distribution-links/{link['id']}/revoke", headers=auth_headers,
    ).get_json()
    assert second['revoked_at'] == first['revoked_at']

def test_viewer_can_list_but_not_create_or_revoke_links(client, auth_headers, viewer_headers, sample_client, sample_template):
    report = _create_report(client, auth_headers, sample_template, client_id=sample_client)
    _distribute(client, auth_headers, report['id'])

    assert client.get(f"/api/reports/{report['id']}/distribution-links", headers=viewer_headers).status_code == 200
    assert client.post(f"/api/reports/{report['id']}/distribution-links", headers=viewer_headers, json={}).status_code == 403

def test_public_view_and_export_work_without_auth(client, auth_headers, sample_client, sample_template):
    report = _create_report(client, auth_headers, sample_template, client_id=sample_client)
    _distribute(client, auth_headers, report['id'])
    link = client.post(f"/api/reports/{report['id']}/distribution-links", headers=auth_headers, json={}).get_json()
    token = link['token']

    view = client.get(f"/api/public/reports/{token}")
    assert view.status_code == 200
    body = view.get_json()
    assert body['report_title'] == 'Q2 Report'
    assert len(body['components']) == 3

    export = client.get(f"/api/public/reports/{token}/export?format=pdf")
    assert export.status_code == 200
    assert export.data[:4] == b'%PDF'

def test_public_route_404s_for_unknown_token(client):
    assert client.get('/api/public/reports/not-a-real-token').status_code == 404
    assert client.get('/api/public/reports/not-a-real-token/export').status_code == 404

def test_public_route_404s_for_revoked_link(client, auth_headers, sample_client, sample_template):
    report = _create_report(client, auth_headers, sample_template, client_id=sample_client)
    _distribute(client, auth_headers, report['id'])
    link = client.post(f"/api/reports/{report['id']}/distribution-links", headers=auth_headers, json={}).get_json()
    client.post(f"/api/reports/{report['id']}/distribution-links/{link['id']}/revoke", headers=auth_headers)

    assert client.get(f"/api/public/reports/{link['token']}").status_code == 404

def test_public_route_404s_if_report_no_longer_distributed(client, auth_headers, sample_client, sample_template, app):
    report = _create_report(client, auth_headers, sample_template, client_id=sample_client)
    _distribute(client, auth_headers, report['id'])
    link = client.post(f"/api/reports/{report['id']}/distribution-links", headers=auth_headers, json={}).get_json()

    with app.app_context():
        row = db_session.query(Report).filter_by(id=report['id']).first()
        row.status = 'draft'
        db_session.commit()

    assert client.get(f"/api/public/reports/{link['token']}").status_code == 404
