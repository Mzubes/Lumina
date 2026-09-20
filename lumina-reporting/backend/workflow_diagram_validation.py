# Server-side validation for a workflow diagram's nodes/edges JSON, called
# from routes/workflow_diagrams.py before a new version is ever persisted.
# Same "return None on success, an error string otherwise" shape as
# template_components.py's validate_components -- kept as a pure function,
# separate from the route, so it's trivial to unit test.
NODE_TYPES = {'start', 'step', 'parallel_gateway', 'join', 'terminal'}

def validate_diagram(nodes, edges):
    if not isinstance(nodes, list) or not nodes:
        return 'nodes must be a non-empty list'
    if not isinstance(edges, list):
        return 'edges must be a list'

    node_ids = set()
    start_count = 0
    for node in nodes:
        if not isinstance(node, dict):
            return 'each node must be an object'
        node_id = node.get('id')
        if not node_id or node_id in node_ids:
            return 'each node needs a unique id'
        node_ids.add(node_id)
        if not node.get('name'):
            return 'each node needs a name'
        if node.get('type') not in NODE_TYPES:
            return f"invalid node type '{node.get('type')}'"
        if node.get('type') == 'start':
            start_count += 1
    if start_count != 1:
        return 'a diagram needs exactly one start node'

    edge_ids = set()
    predecessors = {}
    outgoing = {}
    for edge in edges:
        if not isinstance(edge, dict):
            return 'each edge must be an object'
        edge_id = edge.get('id')
        if not edge_id or edge_id in edge_ids:
            return 'each edge needs a unique id'
        edge_ids.add(edge_id)
        from_node, to_node = edge.get('from_node'), edge.get('to_node')
        if from_node not in node_ids or to_node not in node_ids:
            return f"edge '{edge_id}' references an unknown node"
        if not edge.get('action_label'):
            return f"edge '{edge_id}' needs an action_label"
        predecessors.setdefault(to_node, set()).add(from_node)
        outgoing.setdefault(from_node, []).append(to_node)

    nodes_by_id = {n['id']: n for n in nodes}
    for node_id, node in nodes_by_id.items():
        if node['type'] == 'join' and len(predecessors.get(node_id, set())) < 2:
            return f"join node '{node['name']}' needs at least 2 incoming edges"

    start_id = next(n['id'] for n in nodes if n['type'] == 'start')
    reachable = {start_id}
    frontier = [start_id]
    while frontier:
        current = frontier.pop()
        for target in outgoing.get(current, []):
            if target not in reachable:
                reachable.add(target)
                frontier.append(target)
    unreachable = node_ids - reachable
    if unreachable:
        names = sorted(nodes_by_id[node_id]['name'] for node_id in unreachable)
        return f"unreachable from start: {', '.join(names)}"

    return None
