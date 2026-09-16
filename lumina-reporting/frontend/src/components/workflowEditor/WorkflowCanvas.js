import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MarkerType,
  addEdge, useEdgesState, useNodesState, useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { apiFetch } from '../../api';
import StepNode from './StepNode';
import NodePalette from './NodePalette';
import { autoLayoutPositions } from './autoLayout';

const makeId = (prefix) => `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;

const NODE_TYPES = { workflowStep: StepNode };

const DEFAULT_NODES = [
  {
    id: 'start', type: 'workflowStep', position: { x: 40, y: 140 }, deletable: false,
    data: { name: 'Start', nodeType: 'start', groupId: null, groupName: null, groupColor: null, isDistributionGate: false },
  },
];

const groupById = (groups, id) => groups.find(g => g.id === id) || null;

const toFlowNodes = (domainNodes, groups) => domainNodes.map(n => {
  const group = n.group_id != null ? groupById(groups, n.group_id) : null;
  return {
    id: n.id, type: 'workflowStep', position: n.position || { x: 0, y: 0 }, deletable: n.type !== 'start',
    data: {
      name: n.name, nodeType: n.type, groupId: n.group_id ?? null,
      groupName: group ? group.name : null, groupColor: group ? group.color : null,
      isDistributionGate: !!n.is_distribution_gate,
    },
  };
});

const toFlowEdges = (domainEdges) => domainEdges.map(e => ({
  id: e.id, source: e.from_node, target: e.to_node, label: e.action_label,
  markerEnd: { type: MarkerType.ArrowClosed },
}));

const fromFlowNodes = (flowNodes) => flowNodes.map(n => ({
  id: n.id, name: n.data.name, type: n.data.nodeType, group_id: n.data.groupId,
  position: n.position, is_distribution_gate: !!n.data.isDistributionGate,
  is_terminal: n.data.nodeType === 'terminal',
}));

const fromFlowEdges = (flowEdges) => flowEdges.map(e => ({
  id: e.id, from_node: e.source, to_node: e.target, action_label: e.label || 'Next',
}));

// group_id is meaningless on structural nodes -- the engine never checks
// eligibility against them (they auto-complete), so the inspector doesn't
// offer a group field for these types.
const GROUP_ELIGIBLE_TYPES = new Set(['step', 'join', 'terminal']);

const WorkflowCanvasInner = ({ templateId }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState(null);
  const { screenToFlowPosition } = useReactFlow();

  useEffect(() => {
    apiFetch('/api/workflow-groups').then(setGroups).catch(() => {});
  }, []);

  useEffect(() => {
    if (!templateId) return;
    setLoading(true);
    apiFetch(`/api/templates/${templateId}/workflow`)
      .then(diagram => {
        if (diagram) {
          setNodes(toFlowNodes(diagram.nodes, groups));
          setEdges(toFlowEdges(diagram.edges));
        } else {
          setNodes(DEFAULT_NODES);
          setEdges([]);
        }
      })
      .catch(requestError => setError(requestError.message))
      .finally(() => setLoading(false));
    // Intentionally only re-runs when the template changes -- reloading on
    // every `groups` change would clobber in-progress edits with the
    // last-saved diagram just because someone added a workflow group.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [templateId]);

  const onConnect = useCallback((connection) => {
    setEdges(eds => addEdge({
      ...connection, id: makeId('e'), label: 'Next', markerEnd: { type: MarkerType.ArrowClosed },
    }, eds));
  }, [setEdges]);

  const onSelectionChange = useCallback(({ nodes: selectedNodes, edges: selectedEdges }) => {
    setSelectedNodeId(selectedNodes[0]?.id || null);
    setSelectedEdgeId(selectedEdges[0]?.id || null);
  }, []);

  const handleDrop = useCallback((event) => {
    event.preventDefault();
    const nodeType = event.dataTransfer.getData('application/lumina-workflow-node-type');
    if (!nodeType) return;
    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
    const id = makeId('n');
    const defaultName = { step: 'New Step', parallel_gateway: 'Split', join: 'Join', terminal: 'End' }[nodeType] || 'New Step';
    setNodes(nds => [...nds, {
      id, type: 'workflowStep', position, deletable: true,
      data: { name: defaultName, nodeType, groupId: null, groupName: null, groupColor: null, isDistributionGate: false },
    }]);
  }, [screenToFlowPosition, setNodes]);

  const handleDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const updateSelectedNode = (patch) => {
    setNodes(nds => nds.map(n => (n.id === selectedNodeId ? { ...n, data: { ...n.data, ...patch } } : n)));
  };

  const handleGroupChange = (groupIdValue) => {
    const groupId = groupIdValue ? Number(groupIdValue) : null;
    const group = groupId != null ? groupById(groups, groupId) : null;
    updateSelectedNode({ groupId, groupName: group ? group.name : null, groupColor: group ? group.color : null });
  };

  const updateSelectedEdgeLabel = (label) => {
    setEdges(eds => eds.map(e => (e.id === selectedEdgeId ? { ...e, label } : e)));
  };

  const deleteSelected = () => {
    if (selectedNodeId) {
      setNodes(nds => nds.filter(n => n.id !== selectedNodeId || n.data.nodeType === 'start'));
      setEdges(eds => eds.filter(e => e.source !== selectedNodeId && e.target !== selectedNodeId));
    }
    if (selectedEdgeId) {
      setEdges(eds => eds.filter(e => e.id !== selectedEdgeId));
    }
  };

  const handleAutoArrange = () => setNodes(nds => autoLayoutPositions(nds, edges));

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await apiFetch(`/api/templates/${templateId}/workflow`, {
        method: 'PUT',
        body: JSON.stringify({ nodes: fromFlowNodes(nodes), edges: fromFlowEdges(edges) }),
      });
      setMessage('Workflow saved.');
      setTimeout(() => setMessage(''), 4000);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  };

  const selectedNode = useMemo(() => nodes.find(n => n.id === selectedNodeId) || null, [nodes, selectedNodeId]);
  const selectedEdge = useMemo(() => edges.find(e => e.id === selectedEdgeId) || null, [edges, selectedEdgeId]);

  if (!templateId) return null;

  return (
    <div className="workflow-editor">
      <div className="workflow-editor-toolbar">
        <button type="button" onClick={handleAutoArrange}>Auto-arrange</button>
        <button type="button" onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save workflow'}</button>
        {message && <span className="workflow-editor-toolbar-message">{message}</span>}
      </div>

      <div className="workflow-editor-layout">
        <NodePalette />

        <div className="workflow-canvas-wrapper" onDrop={handleDrop} onDragOver={handleDragOver}>
          {loading ? (
            <p className="panel-subtitle">Loading…</p>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onSelectionChange={onSelectionChange}
              nodeTypes={NODE_TYPES}
              fitView
            >
              <Background />
              <Controls />
            </ReactFlow>
          )}
        </div>

        <div className="workflow-inspector">
          {selectedNode && (
            <>
              <h4>Step</h4>
              <label>Name
                <input
                  value={selectedNode.data.name}
                  onChange={e => updateSelectedNode({ name: e.target.value })}
                />
              </label>
              {GROUP_ELIGIBLE_TYPES.has(selectedNode.data.nodeType) && (
                <label>Workflow group
                  <select value={selectedNode.data.groupId ?? ''} onChange={e => handleGroupChange(e.target.value)}>
                    <option value="">Generic / any staff</option>
                    {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                  </select>
                </label>
              )}
              {selectedNode.data.nodeType === 'terminal' && (
                <label className="checkbox-label">
                  <input
                    type="checkbox" checked={!!selectedNode.data.isDistributionGate}
                    onChange={e => updateSelectedNode({ isDistributionGate: e.target.checked })}
                  /> Distribution gate
                </label>
              )}
              {selectedNode.data.nodeType !== 'start' && (
                <button type="button" onClick={deleteSelected}>Delete step</button>
              )}
            </>
          )}
          {selectedEdge && (
            <>
              <h4>Connection</h4>
              <label>Action label
                <input value={selectedEdge.label || ''} onChange={e => updateSelectedEdgeLabel(e.target.value)} />
              </label>
              <button type="button" onClick={deleteSelected}>Delete connection</button>
            </>
          )}
          {!selectedNode && !selectedEdge && (
            <p className="field-hint">Select a step or connection to edit it.</p>
          )}
        </div>
      </div>

      {error && <p className="form-message">{error}</p>}
    </div>
  );
};

const WorkflowCanvas = ({ templateId }) => (
  <ReactFlowProvider>
    <WorkflowCanvasInner templateId={templateId} />
  </ReactFlowProvider>
);

export default WorkflowCanvas;
