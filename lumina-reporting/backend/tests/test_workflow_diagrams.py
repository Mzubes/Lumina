def _node(node_id, name, node_type='step'):
    return {'id': node_id, 'name': name, 'type': node_type, 'group_id': None, 'position': {'x': 0, 'y': 0}}

def _edge(edge_id, from_node, to_node, label='Next'):
    return {'id': edge_id, 'from_node': from_node, 'to_node': to_node, 'action_label': label}

VALID_NODES = [
    _node('start', 'Start', 'start'),
    _node('draft', 'Draft'),
    _node('done', 'Distributed', 'terminal'),
]
VALID_EDGES = [
    _edge('e1', 'start', 'draft'),
    _edge('e2', 'draft', 'done', 'Distribute'),
]

def test_get_workflow_null_when_no_diagram(client, auth_headers, sample_template):
    response = client.get(f'/api/templates/{sample_template}/workflow', headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json() is None

def test_get_workflow_404_for_unknown_template(client, auth_headers):
    assert client.get('/api/templates/999/workflow', headers=auth_headers).status_code == 404

def test_save_workflow_requires_admin(client, editor_headers, viewer_headers, sample_template):
    payload = {'nodes': VALID_NODES, 'edges': VALID_EDGES}
    assert client.put(f'/api/templates/{sample_template}/workflow', headers=editor_headers, json=payload).status_code == 403
    assert client.put(f'/api/templates/{sample_template}/workflow', headers=viewer_headers, json=payload).status_code == 403

def test_save_workflow_success_and_get(client, auth_headers, sample_template):
    response = client.put(
        f'/api/templates/{sample_template}/workflow', headers=auth_headers,
        json={'nodes': VALID_NODES, 'edges': VALID_EDGES},
    )
    assert response.status_code == 201
    saved = response.get_json()
    assert saved['version'] == 1
    assert saved['is_active'] is True
    assert len(saved['nodes']) == 3

    fetched = client.get(f'/api/templates/{sample_template}/workflow', headers=auth_headers).get_json()
    assert fetched['id'] == saved['id']

def test_save_workflow_versions_and_deactivates_prior(client, auth_headers, sample_template):
    first = client.put(
        f'/api/templates/{sample_template}/workflow', headers=auth_headers,
        json={'nodes': VALID_NODES, 'edges': VALID_EDGES},
    ).get_json()

    second_nodes = VALID_NODES + [_node('review', 'Review')]
    second_edges = [_edge('e1', 'start', 'draft'), _edge('e2', 'draft', 'review', 'Submit'), _edge('e3', 'review', 'done', 'Distribute')]
    second = client.put(
        f'/api/templates/{sample_template}/workflow', headers=auth_headers,
        json={'nodes': second_nodes, 'edges': second_edges},
    ).get_json()
    assert second['version'] == 2

    history = client.get(f'/api/templates/{sample_template}/workflow/history', headers=auth_headers).get_json()
    assert [h['version'] for h in history] == [2, 1]
    active_flags = {h['id']: h['is_active'] for h in history}
    assert active_flags[first['id']] is False
    assert active_flags[second['id']] is True

    fetched = client.get(f'/api/templates/{sample_template}/workflow', headers=auth_headers).get_json()
    assert fetched['id'] == second['id']

def test_workflow_history_requires_admin(client, editor_headers, sample_template):
    assert client.get(f'/api/templates/{sample_template}/workflow/history', headers=editor_headers).status_code == 403

# ---------- validation ----------

def _put(client, auth_headers, template_id, nodes, edges):
    return client.put(f'/api/templates/{template_id}/workflow', headers=auth_headers, json={'nodes': nodes, 'edges': edges})

def test_save_rejects_missing_start_node(client, auth_headers, sample_template):
    nodes = [_node('draft', 'Draft'), _node('done', 'Done', 'terminal')]
    edges = [_edge('e1', 'draft', 'done')]
    assert _put(client, auth_headers, sample_template, nodes, edges).status_code == 400

def test_save_rejects_two_start_nodes(client, auth_headers, sample_template):
    nodes = [_node('start', 'Start', 'start'), _node('start2', 'Start Also', 'start'), _node('done', 'Done', 'terminal')]
    edges = [_edge('e1', 'start', 'done'), _edge('e2', 'start2', 'done')]
    assert _put(client, auth_headers, sample_template, nodes, edges).status_code == 400

def test_save_rejects_unreachable_node(client, auth_headers, sample_template):
    nodes = [_node('start', 'Start', 'start'), _node('draft', 'Draft'), _node('orphan', 'Orphan')]
    edges = [_edge('e1', 'start', 'draft')]
    response = _put(client, auth_headers, sample_template, nodes, edges)
    assert response.status_code == 400
    assert 'Orphan' in response.get_json()['message']

def test_save_rejects_join_with_fewer_than_two_predecessors(client, auth_headers, sample_template):
    nodes = [_node('start', 'Start', 'start'), _node('a', 'Branch A'), _node('join', 'Join', 'join'), _node('done', 'Done', 'terminal')]
    edges = [_edge('e1', 'start', 'a'), _edge('e2', 'a', 'join'), _edge('e3', 'join', 'done')]
    response = _put(client, auth_headers, sample_template, nodes, edges)
    assert response.status_code == 400
    assert 'Join' in response.get_json()['message']

def test_save_accepts_valid_join_with_two_predecessors(client, auth_headers, sample_template):
    nodes = [
        _node('start', 'Start', 'start'), _node('gw', 'Split', 'parallel_gateway'),
        _node('a', 'Branch A'), _node('b', 'Branch B'), _node('join', 'Join', 'join'),
        _node('done', 'Done', 'terminal'),
    ]
    edges = [
        _edge('e1', 'start', 'gw'), _edge('e2', 'gw', 'a'), _edge('e3', 'gw', 'b'),
        _edge('e4', 'a', 'join'), _edge('e5', 'b', 'join'), _edge('e6', 'join', 'done'),
    ]
    assert _put(client, auth_headers, sample_template, nodes, edges).status_code == 201

def test_save_rejects_edge_referencing_unknown_node(client, auth_headers, sample_template):
    nodes = [_node('start', 'Start', 'start'), _node('done', 'Done', 'terminal')]
    edges = [_edge('e1', 'start', 'nope')]
    assert _put(client, auth_headers, sample_template, nodes, edges).status_code == 400

def test_save_rejects_duplicate_node_ids(client, auth_headers, sample_template):
    nodes = [_node('start', 'Start', 'start'), _node('start', 'Also Start')]
    assert _put(client, auth_headers, sample_template, nodes, []).status_code == 400

def test_save_rejects_empty_nodes(client, auth_headers, sample_template):
    assert _put(client, auth_headers, sample_template, [], []).status_code == 400
