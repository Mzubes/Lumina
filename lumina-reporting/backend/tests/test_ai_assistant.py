import json
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


# ---------- Phase 4e: structured replies, link-only actions, context chips ----------

import ai_actions


def test_only_paths_this_app_actually_routes_are_allowed():
    for path in ('/', '/reports', '/reports/12', '/internal-portal/clients/3',
                 '/reports?overdue=1', '/audit-trail?action_type=distribution'):
        assert ai_actions.is_allowed_path(path), path


def test_an_external_or_crafted_url_is_never_allowed():
    # Each of these is a way a prompt-injected or hallucinated link could try
    # to leave the app; none may reach the UI.
    for path in ('https://evil.example/steal', '//evil.example', 'javascript:alert(1)',
                 'data:text/html,<script>', '/reports#/somewhere-else', '\\\\evil.example',
                 '/nope', '/reports/abc', 'reports', '', None, 123):
        assert not ai_actions.is_allowed_path(path), path


def test_a_query_key_the_page_does_not_use_is_rejected():
    # Stops a crafted link smuggling a redirect target or a token through
    # the query string of an otherwise-valid path.
    assert ai_actions.is_allowed_path('/reports?stuck=1')
    assert not ai_actions.is_allowed_path('/reports?next=https://evil.example')
    assert not ai_actions.is_allowed_path('/reports?stuck=1&token=abc')
    # A page with no declared query keys accepts none at all.
    assert not ai_actions.is_allowed_path('/queue?anything=1')


def test_actions_are_capped_and_unlabelled_ones_dropped():
    actions = ai_actions.sanitize_actions([
        {'label': 'One', 'to': '/reports'},
        {'label': '', 'to': '/queue'},
        {'label': 'Two', 'to': '/queue'},
        {'label': 'Three', 'to': '/templates'},
        {'label': 'Four', 'to': '/clients'},
    ])
    assert [a['label'] for a in actions] == ['One', 'Two', 'Three']


def test_parse_directives_splits_prose_from_actions_and_follow_ups():
    prose, actions, follow_ups = ai_assistant.parse_directives(
        'Two reports are overdue.\n\n'
        '- **Meridian Q3** is 4 days past due\n\n'
        '[[action: Open overdue reports | /reports?overdue=1]]\n'
        '[[followup: Who is the RM on Meridian?]]\n'
    )
    # The directive lines are removed from what the user reads.
    assert '[[' not in prose
    assert prose.startswith('Two reports are overdue.')
    assert actions == [{'label': 'Open overdue reports', 'to': '/reports?overdue=1'}]
    assert follow_ups == ['Who is the RM on Meridian?']


def test_a_malformed_directive_line_is_dropped_without_taking_the_rest_with_it():
    prose, actions, follow_ups = ai_assistant.parse_directives(
        'Here you go.\n'
        '[[action: Missing its path]]\n'
        '[[action: Good one | /queue]]\n'
    )
    assert prose == 'Here you go.'
    assert actions == [{'label': 'Good one', 'to': '/queue'}]
    assert follow_ups == []


def test_an_off_allow_list_action_from_the_model_is_stripped_server_side(client, auth_headers):
    # The safety property worth pinning down: whatever the model proposes,
    # only in-app paths reach the browser.
    reply = (
        'Have a look.\n'
        '[[action: Exfiltrate | https://evil.example/collect]]\n'
        '[[action: Open the queue | /queue]]\n'
    )
    with patch.object(ai_assistant, 'ANTHROPIC_API_KEY', 'test-key'), \
         patch('ai_assistant.requests.post', return_value=_fake_anthropic_response(reply)):
        body = client.post('/api/ai/ask', headers=auth_headers, json={'message': 'What next?'}).get_json()

    assert body['actions'] == [{'label': 'Open the queue', 'to': '/queue'}]
    assert 'evil.example' not in json.dumps(body)


def test_reply_keys_are_additive_and_always_present(client, auth_headers):
    with patch.object(ai_assistant, 'ANTHROPIC_API_KEY', 'test-key'), \
         patch('ai_assistant.requests.post', return_value=_fake_anthropic_response('Plain answer.')):
        body = client.post('/api/ai/ask', headers=auth_headers,
                           json={'message': 'Hi', 'page': 'Reports'}).get_json()

    assert body['reply'] == 'Plain answer.'
    assert body['configured'] is True
    assert body['actions'] == []
    assert body['followUps'] == []
    assert body['contextSummary']


def test_unconfigured_reply_also_carries_the_new_keys(client, auth_headers):
    with patch.object(ai_assistant, 'ANTHROPIC_API_KEY', None):
        body = client.post('/api/ai/ask', headers=auth_headers, json={'message': 'Hi'}).get_json()
    assert body['actions'] == [] and body['followUps'] == [] and body['contextSummary'] is None


def test_context_summary_names_the_snapshot_the_model_was_given(client, auth_headers, sample_client, sample_holding):
    with patch.object(ai_assistant, 'ANTHROPIC_API_KEY', 'test-key'), \
         patch('ai_assistant.requests.post', return_value=_fake_anthropic_response('ok')):
        body = client.post('/api/ai/ask', headers=auth_headers,
                           json={'message': 'Hi', 'page': 'Internal Portal'}).get_json()

    summary = body['contextSummary']
    assert 'Internal Portal' in summary
    assert '1 client' in summary
