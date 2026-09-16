import dagre from 'dagre';

const NODE_WIDTH = 200;
const NODE_HEIGHT = 64;

// Only invoked from an explicit "Auto-arrange" toolbar button, never on
// every edit -- dagre doesn't know about a user's manual positioning and
// would fight it if run automatically.
export const autoLayoutPositions = (nodes, edges, direction = 'LR') => {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({ rankdir: direction, nodesep: 50, ranksep: 110 });

  nodes.forEach(node => graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach(edge => graph.setEdge(edge.source, edge.target));

  dagre.layout(graph);

  return nodes.map(node => {
    const position = graph.node(node.id);
    if (!position) return node;
    return { ...node, position: { x: position.x - NODE_WIDTH / 2, y: position.y - NODE_HEIGHT / 2 } };
  });
};
