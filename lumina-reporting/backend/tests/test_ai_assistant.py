from unittest.mock import MagicMock, patch

import ai_assistant

def _fake_anthropic_response(text='The firm has 1 client on file.'):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {'content': [{'type': 'text', 'text': text}]}
    return response

def test_ai_ask_requires_message(client, auth_headers):
    response = client.post('/api/ai/ask', headers=auth_headers, json={'message': '   '})
    assert response.status_code == 400

def test_ai_ask_requires_staff_role(client, client_portal_headers):
    response = client.post('/api/ai/ask', headers=client_portal_headers, json={'message': 'Hi'})
    assert response.status_code == 403

def test_ai_ask_not_configured_returns_friendly_reply(client, auth_headers):
    with patch.object(ai_assistant, 'ANTHROPIC_API_KEY', None), \
         patch('ai_assistant.requests.post') as mock_post:
        response = client.post('/api/ai/ask', headers=auth_headers, json={'message': 'How is Acme doing?'})
    assert response.status_code == 200
    body = response.get_json()
    assert body['configured'] is False
    assert 'ANTHROPIC_API_KEY' in body['reply']
    mock_post.assert_not_called()

def test_ai_ask_calls_anthropic_with_grounded_firm_data(client, auth_headers, sample_client, sample_holding):
    with patch.object(ai_assistant, 'ANTHROPIC_API_KEY', 'test-key'), \
         patch('ai_assistant.requests.post', return_value=_fake_anthropic_response()) as mock_post:
        response = client.post('/api/ai/ask', headers=auth_headers, json={
            'message': 'How many clients do we have?', 'page': 'Internal Portal',
        })

    assert response.status_code == 200
    body = response.get_json()
    assert body['configured'] is True
    assert body['reply'] == 'The firm has 1 client on file.'

    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs['headers']['x-api-key'] == 'test-key'
    payload = call_kwargs['json']
    assert payload['messages'] == [{'role': 'user', 'content': 'How many clients do we have?'}]
    assert '"clientCount": 1' in payload['system']
    assert 'Internal Portal' in payload['system']

def test_ai_ask_includes_report_context_when_provided(client, auth_headers, sample_client):
    created = client.post('/api/reports', headers=auth_headers, json={'title': 'Q3 Update', 'client_id': sample_client})
    report_id = created.get_json()['id']

    with patch.object(ai_assistant, 'ANTHROPIC_API_KEY', 'test-key'), \
         patch('ai_assistant.requests.post', return_value=_fake_anthropic_response()) as mock_post:
        client.post('/api/ai/ask', headers=auth_headers, json={'message': 'Summarize this report', 'reportId': report_id})

    system_prompt = mock_post.call_args.kwargs['json']['system']
    assert '"title": "Q3 Update"' in system_prompt

def test_ai_ask_unknown_report_id_is_silently_omitted(client, auth_headers):
    with patch.object(ai_assistant, 'ANTHROPIC_API_KEY', 'test-key'), \
         patch('ai_assistant.requests.post', return_value=_fake_anthropic_response()) as mock_post:
        response = client.post('/api/ai/ask', headers=auth_headers, json={'message': 'Hi', 'reportId': 999999})

    assert response.status_code == 200
    assert 'currentReport' not in mock_post.call_args.kwargs['json']['system']

def test_ai_ask_surfaces_request_failure_as_502(client, auth_headers):
    import requests
    with patch.object(ai_assistant, 'ANTHROPIC_API_KEY', 'test-key'), \
         patch('ai_assistant.requests.post', side_effect=requests.ConnectionError('boom')):
        response = client.post('/api/ai/ask', headers=auth_headers, json={'message': 'Hi'})
    assert response.status_code == 502
